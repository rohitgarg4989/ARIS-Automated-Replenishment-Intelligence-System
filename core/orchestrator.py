"""
agents/orchestrator.py
=======================
Orchestrator Agent — implements the full agent loop:
  Perceive → Plan → Act → Validate → HITL

Coordinates all specialist agents and enforces safety rules.
"""

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.llm_client import get_llm
from core.memory import ShortTermMemory, LongTermMemory, AdaptationMemory
from prompts.system import ORCHESTRATOR_SYSTEM_PROMPT, PROMPT_VARIANTS
from core.retriever import KnowledgeRetriever
from tools import TOOL_REGISTRY, execute_tool
from config import CONFIDENCE_THRESHOLD, HITL_THRESHOLD, MAX_REORDER_VALUE


# ── Logging helper ────────────────────────────────────────────────────────────
import logging
import os

log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "agent.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger("OrchestratorAgent")


# ════════════════════════════════════════════════════════════════════════════════
# Data classes for the agent loop
# ════════════════════════════════════════════════════════════════════════════════
@dataclass
class Perception:
    intent         : str
    entities       : dict
    sku_ids        : list[str]
    raw_query      : str
    requires_tools : bool
    policy_context : str = ""


@dataclass
class Plan:
    steps      : list[dict]
    agent_route: str   # "sales" | "inventory" | "supplier" | "feedback" | "general"
    confidence : float = 1.0


@dataclass
class AgentResponse:
    answer          : str
    tool_outputs    : list[dict] = field(default_factory=list)
    confidence      : float = 1.0
    escalated       : bool  = False
    escalation_reason: str  = ""
    plan_trace      : list[str] = field(default_factory=list)
    latency_ms      : int   = 0


# ════════════════════════════════════════════════════════════════════════════════
# Intent patterns
# ════════════════════════════════════════════════════════════════════════════════
_INTENT_PATTERNS = {
    # Check feedback FIRST (most specific — has "delay", "late", "record", "arrived")
    "supplier_feedback": r'\b(delay|delayed|feedback|late|arrived|shipment|record.*delivery|delivery.*record)\b',
    "supplier_perf"    : r'\b(supplier performance|performance.*SUP|reliability|on.?time|how has.*supplier|supplier.*perform|lead time|lead_time)\b',
    "sales_analysis"   : r'\b(sales|demand|velocity|forecast|trend|spike)\b',
    "eoq_calc"         : r'\b(eoq|economic order|order quantity)\b',
    "safety_stock"     : r'\b(safety stock|buffer stock)\b',
    "all_sku_check"    : r'(\ball\b.*(sku|item|product|warehouse)|which\s+skus|what\s+skus|list.*sku)',
    # reorder_check — broad but after more specific patterns
    "reorder_check"    : r'\b(reorder|reordering|replenish|replenishment|rop|reorder point|need.*reorder|inventory|stock)\b',
    "help"             : r'\b(help|what can|capabilities|how do)\b',
}

_UNSAFE_PATTERNS = [
    r'\b(delete|drop|remove|truncate|wipe)\b',
    r'\b(execute|place|confirm|approve).*(order|purchase)\b',
    r'\b(modify|update|change|edit).*(inventory|stock|record)\b',
    r'\b(bypass|ignore|skip).*(safety|rule|check|policy)\b',
]


