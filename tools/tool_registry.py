"""
tools/tool_registry.py
=======================
Unified tool registry — maps tool names to their Python implementations.
Used by the orchestrator to dispatch tool calls.
"""

from tools.sales import (
    analyze_sales_velocity,
    forecast_demand,
    detect_demand_spike,
)
from tools.inventory import (
    get_inventory_status,
    calculate_safety_stock,
    calculate_rop,
    calculate_eoq,
    generate_reorder_recommendation,
)
from tools.supplier import (
    get_supplier_lead_time,
    record_supplier_feedback,
    analyze_supplier_performance,
)

# ── Tool dispatcher ───────────────────────────────────────────────────────────
TOOL_REGISTRY: dict = {
    "analyze_sales_velocity"        : analyze_sales_velocity,
    "forecast_demand"               : forecast_demand,
    "detect_demand_spike"           : detect_demand_spike,
    "get_inventory_status"          : get_inventory_status,
    "calculate_safety_stock"        : calculate_safety_stock,
    "calculate_rop"                 : calculate_rop,
    "calculate_eoq"                 : calculate_eoq,
    "generate_reorder_recommendation": generate_reorder_recommendation,
    "get_supplier_lead_time"        : get_supplier_lead_time,
    "record_supplier_feedback"      : record_supplier_feedback,
    "analyze_supplier_performance"  : analyze_supplier_performance,
}


def execute_tool(tool_name: str, **kwargs) -> dict:
    """Dispatch a tool call by name with keyword arguments."""
    if tool_name not in TOOL_REGISTRY:
        return {
            "status" : "error",
            "message": f"Unknown tool '{tool_name}'. "
                       f"Available: {sorted(TOOL_REGISTRY.keys())}"
        }
    try:
        return TOOL_REGISTRY[tool_name](**kwargs)
    except TypeError as e:
        return {
            "status" : "error",
            "message": f"Invalid arguments for tool '{tool_name}': {e}"
        }
    except Exception as e:
        return {
            "status" : "error",
            "message": f"Tool '{tool_name}' raised an exception: {e}"
        }
