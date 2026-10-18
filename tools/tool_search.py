"""
tools/tool_search.py
=====================
Tool search and schema definitions for dynamic tool discovery.
Each schema follows the OpenAI function-calling specification.
"""

from tools.schemas import (
    ANALYZE_SALES_VELOCITY_SCHEMA,
    FORECAST_DEMAND_SCHEMA,
    DETECT_DEMAND_SPIKE_SCHEMA,
    GET_INVENTORY_STATUS_SCHEMA,
    CALCULATE_SAFETY_STOCK_SCHEMA,
    CALCULATE_ROP_SCHEMA,
    CALCULATE_EOQ_SCHEMA,
    GENERATE_REORDER_RECOMMENDATION_SCHEMA,
    GET_SUPPLIER_LEAD_TIME_SCHEMA,
    RECORD_SUPPLIER_FEEDBACK_SCHEMA,
    ANALYZE_SUPPLIER_PERFORMANCE_SCHEMA,
    ALL_TOOL_SCHEMAS,
    TOOL_NAMES,
)


def search_tools(query: str) -> list[dict]:
    """
    Search for tools matching a natural language query.
    Returns matching tool schemas ranked by relevance.
    """
    q_lower = query.lower()
    results = []

    keyword_map = {
        "sales": ["analyze_sales_velocity", "forecast_demand", "detect_demand_spike"],
        "demand": ["analyze_sales_velocity", "forecast_demand", "detect_demand_spike"],
        "forecast": ["forecast_demand"],
        "spike": ["detect_demand_spike"],
        "velocity": ["analyze_sales_velocity"],
        "inventory": ["get_inventory_status", "calculate_safety_stock", "calculate_rop",
                       "calculate_eoq", "generate_reorder_recommendation"],
        "stock": ["get_inventory_status", "calculate_safety_stock", "generate_reorder_recommendation"],
        "safety": ["calculate_safety_stock"],
        "reorder": ["calculate_rop", "generate_reorder_recommendation"],
        "rop": ["calculate_rop"],
        "eoq": ["calculate_eoq"],
        "supplier": ["get_supplier_lead_time", "record_supplier_feedback",
                      "analyze_supplier_performance"],
        "lead time": ["get_supplier_lead_time"],
        "feedback": ["record_supplier_feedback"],
        "performance": ["analyze_supplier_performance"],
        "delay": ["record_supplier_feedback", "analyze_supplier_performance"],
    }

    matched_names = set()
    for keyword, tool_names in keyword_map.items():
        if keyword in q_lower:
            matched_names.update(tool_names)

    for schema in ALL_TOOL_SCHEMAS:
        if schema["name"] in matched_names:
            results.append(schema)

    # If no keyword match, return all schemas
    if not results:
        results = list(ALL_TOOL_SCHEMAS)

    return results


def get_tool_schema(tool_name: str) -> dict | None:
    """Get the schema for a specific tool by name."""
    for schema in ALL_TOOL_SCHEMAS:
        if schema["name"] == tool_name:
            return schema
    return None
