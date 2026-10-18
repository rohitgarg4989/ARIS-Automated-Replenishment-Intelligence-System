"""
tools/schemas.py
================
JSON Schema definitions for all agent tools.
Each schema follows the OpenAI function-calling specification so the same
definitions work with LangChain, raw OpenAI API, and the MockLLM dispatcher.
"""

# ════════════════════════════════════════════════════════════════════════════════
# SALES ANALYSIS TOOLS
# ════════════════════════════════════════════════════════════════════════════════

ANALYZE_SALES_VELOCITY_SCHEMA = {
    "name": "analyze_sales_velocity",
    "description": (
        "Compute the average daily sales velocity and demand variability "
        "(standard deviation) for a given SKU over a specified look-back window. "
        "Returns avg_daily_demand, std_daily_demand, total_units_sold, days_analyzed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sku_id": {
                "type": "string",
                "description": "SKU identifier (e.g. 'SKU-001')."
            },
            "lookback_days": {
                "type": "integer",
                "description": "Number of past calendar days to analyse. Default 30.",
                "default": 30,
                "minimum": 7,
                "maximum": 365
            }
        },
        "required": ["sku_id"]
    }
}

FORECAST_DEMAND_SCHEMA = {
    "name": "forecast_demand",
    "description": (
        "Forecast future demand for a SKU using a simple moving-average model. "
        "Returns forecasted daily demand, trend direction, and a confidence score."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sku_id": {
                "type": "string",
                "description": "SKU identifier."
            },
            "forecast_days": {
                "type": "integer",
                "description": "Number of days to forecast ahead. Default 30.",
                "default": 30,
                "minimum": 1,
                "maximum": 90
            }
        },
        "required": ["sku_id"]
    }
}

DETECT_DEMAND_SPIKE_SCHEMA = {
    "name": "detect_demand_spike",
    "description": (
        "Detect whether current demand (last 7 days) significantly exceeds "
        "the rolling 30-day baseline. Returns spike_detected (bool), spike_factor, "
        "and a recommended buffer_pct to add to order quantities."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sku_id": {
                "type": "string",
                "description": "SKU identifier."
            }
        },
        "required": ["sku_id"]
    }
}

# ════════════════════════════════════════════════════════════════════════════════
# INVENTORY PLANNING TOOLS
# ════════════════════════════════════════════════════════════════════════════════

GET_INVENTORY_STATUS_SCHEMA = {
    "name": "get_inventory_status",
    "description": (
        "Retrieve current inventory details for a SKU: current stock, reorder "
        "point, safety stock, max stock, and whether a reorder is needed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sku_id": {
                "type": "string",
                "description": "SKU identifier."
            }
        },
        "required": ["sku_id"]
    }
}

CALCULATE_SAFETY_STOCK_SCHEMA = {
    "name": "calculate_safety_stock",
    "description": (
        "Calculate the recommended safety stock using the formula: "
        "SS = Z × σ_d × √L, where Z is the service-level z-score, "
        "σ_d is the standard deviation of daily demand, and L is lead time in days."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sku_id": {
                "type": "string",
                "description": "SKU identifier."
            },
            "service_level": {
                "type": "number",
                "description": "Desired service level (0.90–0.99). Default 0.95.",
                "default": 0.95,
                "minimum": 0.80,
                "maximum": 0.99
            },
            "lead_time_days": {
                "type": "integer",
                "description": "Supplier lead time in days (overrides stored value if provided)."
            }
        },
        "required": ["sku_id"]
    }
}

CALCULATE_ROP_SCHEMA = {
    "name": "calculate_rop",
    "description": (
        "Calculate the Reorder Point (ROP) for a SKU using: "
        "ROP = (Avg Daily Demand × Lead Time) + Safety Stock."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sku_id": {
                "type": "string",
                "description": "SKU identifier."
            },
            "lead_time_days": {
                "type": "integer",
                "description": "Lead time in days. If omitted, uses the supplier's adjusted lead time."
            },
            "service_level": {
                "type": "number",
                "description": "Service level for safety stock calculation. Default 0.95.",
                "default": 0.95
            }
        },
        "required": ["sku_id"]
    }
}

