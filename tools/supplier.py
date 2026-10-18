"""
tools/supplier_tools.py
=======================
Self-defined tools for supplier lead-time management and feedback processing.
Feedback is RECORDED only — the agent never directly modifies purchase data.
"""

import math
import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_fb_df : pd.DataFrame | None = None
_sup_df: pd.DataFrame | None = None


def _load_feedback() -> pd.DataFrame:
    global _fb_df
    if _fb_df is None:
        path = _DATA_DIR / "supplier_feedback.csv"
        if not path.exists():
            # Create empty file
            pd.DataFrame(columns=[
                "feedback_id","supplier_id","sku_id","order_date",
                "expected_delivery","actual_delivery","delay_days",
                "delay_reason","status","recorded_by"
            ]).to_csv(path, index=False)
        _fb_df = pd.read_csv(path)
        for col in ["order_date", "expected_delivery", "actual_delivery"]:
            _fb_df[col] = pd.to_datetime(_fb_df[col], format="mixed", dayfirst=False)
    return _fb_df


def _load_suppliers() -> pd.DataFrame:
    global _sup_df
    if _sup_df is None:
        path = _DATA_DIR / "supplier_data.csv"
        if not path.exists():
            raise FileNotFoundError("supplier_data.csv not found. Run generate_sample_data.py")
        _sup_df = pd.read_csv(path)
    return _sup_df


def _save_suppliers(df: pd.DataFrame):
    df.to_csv(_DATA_DIR / "supplier_data.csv", index=False)


def reload_supplier_cache():
    global _fb_df, _sup_df
    _fb_df = None
    _sup_df = None


