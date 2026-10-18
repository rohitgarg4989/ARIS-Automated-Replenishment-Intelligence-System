"""
safety/guardrails.py
=====================
Safety guardrails for the ARIS agent.
Detects unsafe requests and enforces operational boundaries.
"""

import re
from typing import Any


# ════════════════════════════════════════════════════════════════════════════════
# Unsafe request patterns
# ════════════════════════════════════════════════════════════════════════════════
UNSAFE_PATTERNS = [
    r'\b(delete|drop|remove|truncate|wipe)\b',
    r'\b(execute|place|confirm|approve).*(order|purchase)\b',
    r'\b(modify|update|change|edit).*(inventory|stock|record)\b',
    r'\b(bypass|ignore|skip).*(safety|rule|check|policy)\b',
]


def check_unsafe(query: str) -> bool:
    """
    Check if a query contains unsafe patterns that should be refused.
    Returns True if the query is unsafe.
    """
    q_lower = query.lower()
    for pattern in UNSAFE_PATTERNS:
        if re.search(pattern, q_lower, re.IGNORECASE):
            return True
    return False


def get_safety_refusal_message() -> str:
    """Return the standard safety refusal message."""
    return (
        "⚠ **Safety Refusal:** I cannot execute that request.\n\n"
        "My mandate is to GENERATE replenishment recommendations only. "
        "I am not authorised to modify inventory data, execute purchase orders, "
        "or bypass safety controls.\n\n"
        "If you need to make changes, please use your ERP system with appropriate authorisation."
    )


def check_scope(query: str) -> bool:
    """
    Check if a query is within the agent's scope.
    Returns True if the query is in scope.
    """
    in_scope_keywords = [
        "sku", "inventory", "stock", "reorder", "supplier", "lead time",
        "safety stock", "rop", "eoq", "demand", "sales", "forecast",
        "replenish", "order", "warehouse", "delivery", "delay",
        "performance", "reliability", "feedback",
    ]
    q_lower = query.lower()
    return any(kw in q_lower for kw in in_scope_keywords)
