"""
agent/core_agent.py
====================
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

from agent.planner import Planner, Perception, Plan, INTENT_PATTERNS
from agent.memory import ShortTermMemory, LongTermMemory, AdaptationMemory
from agent.prompts import ORCHESTRATOR_SYSTEM_PROMPT, PROMPT_VARIANTS
from retrieval.retriever import KnowledgeRetriever
from tools.tool_registry import TOOL_REGISTRY, execute_tool
from tools.tool_escalate import validate_outputs, escalate
from safety.guardrails import check_unsafe, UNSAFE_PATTERNS
from deployment.config import CONFIDENCE_THRESHOLD, HITL_THRESHOLD, MAX_REORDER_VALUE


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
# LLM Clients
# ════════════════════════════════════════════════════════════════════════════════
from deployment.config import (
    is_openai_available, OPENAI_API_KEY, OPENAI_MODEL,
    OPENAI_TEMPERATURE, OPENAI_MAX_TOKENS
)

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


class MockLLM:
    """Template-based responses for demo mode — no API key required."""
    model_name = "MockLLM-v1"

    def _extract_sku(self, text: str) -> str | None:
        match = re.search(r'SKU-\d{3}', text, re.IGNORECASE)
        return match.group(0).upper() if match else None

    def invoke(self, messages: list[dict], tool_results: dict | None = None) -> str:
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        sku_id = self._extract_sku(last_user)
        if tool_results and tool_results.get("status") == "success":
            return self._format_from_tools(tool_results, sku_id or "the SKU")
        else:
            return self._generic_response(last_user, sku_id)

    def _format_from_tools(self, data: dict, sku_id: str) -> str:
        if "reorder_point" in data and "recommended_qty" in data:
            health = data.get("health_status", "UNKNOWN")
            reorder = data.get("reorder_needed", False)
            confidence = data.get("confidence_score", 0.8)
            lines = [
                f"**SUMMARY:** {'⚠ Reorder required' if reorder else '✅ Stock is adequate'} for {sku_id} ({data.get('sku_name','')}).",
                "", "**ANALYSIS:**",
                f"  • Current Stock   : {data.get('current_stock','N/A')} units",
                f"  • Reorder Point   : {data.get('reorder_point','N/A')} units",
                f"  • Safety Stock    : {data.get('safety_stock','N/A')} units",
                f"  • Health Status   : {health}",
                f"  • Supplier        : {data.get('supplier_name','N/A')} (lead time {data.get('lead_time_days','N/A')} days)",
                f"  • Reliability     : {data.get('reliability_score',0):.0%}",
                "", "**RECOMMENDATION:**",
            ]
            if reorder:
                lines += [
                    f"  Raise a purchase order for **{data.get('recommended_qty','N/A')} units** of {sku_id}.",
                    f"  EOQ: {data.get('eoq','N/A')} units | Estimated Value: ${data.get('order_value_usd',0):,.2f}",
                    f"  Approval required: **{data.get('approval_required','N/A').replace('_',' ').title()}**",
                ]
            else:
                lines.append(f"  No immediate reorder needed. Monitor stock; next review in 7 days.")
            lines += [
                "", f"**CONFIDENCE:** {confidence:.0%}",
                "", "**NEXT STEPS:**",
                "  1. Review this recommendation with the Inventory Manager.",
                "  2. If approved, raise the purchase order through your ERP system.",
                "  3. Record delivery outcome in the system to improve future recommendations.",
            ]
            return "\n".join(lines)

        if "on_time_pct" in data:
            return (
                f"**SUPPLIER PERFORMANCE — {data.get('supplier_name','N/A')}**\n\n"
                f"  • On-time deliveries : {data.get('on_time_pct','N/A')}% "
                f"({data.get('on_time_count','N/A')}/{data.get('total_orders','N/A')})\n"
                f"  • Average delay      : {data.get('avg_delay_days','N/A')} days\n"
                f"  • Reliability score  : {data.get('current_reliability_score','N/A'):.2f}\n"
                f"  • Recommended action : {data.get('action','N/A')}\n\n"
                f"**CONFIDENCE:** 85%\n\n"
                f"**NEXT STEPS:** Review delivery contracts if on-time rate < 80%."
            )

        return (
            f"Based on the analysis:\n\n"
            + "\n".join(f"  • {k}: {v}" for k, v in data.items()
                        if k not in ("status","reasoning") and v is not None)
            + "\n\n**CONFIDENCE:** 80%"
        )

    def _generic_response(self, query: str, sku_id: str | None) -> str:
        q = query.lower()
        if any(w in q for w in ["reorder", "stock", "inventory", "rop", "eoq"]):
            sku_ref = sku_id or "the requested SKU"
            return (
                f"I need to check the current inventory data for {sku_ref}. "
                f"Please ensure the inventory data is loaded and retry. "
                f"If this persists, I recommend escalating to the Inventory Manager.\n\n"
                f"**CONFIDENCE:** 40% — insufficient data to provide a recommendation."
            )
        if any(w in q for w in ["supplier", "delay", "lead time"]):
            return (
                "Supplier performance analysis requires delivery feedback records. "
                "Please provide the supplier ID or SKU to retrieve performance data.\n\n"
                "**CONFIDENCE:** 35%"
            )
        if any(w in q for w in ["help", "what can", "capabilities"]):
            return (
                "I am ARIS — the Automated Replenishment Intelligence System. I can:\n\n"
                "  ✅ Check inventory status for any SKU\n"
                "  ✅ Calculate Reorder Points (ROP) and Economic Order Quantities (EOQ)\n"
                "  ✅ Analyse supplier lead times and delivery performance\n"
                "  ✅ Record supplier delivery feedback\n"
                "  ✅ Generate purchase order recommendations\n\n"
                "Try asking: 'Does SKU-001 need reordering?' or 'Show me supplier performance for SUP-B'"
            )
        if any(w in q for w in ["delete", "modify", "update inventory", "place order", "execute"]):
            return (
                "⚠ **Safety Refusal:** I cannot directly modify inventory records, "
                "execute purchase orders, or delete data. My role is to GENERATE "
                "recommendations only. Please use your ERP system to execute approved orders.\n\n"
                "**ESCALATION:** If this is urgent, please contact the Inventory Manager directly."
            )
        return (
            "I'm ARIS, your Inventory Replenishment Agent. Please ask me about "
            "stock levels, reorder recommendations, or supplier performance for specific SKUs. "
            "Example: 'Should I reorder SKU-008?'"
        )


class LangChainLLM:
    """Thin wrapper around LangChain's ChatOpenAI."""

    def __init__(self):
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("langchain-openai is not installed.")
        self._llm = ChatOpenAI(
            api_key    = OPENAI_API_KEY,
            model      = OPENAI_MODEL,
            temperature= OPENAI_TEMPERATURE,
            max_tokens = OPENAI_MAX_TOKENS,
        )
        self.model_name = OPENAI_MODEL

    def invoke(self, messages: list[dict], tool_results: dict | None = None) -> str:
        lc_messages = []
        for m in messages:
            role    = m["role"]
            content = m["content"]
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))

        if tool_results:
            tool_ctx = f"\n\n[TOOL RESULTS]\n{json.dumps(tool_results, indent=2)}"
            if lc_messages and hasattr(lc_messages[-1], "content"):
                lc_messages[-1].content += tool_ctx

        response = self._llm.invoke(lc_messages)
        return response.content


