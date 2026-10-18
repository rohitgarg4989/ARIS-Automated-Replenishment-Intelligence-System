"""
tools/sales_tools.py
====================
Self-defined tools for sales analysis and demand forecasting.
All functions are pure Python (no LLM call) — they execute real computations.
"""

import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# ── Data loading helper ───────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_sales_df: pd.DataFrame | None = None


def _load_sales() -> pd.DataFrame:
    global _sales_df
    if _sales_df is None:
        path = _DATA_DIR / "sales_data.csv"
        if not path.exists():
            raise FileNotFoundError(
                "sales_data.csv not found. Run: python data/generate_sample_data.py"
            )
        _sales_df = pd.read_csv(path, parse_dates=["date"])
    return _sales_df


def reload_sales():
    """Force a fresh load from disk (used after data updates)."""
    global _sales_df
    _sales_df = None


# ══════════════════════════════════════════════════════════════════════════════
# Tool 1 — analyze_sales_velocity
# ══════════════════════════════════════════════════════════════════════════════
def analyze_sales_velocity(sku_id: str, lookback_days: int = 30) -> dict[str, Any]:
    """
    Compute average daily sales velocity and demand variability for a SKU.

    Returns
    -------
    dict with keys:
        sku_id, avg_daily_demand, std_daily_demand, max_daily_demand,
        min_daily_demand, total_units_sold, days_analyzed, status
    """
    df = _load_sales()
    sku_df = df[df["sku_id"] == sku_id].copy()

    if sku_df.empty:
        return {
            "sku_id": sku_id,
            "status": "error",
            "message": f"No sales records found for SKU '{sku_id}'."
        }

    cutoff = sku_df["date"].max() - timedelta(days=lookback_days)
    window = sku_df[sku_df["date"] >= cutoff]

    if window.empty:
        return {
            "sku_id": sku_id,
            "status": "error",
            "message": f"No sales in the last {lookback_days} days for '{sku_id}'."
        }

    daily = window.groupby("date")["units_sold"].sum()

    return {
        "sku_id"          : sku_id,
        "lookback_days"   : lookback_days,
        "avg_daily_demand": round(float(daily.mean()), 2),
        "std_daily_demand": round(float(daily.std(ddof=1)), 2),
        "max_daily_demand": int(daily.max()),
        "min_daily_demand": int(daily.min()),
        "total_units_sold": int(daily.sum()),
        "days_analyzed"   : len(daily),
        "status"          : "success",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tool 2 — forecast_demand
# ══════════════════════════════════════════════════════════════════════════════
def forecast_demand(sku_id: str, forecast_days: int = 30) -> dict[str, Any]:
    """
    Forecast future demand using a weighted moving average.
    Recent weeks are weighted higher (3-2-1 scheme).
    """
    df = _load_sales()
    sku_df = df[df["sku_id"] == sku_id].copy()

    if sku_df.empty:
        return {"sku_id": sku_id, "status": "error",
                "message": f"No data for '{sku_id}'."}

    daily = sku_df.groupby("date")["units_sold"].sum().sort_index()

    # Need at least 21 days for a 3-week weighted average
    if len(daily) < 21:
        # Fallback: simple mean
        avg = float(daily.mean())
        std = float(daily.std(ddof=1)) if len(daily) > 1 else avg * 0.2
        confidence = 0.60
        method = "simple_mean_fallback"
    else:
        w1 = float(daily.iloc[-7:].mean())     # last week  (weight 3)
        w2 = float(daily.iloc[-14:-7].mean())  # 2nd week  (weight 2)
        w3 = float(daily.iloc[-21:-14].mean()) # 3rd week  (weight 1)
        avg = (3 * w1 + 2 * w2 + 1 * w3) / 6
        std = float(daily.std(ddof=1))
        confidence = 0.80
        method = "weighted_moving_average"

    # Trend: compare last-7 vs prior-7
    if len(daily) >= 14:
        recent  = float(daily.iloc[-7:].mean())
        prior   = float(daily.iloc[-14:-7].mean())
        if prior > 0:
            trend_pct = round((recent - prior) / prior * 100, 1)
        else:
            trend_pct = 0.0
        trend = "increasing" if trend_pct > 5 else ("decreasing" if trend_pct < -5 else "stable")
    else:
        trend_pct = 0.0
        trend = "unknown"

    return {
        "sku_id"                : sku_id,
        "forecast_days"         : forecast_days,
        "forecasted_daily_demand": round(avg, 2),
        "demand_std"            : round(std, 2),
        "forecasted_total"      : round(avg * forecast_days, 0),
        "trend"                 : trend,
        "trend_pct"             : trend_pct,
        "confidence_score"      : confidence,
        "method"                : method,
        "status"                : "success",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tool 3 — detect_demand_spike
# ══════════════════════════════════════════════════════════════════════════════
def detect_demand_spike(sku_id: str) -> dict[str, Any]:
    """
    Detect whether recent demand (last 7 days) significantly exceeds
    the rolling 30-day baseline.

    Returns spike_detected, spike_factor, buffer_pct recommendation.
    """
    df = _load_sales()
    sku_df = df[df["sku_id"] == sku_id].copy()

    if sku_df.empty:
        return {"sku_id": sku_id, "status": "error",
                "message": f"No data for '{sku_id}'."}

    daily = sku_df.groupby("date")["units_sold"].sum().sort_index()

    if len(daily) < 7:
        return {
            "sku_id": sku_id,
            "spike_detected": False,
            "spike_factor": 1.0,
            "buffer_pct": 0,
            "message": "Insufficient data for spike detection (< 7 days).",
            "status": "warning",
        }

    recent_avg   = float(daily.iloc[-7:].mean())
    baseline_avg = float(daily.iloc[-30:].mean()) if len(daily) >= 30 else float(daily.mean())

    if baseline_avg > 0:
        spike_factor = round(recent_avg / baseline_avg, 2)
    else:
        spike_factor = 1.0

    spike_detected = spike_factor >= 1.50
    buffer_pct = 25 if spike_detected else 0

    return {
        "sku_id"        : sku_id,
        "recent_7d_avg" : round(recent_avg, 2),
        "baseline_30d_avg": round(baseline_avg, 2),
        "spike_factor"  : spike_factor,
        "spike_detected": spike_detected,
        "buffer_pct"    : buffer_pct,
        "recommendation": (
            f"Apply +{buffer_pct}% buffer to order quantity."
            if spike_detected else "No spike detected; standard order quantity applies."
        ),
        "status"        : "success",
    }
