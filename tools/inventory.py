"""
tools/inventory_tools.py
========================
Self-defined tools for ROP, EOQ, safety stock, and reorder recommendations.
All formulas implemented according to inventory management best practices.
"""

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from tools.sales import analyze_sales_velocity, forecast_demand, detect_demand_spike

# ── Data loading ──────────────────────────────────────────────────────────────
_DATA_DIR   = Path(__file__).resolve().parent.parent / "data"
_inv_df : pd.DataFrame | None = None
_sup_df : pd.DataFrame | None = None


def _load_inventory() -> pd.DataFrame:
    global _inv_df
    if _inv_df is None:
        path = _DATA_DIR / "inventory_data.csv"
        if not path.exists():
            raise FileNotFoundError("inventory_data.csv not found. Run generate_sample_data.py")
        _inv_df = pd.read_csv(path)
    return _inv_df


def _load_suppliers() -> pd.DataFrame:
    global _sup_df
    if _sup_df is None:
        path = _DATA_DIR / "supplier_data.csv"
        if not path.exists():
            raise FileNotFoundError("supplier_data.csv not found. Run generate_sample_data.py")
        _sup_df = pd.read_csv(path)
    return _sup_df


def reload_inventory():
    global _inv_df, _sup_df
    _inv_df = None
    _sup_df = None


def _service_level_to_z(service_level: float) -> float:
    """Convert service level probability to z-score."""
    return round(float(stats.norm.ppf(service_level)), 3)


def _get_sku_row(sku_id: str) -> pd.Series | None:
    df = _load_inventory()
    rows = df[df["sku_id"] == sku_id]
    return rows.iloc[0] if not rows.empty else None


def _get_supplier_row(sku_id: str) -> pd.Series | None:
    df = _load_suppliers()
    rows = df[df["sku_id"] == sku_id]
    return rows.iloc[0] if not rows.empty else None