def get_llm():
    """Return the appropriate LLM client based on configuration."""
    if is_openai_available() and LANGCHAIN_AVAILABLE:
        try:
            return LangChainLLM()
        except Exception as e:
            print(f"  ⚠ LangChain LLM init failed ({e}). Falling back to MockLLM.")
    return MockLLM()


# ════════════════════════════════════════════════════════════════════════════════
# AgentResponse
# ════════════════════════════════════════════════════════════════════════════════
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
        self.planner      = Planner()
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
        q_lower = query.lower()

        # Safety check first
        if check_unsafe(q_lower):
            return Perception(
                intent="unsafe_request", entities={}, sku_ids=[],
                raw_query=query, requires_tools=False, policy_context="",
            )

        # Intent detection
        detected_intent = "general"
        for intent, pattern in INTENT_PATTERNS.items():
            if re.search(pattern, q_lower, re.IGNORECASE):
                detected_intent = intent
                break

        # Entity extraction
        sku_ids   = [s.upper() for s in re.findall(r'SKU-\d{3}', query, re.IGNORECASE)]
        sup_ids   = [s.upper() for s in re.findall(r'SUP-[A-E]', query, re.IGNORECASE)]
        date_strs = re.findall(r'\d{4}-\d{2}-\d{2}', query)

        entities = {"sku_ids": sku_ids, "sup_ids": sup_ids, "dates": date_strs}
        if detected_intent == "all_sku_check":
            entities["check_all"] = True

        policy_context = ""
        if self.retriever.is_ready:
            policy_context = self.retriever.format_context(query, k=2)

        requires_tools = detected_intent not in ("help", "general", "unsafe_request")

        return Perception(
            intent=detected_intent, entities=entities, sku_ids=sku_ids,
            raw_query=query, requires_tools=requires_tools,
            policy_context=policy_context,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: ACT
    # ─────────────────────────────────────────────────────────────────────────
    def _act(self, plan: Plan) -> list[dict]:
        results = []
        for step in plan.steps:
            tool_name = step.get("tool")
            kwargs    = step.get("kwargs", {})
            label     = step.get("label", tool_name)

            if tool_name is None:
                results.append({"label": label, "status": "skipped",
                                 "message": "No tool specified."})
                continue

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
    # PUBLIC: run()
    # ─────────────────────────────────────────────────────────────────────────
    def run(self, user_query: str) -> AgentResponse:
        start_ms = time.time()
        trace    = []

        logger.info("QUERY: %s", user_query[:200])
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
        plan = self.planner.plan(perception)
        trace.append(f"PLAN: route={plan.agent_route}, steps={len(plan.steps)}")
        logger.info("PLAN  | route=%s steps=%d", plan.agent_route, len(plan.steps))

        # ── ACT ──────────────────────────────────────────────────────────────
        tool_outputs = self._act(plan)
        trace.append(f"ACT: executed {len(tool_outputs)} tool calls")

        # ── VALIDATE ─────────────────────────────────────────────────────────
        validation = validate_outputs(tool_outputs, HITL_THRESHOLD, MAX_REORDER_VALUE)
        trace.append(f"VALIDATE: confidence={validation['avg_confidence']:.0%}, "
                     f"hitl={validation['needs_hitl']}, errors={validation['error_count']}")
        logger.info("VALIDATE | conf=%.2f hitl=%s errors=%d",
                    validation["avg_confidence"], validation["needs_hitl"],
                    validation["error_count"])

        # ── HITL ─────────────────────────────────────────────────────────────
        if validation["needs_hitl"]:
            answer = escalate(validation)
            self.st_memory.add("assistant", answer)
            return AgentResponse(
                answer=answer, tool_outputs=tool_outputs,
                confidence=validation["avg_confidence"],
                escalated=True,
                escalation_reason="; ".join(validation["hitl_reasons"]),
                plan_trace=trace,
                latency_ms=int((time.time()-start_ms)*1000),
            )

        # ── Generate LLM response ────────────────────────────────────────────
        messages = [{"role": "system", "content": self.system_prompt}]
        if perception.policy_context:
            messages.append({"role": "user", "content": perception.policy_context})
            messages.append({"role": "assistant",
                             "content": "I have reviewed the relevant policies and will apply them."})

        for turn in self.st_memory.get_history()[-10:]:
            messages.append({"role": turn["role"], "content": turn["content"]})

        best_output = None
        if validation["successes"]:
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

        # ── Log to long-term memory ──────────────────────────────────────────
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
            answer=answer, tool_outputs=tool_outputs,
            confidence=validation["avg_confidence"],
            escalated=False, plan_trace=trace, latency_ms=latency,
        )

    def set_prompt_variant(self, variant: str):
        self.system_prompt = PROMPT_VARIANTS.get(variant, ORCHESTRATOR_SYSTEM_PROMPT)
        logger.info("Switched to prompt variant: %s", variant)

    def provide_feedback(self, sku_id: str, was_helpful: bool, comment: str = ""):
        self.adaptation.record_feedback(sku_id, was_helpful, comment)
        mult = self.adaptation.get_safety_stock_multiplier()
        logger.info("Feedback recorded: sku=%s helpful=%s mult=%.2f", sku_id, was_helpful, mult)
        return f"Feedback recorded. Safety stock multiplier: {mult:.2f}"