# ══════════════════════════════════════════════════════════════════════════════
# Tool 9 — get_supplier_lead_time
# ══════════════════════════════════════════════════════════════════════════════
def get_supplier_lead_time(sku_id: str) -> dict[str, Any]:
    """
    Return base and adjusted lead time plus reliability for a SKU's supplier.
    """
    sup_df = _load_suppliers()
    rows   = sup_df[sup_df["sku_id"] == sku_id]

    if rows.empty:
        return {"sku_id": sku_id, "status": "error",
                "message": f"No supplier mapped to SKU '{sku_id}'."}

    row = rows.iloc[0]
    base_lt     = int(row["base_lead_time_days"])
    adjusted_lt = int(row["adjusted_lead_time_days"])
    reliability = round(float(row["reliability_score"]), 2)

    return {
        "sku_id"                 : sku_id,
        "supplier_id"            : row["supplier_id"],
        "supplier_name"          : row["supplier_name"],
        "contact_email"          : "***@***.com",   # PII masked in output
        "base_lead_time_days"    : base_lt,
        "adjusted_lead_time_days": adjusted_lt,
        "lead_time_buffer_days"  : adjusted_lt - base_lt,
        "reliability_score"      : reliability,
        "min_order_qty"          : int(row["min_order_qty"]),
        "performance_flag"       : "watch" if reliability < 0.80 else "good",
        "status"                 : "success",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tool 10 — record_supplier_feedback
# ══════════════════════════════════════════════════════════════════════════════
def record_supplier_feedback(
    sku_id: str,
    order_date: str,
    expected_delivery: str,
    actual_delivery: str,
    delay_reason: str,
) -> dict[str, Any]:
    """
    Record a delivery event and update the supplier's adjusted lead time.

    SAFETY: This only WRITES a feedback record and updates lead-time parameters.
    It does NOT create purchase orders or modify inventory counts.
    """
    # Validate dates
    try:
        order_dt    = datetime.strptime(order_date, "%Y-%m-%d").date()
        expected_dt = datetime.strptime(expected_delivery, "%Y-%m-%d").date()
        actual_dt   = datetime.strptime(actual_delivery, "%Y-%m-%d").date()
    except ValueError as e:
        return {"sku_id": sku_id, "status": "error",
                "message": f"Invalid date format: {e}. Use YYYY-MM-DD."}

    if actual_dt < order_dt:
        return {"sku_id": sku_id, "status": "error",
                "message": "actual_delivery cannot be earlier than order_date."}

    delay_days = max(0, (actual_dt - expected_dt).days)
    delivery_status = "on_time" if delay_days == 0 else "delayed"

    # Lookup supplier
    sup_df = _load_suppliers()
    mask   = sup_df["sku_id"] == sku_id
    if not mask.any():
        return {"sku_id": sku_id, "status": "error",
                "message": f"No supplier for SKU '{sku_id}'."}

    supplier_id = sup_df.loc[mask, "supplier_id"].iloc[0]

    # Load feedback and append
    fb_df = _load_feedback()
    new_id = f"FB-{len(fb_df)+1:04d}"
    new_row = {
        "feedback_id"      : new_id,
        "supplier_id"      : supplier_id,
        "sku_id"           : sku_id,
        "order_date"       : order_date,
        "expected_delivery": expected_delivery,
        "actual_delivery"  : actual_delivery,
        "delay_days"       : delay_days,
        "delay_reason"     : delay_reason,
        "status"           : delivery_status,
        "recorded_by"      : "agent",
    }
    new_fb = pd.DataFrame([new_row])
    fb_df  = pd.concat([fb_df, new_fb], ignore_index=True)
    # Re-cast date columns after concat
    for col in ["order_date", "expected_delivery", "actual_delivery"]:
        fb_df[col] = pd.to_datetime(fb_df[col], format="mixed", dayfirst=False)
    fb_df.to_csv(_DATA_DIR / "supplier_feedback.csv", index=False)

    # ── Update adjusted lead time ─────────────────────────────────────────────
    # Use actual_delivery date as reference for 90-day window
    try:
        ref_date = actual_dt
    except Exception:
        ref_date = date.today()
    cutoff = ref_date - timedelta(days=90)
    recent = fb_df[
        (fb_df["supplier_id"] == supplier_id) &
        (pd.to_datetime(fb_df["order_date"]).dt.date >= cutoff)
    ]
    delay_count = int((recent["status"] == "delayed").sum())
    base_lt     = int(sup_df.loc[mask, "base_lead_time_days"].iloc[0])

    if delay_count >= 2:
        new_lt = math.ceil(base_lt * 1.25)
    else:
        new_lt = base_lt

    sup_df.loc[mask, "adjusted_lead_time_days"] = new_lt
    # Update reliability score (exponential moving average)
    old_reliability = float(sup_df.loc[mask, "reliability_score"].iloc[0])
    event_score     = 1.0 if delivery_status == "on_time" else 0.0
    new_reliability = round(0.9 * old_reliability + 0.1 * event_score, 3)
    sup_df.loc[mask, "reliability_score"] = new_reliability

    _save_suppliers(sup_df)
    global _sup_df, _fb_df
    _sup_df = sup_df
    _fb_df  = fb_df

    return {
        "feedback_id"           : new_id,
        "sku_id"                : sku_id,
        "supplier_id"           : supplier_id,
        "delay_days"            : delay_days,
        "delivery_status"       : delivery_status,
        "delay_reason"          : delay_reason,
        "delays_in_90_days"     : delay_count,
        "base_lead_time_days"   : base_lt,
        "new_adjusted_lead_time": new_lt,
        "lead_time_changed"     : new_lt != base_lt,
        "new_reliability_score" : new_reliability,
        "note"                  : "Feedback recorded. ROP will be recalculated on next replenishment check.",
        "status"                : "success",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tool 11 — analyze_supplier_performance
# ══════════════════════════════════════════════════════════════════════════════
def analyze_supplier_performance(
    supplier_id: str,
    lookback_days: int = 90
) -> dict[str, Any]:
    """
    Analyse delivery performance for a supplier over a given window.
    """
    fb_df  = _load_feedback()
    sup_df = _load_suppliers()

    sup_rows = sup_df[sup_df["supplier_id"] == supplier_id]
    if sup_rows.empty:
        return {"supplier_id": supplier_id, "status": "error",
                "message": f"Supplier '{supplier_id}' not found."}

    supplier_name = sup_rows["supplier_name"].iloc[0]
    # Use the latest date in the dataset as reference (handles demo data from past years)
    if fb_df.empty or (fb_df["supplier_id"] == supplier_id).sum() == 0:
        max_date = pd.Timestamp.now()
    else:
        max_date = fb_df[fb_df["supplier_id"] == supplier_id]["order_date"].max()
        if pd.isnull(max_date):
            max_date = pd.Timestamp.now()
    cutoff        = max_date - pd.Timedelta(days=lookback_days)
    recent_fb     = fb_df[
        (fb_df["supplier_id"] == supplier_id) &
        (fb_df["order_date"]  >= cutoff)
    ]

    if recent_fb.empty:
        return {
            "supplier_id"  : supplier_id,
            "supplier_name": supplier_name,
            "lookback_days": lookback_days,
            "total_orders" : 0,
            "message"      : "No delivery records in the analysis window.",
            "status"       : "warning",
        }

    total       = len(recent_fb)
    on_time     = int((recent_fb["status"] == "on_time").sum())
    delayed     = total - on_time
    on_time_pct = round(on_time / total * 100, 1)
    avg_delay   = round(float(recent_fb[recent_fb["status"] == "delayed"]["delay_days"].mean() or 0), 1)
    max_delay   = int(recent_fb["delay_days"].max())

    base_lt     = int(sup_rows["base_lead_time_days"].iloc[0])
    current_lt  = int(sup_rows["adjusted_lead_time_days"].iloc[0])
    reliability = round(float(sup_rows["reliability_score"].iloc[0]), 2)

    recommended_lt_adjustment = math.ceil(base_lt * 1.25) if delayed >= 2 else base_lt

    return {
        "supplier_id"              : supplier_id,
        "supplier_name"            : supplier_name,
        "lookback_days"            : lookback_days,
        "total_orders"             : total,
        "on_time_count"            : on_time,
        "delayed_count"            : delayed,
        "on_time_pct"              : on_time_pct,
        "avg_delay_days"           : avg_delay,
        "max_delay_days"           : max_delay,
        "current_reliability_score": reliability,
        "base_lead_time_days"      : base_lt,
        "current_adjusted_lt"      : current_lt,
        "recommended_adjusted_lt"  : recommended_lt_adjustment,
        "action"                   : (
            "Place on Performance Improvement Plan" if reliability < 0.80
            else ("Monitor closely" if delayed >= 2 else "No action required")
        ),
        "status"                   : "success",
    }