# ══════════════════════════════════════════════════════════════════════════════
# Tool 4 — get_inventory_status
# ══════════════════════════════════════════════════════════════════════════════
def get_inventory_status(sku_id: str) -> dict[str, Any]:
    """
    Return current inventory snapshot for a SKU.
    Includes reorder trigger flag and stock health classification.
    """
    row = _get_sku_row(sku_id)
    if row is None:
        return {"sku_id": sku_id, "status": "error",
                "message": f"SKU '{sku_id}' not found in inventory."}

    current       = int(row["current_stock"])
    safety_stock  = int(row["safety_stock"])
    rop           = int(row["reorder_point"])
    max_stock     = int(row["max_stock"])

    if current == 0:
        health = "STOCKOUT"
    elif current <= safety_stock:
        health = "CRITICAL"
    elif current <= rop:
        health = "REORDER_NEEDED"
    elif current >= max_stock * 0.90:
        health = "OVERSTOCKED"
    else:
        health = "HEALTHY"

    return {
        "sku_id"        : sku_id,
        "sku_name"      : row["sku_name"],
        "category"      : row["category"],
        "current_stock" : current,
        "safety_stock"  : safety_stock,
        "reorder_point" : rop,
        "max_stock"     : max_stock,
        "unit_cost"     : float(row["unit_cost"]),
        "stock_value"   : round(current * float(row["unit_cost"]), 2),
        "reorder_needed": current <= rop,
        "health_status" : health,
        "supplier_id"   : row["supplier_id"],
        "status"        : "success",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tool 5 — calculate_safety_stock
# ══════════════════════════════════════════════════════════════════════════════
def calculate_safety_stock(
    sku_id: str,
    service_level: float = 0.95,
    lead_time_days: int | None = None
) -> dict[str, Any]:
    """
    Safety Stock = Z × σ_d × √L
    """
    # Get demand stats
    velocity = analyze_sales_velocity(sku_id, lookback_days=30)
    if velocity["status"] == "error":
        return {**velocity, "tool": "calculate_safety_stock"}

    std_d = float(velocity["std_daily_demand"])

    # Get lead time
    if lead_time_days is None:
        sup = _get_supplier_row(sku_id)
        if sup is None:
            return {"sku_id": sku_id, "status": "error",
                    "message": f"No supplier found for '{sku_id}'."}
        lead_time_days = int(sup["adjusted_lead_time_days"])

    z = _service_level_to_z(service_level)
    safety_stock = math.ceil(z * std_d * math.sqrt(lead_time_days))

    return {
        "sku_id"          : sku_id,
        "service_level"   : service_level,
        "z_score"         : z,
        "std_daily_demand": std_d,
        "lead_time_days"  : lead_time_days,
        "safety_stock"    : safety_stock,
        "formula"         : f"SS = {z} × {std_d:.2f} × √{lead_time_days} = {safety_stock}",
        "status"          : "success",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tool 6 — calculate_rop
# ══════════════════════════════════════════════════════════════════════════════
def calculate_rop(
    sku_id: str,
    lead_time_days: int | None = None,
    service_level: float = 0.95
) -> dict[str, Any]:
    """
    Reorder Point = (Avg Daily Demand × Lead Time) + Safety Stock
    """
    # Demand velocity
    velocity = analyze_sales_velocity(sku_id, lookback_days=30)
    if velocity["status"] == "error":
        return {**velocity, "tool": "calculate_rop"}

    avg_d = float(velocity["avg_daily_demand"])

    # Lead time
    if lead_time_days is None:
        sup = _get_supplier_row(sku_id)
        if sup is None:
            return {"sku_id": sku_id, "status": "error",
                    "message": f"No supplier found for '{sku_id}'."}
        lead_time_days = int(sup["adjusted_lead_time_days"])

    # Safety stock
    ss_result = calculate_safety_stock(sku_id, service_level, lead_time_days)
    if ss_result["status"] == "error":
        return ss_result
    safety_stock = ss_result["safety_stock"]

    lead_time_demand = round(avg_d * lead_time_days, 1)
    rop = math.ceil(lead_time_demand + safety_stock)

    return {
        "sku_id"             : sku_id,
        "avg_daily_demand"   : avg_d,
        "lead_time_days"     : lead_time_days,
        "lead_time_demand"   : lead_time_demand,
        "safety_stock"       : safety_stock,
        "reorder_point"      : rop,
        "service_level"      : service_level,
        "formula"            : f"ROP = ({avg_d:.2f} × {lead_time_days}) + {safety_stock} = {rop}",
        "status"             : "success",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tool 7 — calculate_eoq
# ══════════════════════════════════════════════════════════════════════════════
def calculate_eoq(
    sku_id: str,
    ordering_cost: float | None = None,
    holding_cost_pct: float | None = None
) -> dict[str, Any]:
    """
    EOQ = √(2 × D × S / H)
    D = Annual demand, S = ordering cost, H = annual holding cost per unit
    """
    inv_row = _get_sku_row(sku_id)
    if inv_row is None:
        return {"sku_id": sku_id, "status": "error",
                "message": f"SKU '{sku_id}' not in inventory."}

    # Demand (annualised from 30-day velocity)
    velocity = analyze_sales_velocity(sku_id, lookback_days=30)
    if velocity["status"] == "error":
        return {**velocity, "tool": "calculate_eoq"}

    avg_d  = float(velocity["avg_daily_demand"])
    D      = avg_d * 250   # working days per year

    S      = ordering_cost   if ordering_cost   is not None else float(inv_row["ordering_cost"])
    hcp    = holding_cost_pct if holding_cost_pct is not None else float(inv_row["holding_cost_pct"])
    H      = float(inv_row["unit_cost"]) * hcp

    if H <= 0:
        return {"sku_id": sku_id, "status": "error",
                "message": "Holding cost is zero; EOQ is undefined."}

    eoq = math.ceil(math.sqrt((2 * D * S) / H))

    # Check against MOQ
    sup = _get_supplier_row(sku_id)
    moq = int(sup["min_order_qty"]) if sup is not None else 1
    order_qty = max(eoq, moq)

    return {
        "sku_id"             : sku_id,
        "annual_demand_D"    : round(D, 1),
        "ordering_cost_S"    : S,
        "holding_cost_H"     : round(H, 4),
        "eoq"                : eoq,
        "min_order_qty"      : moq,
        "recommended_qty"    : order_qty,
        "moq_applied"        : order_qty > eoq,
        "formula"            : f"EOQ = √(2 × {D:.0f} × {S} / {H:.2f}) = {eoq}",
        "status"             : "success",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tool 8 — generate_reorder_recommendation
# ══════════════════════════════════════════════════════════════════════════════
def generate_reorder_recommendation(
    sku_id: str,
    include_reasoning: bool = True
) -> dict[str, Any]:
    """
    Full replenishment recommendation combining all tools.
    Returns structured recommendation with confidence score.
    """
    if sku_id.upper() == "ALL":
        inv = _load_inventory()
        results = []
        for sid in inv["sku_id"].tolist():
            r = generate_reorder_recommendation(sid, include_reasoning=False)
            if r.get("reorder_needed"):
                results.append(r)
        return {
            "query"            : "ALL SKUs requiring reorder",
            "total_skus_checked": len(inv),
            "skus_needing_reorder": len(results),
            "recommendations"  : results,
            "status"           : "success",
        }

    # ── Step 1: Inventory status ──────────────────────────────────────────────
    inv_status = get_inventory_status(sku_id)
    if inv_status["status"] == "error":
        return {**inv_status, "tool": "generate_reorder_recommendation"}

    # ── Step 2: Supplier lead time ────────────────────────────────────────────
    sup = _get_supplier_row(sku_id)
    if sup is None:
        return {"sku_id": sku_id, "status": "error",
                "message": "No supplier data found."}

    lead_time = int(sup["adjusted_lead_time_days"])
    reliability = float(sup["reliability_score"])

    # ── Step 3: ROP & EOQ ─────────────────────────────────────────────────────
    rop_result = calculate_rop(sku_id, lead_time)
    eoq_result = calculate_eoq(sku_id)
    spike_result = detect_demand_spike(sku_id)

    if rop_result["status"] == "error" or eoq_result["status"] == "error":
        return {"sku_id": sku_id, "status": "error",
                "message": "Could not complete ROP or EOQ calculation."}

    # ── Step 4: Order quantity with spike buffer ───────────────────────────────
    base_qty   = eoq_result["recommended_qty"]
    buffer_pct = spike_result.get("buffer_pct", 0)
    final_qty  = math.ceil(base_qty * (1 + buffer_pct / 100))

    # ── Step 5: Confidence score ───────────────────────────────────────────────
    confidence = 0.90
    if reliability < 0.80:
        confidence -= 0.15
    if spike_result.get("spike_detected"):
        confidence -= 0.10
    if lead_time != int(sup["base_lead_time_days"]):
        confidence -= 0.05   # adjusted lead time indicates past delays

    confidence = round(max(0.30, min(1.0, confidence)), 2)

    # ── Step 6: Order value for approval routing ───────────────────────────────
    unit_cost   = inv_status["unit_cost"]
    order_value = round(final_qty * unit_cost, 2)

    approval_level = (
        "auto_approved"           if order_value < 5_000  else
        "inventory_manager"       if order_value <= 50_000 else
        "cfo_sign_off"
    )

    reasoning = []
    if include_reasoning:
        reasoning = [
            f"Current Stock: {inv_status['current_stock']} units",
            f"Reorder Point: {rop_result['reorder_point']} units "
            f"(Lead Time Demand {rop_result['lead_time_demand']} + Safety Stock {rop_result['safety_stock']})",
            f"EOQ: {eoq_result['eoq']} units (MOQ applied: {eoq_result['moq_applied']})",
            f"Demand Spike Detected: {spike_result.get('spike_detected', False)} "
            f"(buffer +{buffer_pct}%)",
            f"Supplier Reliability: {reliability:.0%}",
            f"Lead Time: {lead_time} days "
            f"(base: {int(sup['base_lead_time_days'])} days)",
            f"Confidence Score: {confidence:.0%}",
            f"Order Value: ${order_value:,.2f} → Approval: {approval_level}",
        ]

    return {
        "sku_id"            : sku_id,
        "sku_name"          : inv_status["sku_name"],
        "current_stock"     : inv_status["current_stock"],
        "reorder_point"     : rop_result["reorder_point"],
        "reorder_needed"    : inv_status["reorder_needed"],
        "health_status"     : inv_status["health_status"],
        "recommended_qty"   : final_qty,
        "eoq"               : eoq_result["eoq"],
        "safety_stock"      : rop_result["safety_stock"],
        "supplier_id"       : sup["supplier_id"],
        "supplier_name"     : sup["supplier_name"],
        "lead_time_days"    : lead_time,
        "reliability_score" : reliability,
        "order_value_usd"   : order_value,
        "approval_required" : approval_level,
        "confidence_score"  : confidence,
        "spike_detected"    : spike_result.get("spike_detected", False),
        "reasoning"         : reasoning,
        "status"            : "success",
    }