CALCULATE_EOQ_SCHEMA = {
    "name": "calculate_eoq",
    "description": (
        "Calculate the Economic Order Quantity (EOQ) for a SKU using: "
        "EOQ = √(2 × D × S / H), where D=annual demand, S=ordering cost, "
        "H=holding cost per unit per year."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sku_id": {
                "type": "string",
                "description": "SKU identifier."
            },
            "ordering_cost": {
                "type": "number",
                "description": "Fixed cost per order in $. Overrides stored value if provided."
            },
            "holding_cost_pct": {
                "type": "number",
                "description": "Annual holding cost as fraction of unit cost. Default 0.20."
            }
        },
        "required": ["sku_id"]
    }
}

GENERATE_REORDER_RECOMMENDATION_SCHEMA = {
    "name": "generate_reorder_recommendation",
    "description": (
        "Generate a full stock replenishment recommendation for one or all SKUs. "
        "Combines ROP, EOQ, safety stock, supplier lead time, and demand forecast. "
        "Returns a structured recommendation with confidence score and reasoning."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sku_id": {
                "type": "string",
                "description": "SKU identifier. Pass 'ALL' to check every SKU."
            },
            "include_reasoning": {
                "type": "boolean",
                "description": "Include detailed step-by-step reasoning. Default true.",
                "default": True
            }
        },
        "required": ["sku_id"]
    }
}

# ════════════════════════════════════════════════════════════════════════════════
# SUPPLIER TOOLS
# ════════════════════════════════════════════════════════════════════════════════

GET_SUPPLIER_LEAD_TIME_SCHEMA = {
    "name": "get_supplier_lead_time",
    "description": (
        "Return both the base and adjusted lead time (in days) for the supplier "
        "of a given SKU, along with the supplier's current reliability score."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sku_id": {
                "type": "string",
                "description": "SKU identifier."
            }
        },
        "required": ["sku_id"]
    }
}

RECORD_SUPPLIER_FEEDBACK_SCHEMA = {
    "name": "record_supplier_feedback",
    "description": (
        "Record a supplier delivery event (on-time or delayed). "
        "This ONLY creates a feedback record — it does NOT modify inventory or "
        "place orders. Returns the new adjusted lead time after update."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sku_id": {
                "type": "string",
                "description": "SKU identifier."
            },
            "order_date": {
                "type": "string",
                "description": "Order placement date (YYYY-MM-DD)."
            },
            "expected_delivery": {
                "type": "string",
                "description": "Originally promised delivery date (YYYY-MM-DD)."
            },
            "actual_delivery": {
                "type": "string",
                "description": "Actual delivery date received (YYYY-MM-DD)."
            },
            "delay_reason": {
                "type": "string",
                "description": "Reason for delay (or 'On time' if no delay).",
                "enum": [
                    "On time",
                    "Port congestion causing shipment hold",
                    "Supplier production backlog",
                    "Customs clearance delay",
                    "Weather disruption at origin warehouse",
                    "Raw material shortage at supplier facility",
                    "Other"
                ]
            }
        },
        "required": ["sku_id", "order_date", "expected_delivery", "actual_delivery", "delay_reason"]
    }
}

ANALYZE_SUPPLIER_PERFORMANCE_SCHEMA = {
    "name": "analyze_supplier_performance",
    "description": (
        "Analyse delivery performance for a supplier over a date range. "
        "Returns on-time rate, average delay, and a recommended lead-time adjustment."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "supplier_id": {
                "type": "string",
                "description": "Supplier identifier (e.g. 'SUP-A')."
            },
            "lookback_days": {
                "type": "integer",
                "description": "Days of history to analyse. Default 90.",
                "default": 90
            }
        },
        "required": ["supplier_id"]
    }
}

# ════════════════════════════════════════════════════════════════════════════════
# REGISTRY — used by the orchestrator for dynamic tool lookup
# ════════════════════════════════════════════════════════════════════════════════

ALL_TOOL_SCHEMAS = [
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
]

TOOL_NAMES = {s["name"] for s in ALL_TOOL_SCHEMAS}
