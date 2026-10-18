"""
tools/tool_escalate.py
=======================
Validation and HITL (Human-in-the-Loop) escalation logic.
"""

from typing import Any


def validate_outputs(
    tool_outputs: list[dict],
    hitl_threshold: float = 0.60,
    max_reorder_value: float = 50000.0,
) -> dict:
    """
    Validate tool outputs:
    - Check for errors
    - Compute aggregate confidence
    - Determine if HITL escalation is needed
    """
    errors    = [r for r in tool_outputs if r.get("status") == "error"]
    successes = [r for r in tool_outputs if r.get("status") == "success"]

    confidences = [r.get("confidence_score", 0.85)
                   for r in successes if "confidence_score" in r]
    avg_conf    = sum(confidences) / len(confidences) if confidences else (
        0.85 if successes else 0.30
    )

    hitl_reasons = []
    for r in successes:
        if r.get("confidence_score", 1.0) < hitl_threshold:
            hitl_reasons.append(
                f"Low confidence ({r['confidence_score']:.0%}) for {r.get('sku_id','')}"
            )
        if r.get("order_value_usd", 0) > max_reorder_value:
            hitl_reasons.append(
                f"Order value ${r['order_value_usd']:,.0f} exceeds auto-approval limit"
            )
        if r.get("health_status") == "STOCKOUT":
            hitl_reasons.append(
                f"STOCKOUT condition detected for {r.get('sku_id','')}"
            )

    return {
        "errors"        : errors,
        "successes"     : successes,
        "avg_confidence": round(avg_conf, 2),
        "needs_hitl"    : bool(hitl_reasons) or (avg_conf < hitl_threshold),
        "hitl_reasons"  : hitl_reasons,
        "error_count"   : len(errors),
    }


def escalate(validation: dict) -> str:
    """Generate a HITL escalation message."""
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
