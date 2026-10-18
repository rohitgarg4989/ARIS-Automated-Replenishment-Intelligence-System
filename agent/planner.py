"""
agent/planner.py
=================
Planning logic for the orchestrator — determines tool call sequences
based on detected intent and entities.
"""

import re
from dataclasses import dataclass, field
from typing import Any


# ════════════════════════════════════════════════════════════════════════════════
# Data classes
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
    agent_route: str
    confidence : float = 1.0


# ════════════════════════════════════════════════════════════════════════════════
# Intent patterns
# ════════════════════════════════════════════════════════════════════════════════
INTENT_PATTERNS = {
    "supplier_feedback": r'\b(delay|delayed|feedback|late|arrived|shipment|record.*delivery|delivery.*record)\b',
    "supplier_perf"    : r'\b(supplier performance|performance.*SUP|reliability|on.?time|how has.*supplier|supplier.*perform|lead time|lead_time)\b',
    "sales_analysis"   : r'\b(sales|demand|velocity|forecast|trend|spike)\b',
    "eoq_calc"         : r'\b(eoq|economic order|order quantity)\b',
    "safety_stock"     : r'\b(safety stock|buffer stock)\b',
    "all_sku_check"    : r'(\ball\b.*(sku|item|product|warehouse)|which\s+skus|what\s+skus|list.*sku)',
    "reorder_check"    : r'\b(reorder|reordering|replenish|replenishment|rop|reorder point|need.*reorder|inventory|stock)\b',
    "help"             : r'\b(help|what can|capabilities|how do)\b',
}


# ════════════════════════════════════════════════════════════════════════════════
# Planner
# ════════════════════════════════════════════════════════════════════════════════
class Planner:
    """
    Determines the sequence of tool calls needed to answer a query
    based on the perceived intent and entities.
    """

    def plan(self, perception: Perception) -> Plan:
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
            dates = perception.entities.get("dates", [])
            if len(dates) >= 2 and sku_ids:
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
