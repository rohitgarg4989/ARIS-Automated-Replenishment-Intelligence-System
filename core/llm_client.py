"""
agents/llm_client.py
====================
Unified LLM client that supports:
  - OpenAI API (real)
  - MockLLM (template-based, for demo without API key)

All agents import from here so switching providers is a single change.
"""

import json
import time
from typing import Any

from config import (
    is_openai_available, OPENAI_API_KEY, OPENAI_MODEL,
    OPENAI_TEMPERATURE, OPENAI_MAX_TOKENS
)

# ── Try importing LangChain OpenAI ────────────────────────────────────────────
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


# ════════════════════════════════════════════════════════════════════════════════
# MockLLM — template-based responses for demo mode
# ════════════════════════════════════════════════════════════════════════════════
class MockLLM:
    """
    Generates structured, realistic-looking responses using tool outputs
    and templates. No API key required.
    """
    model_name = "MockLLM-v1"

    def _extract_sku(self, text: str) -> str | None:
        import re
        match = re.search(r'SKU-\d{3}', text, re.IGNORECASE)
        return match.group(0).upper() if match else None

    def invoke(self, messages: list[dict], tool_results: dict | None = None) -> str:
        """Generate a response from messages + optional tool results."""
        # Build context from last human message
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            ""
        )
        sku_id = self._extract_sku(last_user)

        if tool_results and tool_results.get("status") == "success":
            return self._format_from_tools(tool_results, sku_id or "the SKU")
        else:
            return self._generic_response(last_user, sku_id)

    def _format_from_tools(self, data: dict, sku_id: str) -> str:
        """Format a response using actual tool computation results."""
        # Handle full reorder recommendation
        if "reorder_point" in data and "recommended_qty" in data:
            health = data.get("health_status", "UNKNOWN")
            reorder = data.get("reorder_needed", False)
            confidence = data.get("confidence_score", 0.8)

            lines = [
                f"**SUMMARY:** {'⚠ Reorder required' if reorder else '✅ Stock is adequate'} for {sku_id} ({data.get('sku_name','')}).",
                "",
                "**ANALYSIS:**",
                f"  • Current Stock   : {data.get('current_stock','N/A')} units",
                f"  • Reorder Point   : {data.get('reorder_point','N/A')} units",
                f"  • Safety Stock    : {data.get('safety_stock','N/A')} units",
                f"  • Health Status   : {health}",
                f"  • Supplier        : {data.get('supplier_name','N/A')} (lead time {data.get('lead_time_days','N/A')} days)",
                f"  • Reliability     : {data.get('reliability_score',0):.0%}",
                "",
                "**RECOMMENDATION:**",
            ]
            if reorder:
                lines += [
                    f"  Raise a purchase order for **{data.get('recommended_qty','N/A')} units** of {sku_id}.",
                    f"  EOQ: {data.get('eoq','N/A')} units | Estimated Value: ${data.get('order_value_usd',0):,.2f}",
                    f"  Approval required: **{data.get('approval_required','N/A').replace('_',' ').title()}**",
                ]
            else:
                lines.append(
                    f"  No immediate reorder needed. Monitor stock; next review in 7 days."
                )
            lines += [
                "",
                f"**CONFIDENCE:** {confidence:.0%}",
                "",
                "**NEXT STEPS:**",
                "  1. Review this recommendation with the Inventory Manager.",
                "  2. If approved, raise the purchase order through your ERP system.",
                "  3. Record delivery outcome in the system to improve future recommendations.",
            ]
            return "\n".join(lines)

        # Handle supplier performance
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

        # Generic data response
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
        # Safety refusal
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


# ════════════════════════════════════════════════════════════════════════════════
# LangChain LLM wrapper
# ════════════════════════════════════════════════════════════════════════════════
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
        """
        Call the LLM with a list of {role, content} dicts.
        Injects tool results into the last user message if provided.
        """
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


# ════════════════════════════════════════════════════════════════════════════════
# Factory
# ════════════════════════════════════════════════════════════════════════════════
def get_llm():
    """Return the appropriate LLM client based on configuration."""
    if is_openai_available() and LANGCHAIN_AVAILABLE:
        try:
            return LangChainLLM()
        except Exception as e:
            print(f"  ⚠ LangChain LLM init failed ({e}). Falling back to MockLLM.")
    return MockLLM()