# ════════════════════════════════════════════════════════════════════════════════
# OrchestratorAgent
# ════════════════════════════════════════════════════════════════════════════════
class OrchestratorAgent:
    """
    Central coordinator implementing Perceive → Plan → Act → Validate → HITL.
    """

    def __init__(self, prompt_variant: str = "v3_cot"):
        self.llm          = get_llm()
        self.st_memory    = ShortTermMemory(max_turns=20)
        self.lt_memory    = LongTermMemory()
        self.adaptation   = AdaptationMemory()
        self.retriever    = KnowledgeRetriever()
        self.system_prompt = PROMPT_VARIANTS.get(prompt_variant, ORCHESTRATOR_SYSTEM_PROMPT)
        self._build_retriever()
        logger.info("OrchestratorAgent initialised (LLM: %s, prompt: %s)",
                    self.llm.model_name, prompt_variant)

    def _build_retriever(self):
        try:
            self.retriever.build()
        except Exception as e:
            logger.warning("RAG retriever build failed: %s", e)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: PERCEIVE
    # ─────────────────────────────────────────────────────────────────────────
    def _perceive(self, query: str) -> Perception:
        """
        Understand the user query:
        - Classify intent
        - Extract entities (SKU IDs, supplier IDs, dates)
        - Retrieve relevant policy context
        - Check for unsafe requests
        """
        q_lower = query.lower()

        # Safety check first
        for pattern in _UNSAFE_PATTERNS:
            if re.search(pattern, q_lower, re.IGNORECASE):
                return Perception(
                    intent="unsafe_request",
                    entities={},
                    sku_ids=[],
                    raw_query=query,
                    requires_tools=False,
                    policy_context="",
                )

        # Intent detection
        detected_intent = "general"
        for intent, pattern in _INTENT_PATTERNS.items():
            if re.search(pattern, q_lower, re.IGNORECASE):
                detected_intent = intent
                break

        # Entity extraction
        sku_ids     = re.findall(r'SKU-\d{3}', query, re.IGNORECASE)
        sku_ids     = [s.upper() for s in sku_ids]
        sup_ids     = re.findall(r'SUP-[A-E]', query, re.IGNORECASE)
        sup_ids     = [s.upper() for s in sup_ids]
        date_strs   = re.findall(r'\d{4}-\d{2}-\d{2}', query)

        entities = {
            "sku_ids"   : sku_ids,
            "sup_ids"   : sup_ids,
            "dates"     : date_strs,
        }

        if detected_intent == "all_sku_check":
            entities["check_all"] = True

        # Retrieve policy context
        policy_context = ""
        if self.retriever.is_ready:
            policy_context = self.retriever.format_context(query, k=2)

        requires_tools = detected_intent not in ("help", "general", "unsafe_request")

        return Perception(
            intent        = detected_intent,
            entities      = entities,
            sku_ids       = sku_ids,
            raw_query     = query,
            requires_tools= requires_tools,
            policy_context= policy_context,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: PLAN
    # ─────────────────────────────────────────────────────────────────────────
    def _plan(self, perception: Perception) -> Plan:
        """
        Determine the sequence of tool calls needed to answer the query.
        """
        intent   = perception.intent
        sku_ids  = perception.sku_ids
        sup_ids  = perception.entities.get("sup_ids", [])

        steps: list[dict] = []

        if intent == "unsafe_request":
            return Plan(steps=[], agent_route="safety_refusal", confidence=1.0)

        if intent in ("reorder_check", "all_sku_check"):
            targets = sku_ids if sku_ids else (
                ["ALL"] if perception.entities.get("check_all") else []
            )
            for sku in targets:
                steps.append({
                    "tool"  : "generate_reorder_recommendation",
                    "kwargs": {"sku_id": sku, "include_reasoning": True},
                    "label" : f"Full recommendation for {sku}",
                })
            if not targets:
                steps.append({"tool": None, "label": "no_sku_provided"})

        elif intent == "eoq_calc":
            for sku in sku_ids:
                steps.append({
                    "tool"  : "calculate_eoq",
                    "kwargs": {"sku_id": sku},
                    "label" : f"EOQ for {sku}",
                })
            if not sku_ids:
                steps.append({"tool": None, "label": "no_sku_provided"})

        elif intent == "safety_stock":
            for sku in sku_ids:
                steps.append({
                    "tool"  : "calculate_safety_stock",
                    "kwargs": {"sku_id": sku},
                    "label" : f"Safety stock for {sku}",
                })
            if not sku_ids:
                steps.append({"tool": None, "label": "no_sku_provided"})

        elif intent == "sales_analysis":
            for sku in sku_ids:
                steps += [
                    {"tool": "analyze_sales_velocity",
                     "kwargs": {"sku_id": sku, "lookback_days": 30},
                     "label": f"Sales velocity for {sku}"},
                    {"tool": "forecast_demand",
                     "kwargs": {"sku_id": sku, "forecast_days": 30},
                     "label": f"Demand forecast for {sku}"},
                    {"tool": "detect_demand_spike",
                     "kwargs": {"sku_id": sku},
                     "label": f"Spike detection for {sku}"},
                ]

        elif intent == "supplier_feedback":
            # If dates are present in the query, attempt a record_supplier_feedback call
            dates = perception.entities.get("dates", [])
            if len(dates) >= 2 and sku_ids:
                # Determine delay reason
                q_low = perception.raw_query.lower()
                reason_map = [
                    ("port congestion",     "Port congestion causing shipment hold"),
                    ("production backlog",  "Supplier production backlog"),
                    ("customs",             "Customs clearance delay"),
                    ("weather",             "Weather disruption at origin warehouse"),
                    ("raw material",        "Raw material shortage at supplier facility"),
                ]
                reason = "On time"
                for kw, label in reason_map:
                    if kw in q_low:
                        reason = label
                        break
                if any(w in q_low for w in ["late", "delay", "delayed"]) and reason == "On time":
                    reason = "Other"

                order_dt    = dates[0] if len(dates) > 0 else ""
                expected_dt = dates[1] if len(dates) > 1 else ""
                actual_dt   = dates[2] if len(dates) > 2 else dates[1]

                for sku in sku_ids:
                    steps.append({
                        "tool"  : "record_supplier_feedback",
                        "kwargs": {
                            "sku_id"           : sku,
                            "order_date"       : order_dt,
                            "expected_delivery": expected_dt,
                            "actual_delivery"  : actual_dt,
                            "delay_reason"     : reason,
                        },
                        "label" : f"Record feedback for {sku}",
                    })
            else:
                # Collect info only — feedback recording needs specific dates
                for sku in sku_ids:
                    steps.append({
                        "tool"  : "get_supplier_lead_time",
                        "kwargs": {"sku_id": sku},
                        "label" : f"Lead time for {sku}",
                    })

        elif intent == "supplier_perf":
            targets = sup_ids if sup_ids else []
            for sid in targets:
                steps.append({
                    "tool"  : "analyze_supplier_performance",
                    "kwargs": {"supplier_id": sid, "lookback_days": 180},
                    "label" : f"Performance for {sid}",
                })
            if not targets and sku_ids:
                for sku in sku_ids:
                    steps.append({
                        "tool"  : "get_supplier_lead_time",
                        "kwargs": {"sku_id": sku},
                        "label" : f"Supplier info for {sku}",
                    })

        route_map = {
            "reorder_check": "inventory", "eoq_calc": "inventory",
            "safety_stock" : "inventory", "sales_analysis": "sales",
            "supplier_perf": "supplier",  "supplier_feedback": "supplier",
            "all_sku_check": "inventory", "help": "general",
        }

        return Plan(
            steps       = steps,
            agent_route = route_map.get(intent, "general"),
            confidence  = 0.90 if steps else 0.50,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: ACT
    # ─────────────────────────────────────────────────────────────────────────
    def _act(self, plan: Plan) -> list[dict]:
        """Execute all planned tool calls and collect results."""
        results = []
        for step in plan.steps:
            tool_name = step.get("tool")
            kwargs    = step.get("kwargs", {})
            label     = step.get("label", tool_name)

            if tool_name is None:
                results.append({"label": label, "status": "skipped",
                                 "message": "No tool specified."})
                continue

            # Apply adaptation: adjust safety_stock_multiplier via service level
            if tool_name in ("calculate_rop", "calculate_safety_stock"):
                sku = kwargs.get("sku_id", "")
                if sku and sku != "ALL":
                    sl = self.adaptation.get_service_level(sku, 0.95)
                    kwargs.setdefault("service_level", sl)

            logger.info("ACT  | tool=%s kwargs=%s", tool_name, kwargs)
            result = execute_tool(tool_name, **kwargs)
            result["_label"] = label
            results.append(result)

        return results

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: VALIDATE
    # ─────────────────────────────────────────────────────────────────────────
    def _validate(self, tool_outputs: list[dict], perception: Perception) -> dict:
        """
        Validate tool outputs:
        - Check for errors
        - Compute aggregate confidence
        - Determine if HITL escalation is needed
        """
        errors     = [r for r in tool_outputs if r.get("status") == "error"]
        successes  = [r for r in tool_outputs if r.get("status") == "success"]

        # Aggregate confidence from tool outputs
        confidences = [r.get("confidence_score", 0.85)
                       for r in successes if "confidence_score" in r]
        avg_conf    = sum(confidences) / len(confidences) if confidences else (
            0.85 if successes else 0.30
        )

        # Check for HITL triggers
        hitl_reasons = []
        for r in successes:
            if r.get("confidence_score", 1.0) < HITL_THRESHOLD:
                hitl_reasons.append(f"Low confidence ({r['confidence_score']:.0%}) for {r.get('sku_id','')}")
            if r.get("order_value_usd", 0) > MAX_REORDER_VALUE:
                hitl_reasons.append(f"Order value ${r['order_value_usd']:,.0f} exceeds auto-approval limit")
            if r.get("health_status") == "STOCKOUT":
                hitl_reasons.append(f"STOCKOUT condition detected for {r.get('sku_id','')}")

        return {
            "errors"        : errors,
            "successes"     : successes,
            "avg_confidence": round(avg_conf, 2),
            "needs_hitl"    : bool(hitl_reasons) or (avg_conf < HITL_THRESHOLD),
            "hitl_reasons"  : hitl_reasons,
            "error_count"   : len(errors),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5: HITL Escalation
    # ─────────────────────────────────────────────────────────────────────────
    def _escalate(self, validation: dict) -> str:
        reasons = "\n".join(f"  • {r}" for r in validation["hitl_reasons"])
        return (
            "⚠ **HUMAN ESCALATION REQUIRED**\n\n"
            "This recommendation requires review by a human analyst before action.\n\n"
            f"**Escalation reasons:**\n{reasons}\n\n"
            f"**Confidence:** {validation['avg_confidence']:.0%}\n\n"
            "**Action:** Please contact the Inventory Manager or Procurement Analyst "
            "to review the data and authorise the necessary actions.\n\n"
            "I will retain the analysis context for the next 20 minutes."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC: run()
    # ─────────────────────────────────────────────────────────────────────────
    def run(self, user_query: str) -> AgentResponse:
        """
        Main agent loop: Perceive → Plan → Act → Validate → HITL → Respond
        """
        start_ms = time.time()
        trace    = []

        logger.info("QUERY: %s", user_query[:200])

        # ── Memory: add user turn ─────────────────────────────────────────────
        self.st_memory.add("user", user_query)

        # ── PERCEIVE ─────────────────────────────────────────────────────────
        perception = self._perceive(user_query)
        trace.append(f"PERCEIVE: intent={perception.intent}, skus={perception.sku_ids}")
        logger.info("PERCEIVE | intent=%s entities=%s", perception.intent, perception.entities)

        # Safety refusal — short-circuit
        if perception.intent == "unsafe_request":
            answer = (
                "⚠ **Safety Refusal:** I cannot execute that request.\n\n"
                "My mandate is to GENERATE replenishment recommendations only. "
                "I am not authorised to modify inventory data, execute purchase orders, "
                "or bypass safety controls.\n\n"
                "If you need to make changes, please use your ERP system with appropriate authorisation."
            )
            self.st_memory.add("assistant", answer)
            return AgentResponse(
                answer=answer, confidence=1.0, escalated=False,
                plan_trace=trace, latency_ms=int((time.time()-start_ms)*1000)
            )

        # ── PLAN ─────────────────────────────────────────────────────────────
        plan = self._plan(perception)
        trace.append(f"PLAN: route={plan.agent_route}, steps={len(plan.steps)}")
        logger.info("PLAN  | route=%s steps=%d", plan.agent_route, len(plan.steps))

        # ── ACT ──────────────────────────────────────────────────────────────
        tool_outputs = self._act(plan)
        trace.append(f"ACT: executed {len(tool_outputs)} tool calls")

        # ── VALIDATE ─────────────────────────────────────────────────────────
        validation = self._validate(tool_outputs, perception)
        trace.append(f"VALIDATE: confidence={validation['avg_confidence']:.0%}, "
                     f"hitl={validation['needs_hitl']}, errors={validation['error_count']}")
        logger.info("VALIDATE | conf=%.2f hitl=%s errors=%d",
                    validation["avg_confidence"], validation["needs_hitl"],
                    validation["error_count"])

        # ── HITL ─────────────────────────────────────────────────────────────
        if validation["needs_hitl"]:
            answer = self._escalate(validation)
            self.st_memory.add("assistant", answer)
            return AgentResponse(
                answer=answer,
                tool_outputs=tool_outputs,
                confidence=validation["avg_confidence"],
                escalated=True,
                escalation_reason="; ".join(validation["hitl_reasons"]),
                plan_trace=trace,
                latency_ms=int((time.time()-start_ms)*1000),
            )

        # ── Generate LLM response ─────────────────────────────────────────────
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        if perception.policy_context:
            messages.append({
                "role"   : "user",
                "content": perception.policy_context,
            })
            messages.append({
                "role"   : "assistant",
                "content": "I have reviewed the relevant policies and will apply them.",
            })

        # Add conversation history (last 5 turns)
        for turn in self.st_memory.get_history()[-10:]:
            messages.append({"role": turn["role"], "content": turn["content"]})

        # Pick the most informative tool output
        best_output = None
        if validation["successes"]:
            # Prefer recommendations with confidence scores
            recs = [r for r in validation["successes"] if "confidence_score" in r]
            best_output = recs[0] if recs else validation["successes"][0]

        try:
            answer = self.llm.invoke(messages, tool_results=best_output)
        except Exception as e:
            logger.error("LLM invocation failed: %s", e)
            answer = (
                f"I encountered an error generating the response: {e}\n\n"
                f"**Raw analysis results:**\n"
                + "\n".join(
                    f"  • {r.get('sku_id','')}: {r.get('health_status','')} "
                    f"(reorder: {r.get('reorder_needed','')})"
                    for r in validation["successes"]
                )
            )

        # ── Log to long-term memory ────────────────────────────────────────────
        for r in validation["successes"]:
            if r.get("reorder_needed"):
                self.lt_memory.add_recommendation({
                    "sku_id"      : r.get("sku_id"),
                    "recommended_qty": r.get("recommended_qty"),
                    "confidence"  : r.get("confidence_score"),
                    "query"       : user_query[:100],
                })

        self.st_memory.add("assistant", answer)
        latency = int((time.time()-start_ms)*1000)
        logger.info("RESPOND | latency=%dms len=%d", latency, len(answer))

        return AgentResponse(
            answer       = answer,
            tool_outputs = tool_outputs,
            confidence   = validation["avg_confidence"],
            escalated    = False,
            plan_trace   = trace,
            latency_ms   = latency,
        )

    def set_prompt_variant(self, variant: str):
        """Switch prompt variant (for Phase 3 comparison)."""
        self.system_prompt = PROMPT_VARIANTS.get(variant, ORCHESTRATOR_SYSTEM_PROMPT)
        logger.info("Switched to prompt variant: %s", variant)

    def provide_feedback(self, sku_id: str, was_helpful: bool, comment: str = ""):
        """Record user feedback on the last recommendation (Phase 7)."""
        self.adaptation.record_feedback(sku_id, was_helpful, comment)
        mult = self.adaptation.get_safety_stock_multiplier()
        logger.info("Feedback recorded: sku=%s helpful=%s mult=%.2f",
                    sku_id, was_helpful, mult)
        return f"Feedback recorded. Safety stock multiplier: {mult:.2f}"
