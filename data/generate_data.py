"""
data/generate_sample_data.py
=============================
Generates realistic synthetic CSV datasets for the Stock Replenishment Agent.

Datasets created
────────────────
• sales_data.csv        – 180 days × 15 SKUs of daily sales
• inventory_data.csv    – Current stock levels + cost parameters
• supplier_data.csv     – Supplier catalogue with lead times
• supplier_feedback.csv – Historical delivery feedback (some delayed)

Run: python data/generate_sample_data.py
"""

import random
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date, timedelta

# ── Reproducibility ───────────────────────────────────────────────────────────
random.seed(42)
np.random.seed(42)

DATA_DIR = Path(__file__).parent

# ── Master catalogue ──────────────────────────────────────────────────────────
SKUS = [
    # sku_id, sku_name, category, unit_cost, avg_daily_demand, demand_std
    ("SKU-001", "Printer Paper A4 (500 sheets)", "Office Supplies",  3.50,  25, 5),
    ("SKU-002", "Ball-Point Pens (Box 50)",      "Office Supplies",  8.00,  12, 3),
    ("SKU-003", "Stapler Heavy Duty",            "Office Supplies", 22.00,   4, 1),
    ("SKU-004", "USB-C Cables (Pack 5)",         "Electronics",     15.00,  18, 6),
    ("SKU-005", "Wireless Mouse",                "Electronics",     25.00,   9, 3),
    ("SKU-006", "HDMI Cables 2m",               "Electronics",     10.00,  14, 4),
    ("SKU-007", "Laptop Stand Aluminium",        "Electronics",     45.00,   6, 2),
    ("SKU-008", "AA Batteries (Pack 20)",        "Electronics",      6.00,  30, 8),
    ("SKU-009", "Safety Gloves (Box 100)",       "Industrial",       9.00,  20, 5),
    ("SKU-010", "Face Masks (Box 50)",           "Industrial",      12.00,  40,10),
    ("SKU-011", "Safety Goggles",               "Industrial",       7.50,   8, 2),
    ("SKU-012", "Cable Ties 300mm (Pack 100)",  "Industrial",       4.00,  15, 4),
    ("SKU-013", "Padlock Heavy Duty",           "Industrial",      18.00,   5, 2),
    ("SKU-014", "Whiteboard Markers (Set 12)",  "Office Supplies",  9.00,  10, 3),
    ("SKU-015", "Sticky Notes 76x76 (12-pack)", "Office Supplies",  5.00,  22, 6),
]

SUPPLIERS = [
    # supplier_id, supplier_name, contact_email
    ("SUP-A", "OfficeWorld Distributors",  "orders@officeworld.com"),
    ("SUP-B", "TechParts Global Ltd",      "supply@techparts.com"),
    ("SUP-C", "Industrial SafetyPro",      "sales@safetypro.com"),
    ("SUP-D", "FastTrack Logistics",       "ops@fasttrack.com"),
    ("SUP-E", "PrimeLine Supply Co",       "replenish@primeline.com"),
]

# SKU → primary supplier mapping
SKU_SUPPLIER = {
    "SKU-001": "SUP-A", "SKU-002": "SUP-A", "SKU-003": "SUP-A",
    "SKU-014": "SUP-A", "SKU-015": "SUP-A",
    "SKU-004": "SUP-B", "SKU-005": "SUP-B", "SKU-006": "SUP-B",
    "SKU-007": "SUP-B", "SKU-008": "SUP-B",
    "SKU-009": "SUP-C", "SKU-010": "SUP-C", "SKU-011": "SUP-C",
    "SKU-012": "SUP-C", "SKU-013": "SUP-C",
}

# Base lead times per supplier (days)
SUPPLIER_LEAD_TIMES = {
    "SUP-A": 7,
    "SUP-B": 10,
    "SUP-C": 5,
    "SUP-D": 3,
    "SUP-E": 14,
}

# Minimum order quantities per supplier-SKU
MIN_ORDER_QTY = {
    "SKU-001": 100, "SKU-002": 50,  "SKU-003": 10,
    "SKU-004": 20,  "SKU-005": 10,  "SKU-006": 20,
    "SKU-007": 5,   "SKU-008": 50,  "SKU-009": 10,
    "SKU-010": 20,  "SKU-011": 10,  "SKU-012": 20,
    "SKU-013": 5,   "SKU-014": 10,  "SKU-015": 24,
}


# ══════════════════════════════════════════════════════════════════════════════
# 1. Sales Data
# ══════════════════════════════════════════════════════════════════════════════
def generate_sales_data() -> pd.DataFrame:
    start = date(2024, 1, 1)
    rows = []
    for day_offset in range(180):
        current_date = start + timedelta(days=day_offset)
        # Skip Sundays (simulate partial weekday-only ops)
        if current_date.weekday() == 6:
            continue
        for sku_id, sku_name, category, unit_cost, avg_demand, std_demand in SKUS:
            # Add mild seasonality (higher in spring / mid-year)
            season_factor = 1.0 + 0.15 * np.sin(2 * np.pi * day_offset / 90)
            units = max(0, int(np.random.normal(avg_demand * season_factor, std_demand)))
            rows.append({
                "date"        : current_date.isoformat(),
                "sku_id"      : sku_id,
                "sku_name"    : sku_name,
                "category"    : category,
                "units_sold"  : units,
                "unit_price"  : round(unit_cost * 1.40, 2),   # 40% margin
                "warehouse_id": "WH-01",
            })

    df = pd.DataFrame(rows)
    df.to_csv(DATA_DIR / "sales_data.csv", index=False)
    print(f"  ✔ sales_data.csv          ({len(df):,} rows)")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 2. Inventory Data
# ══════════════════════════════════════════════════════════════════════════════
def generate_inventory_data() -> pd.DataFrame:
    rows = []
    for sku_id, sku_name, category, unit_cost, avg_demand, std_demand in SKUS:
        supplier_id  = SKU_SUPPLIER[sku_id]
        lead_time    = SUPPLIER_LEAD_TIMES[supplier_id]
        safety_stock = int(1.65 * std_demand * np.sqrt(lead_time))
        rop          = int(avg_demand * lead_time + safety_stock)
        current_stock = random.randint(
            max(0, rop - int(avg_demand * 5)),
            rop + int(avg_demand * 20)
        )
        rows.append({
            "sku_id"          : sku_id,
            "sku_name"        : sku_name,
            "category"        : category,
            "current_stock"   : current_stock,
            "safety_stock"    : safety_stock,
            "reorder_point"   : rop,
            "max_stock"       : rop + int(avg_demand * 30),
            "unit_cost"       : unit_cost,
            "ordering_cost"   : 50.00,          # fixed ordering cost $
            "holding_cost_pct": 0.20,            # 20% per year
            "supplier_id"     : supplier_id,
            "warehouse_id"    : "WH-01",
        })

    df = pd.DataFrame(rows)
    df.to_csv(DATA_DIR / "inventory_data.csv", index=False)
    print(f"  ✔ inventory_data.csv      ({len(df)} rows)")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 3. Supplier Data
# ══════════════════════════════════════════════════════════════════════════════
def generate_supplier_data() -> pd.DataFrame:
    rows = []
    for sku_id, sku_name, category, unit_cost, _, _ in SKUS:
        supplier_id   = SKU_SUPPLIER[sku_id]
        sup_name      = next(s[1] for s in SUPPLIERS if s[0] == supplier_id)
        sup_email     = next(s[2] for s in SUPPLIERS if s[0] == supplier_id)
        lead_time     = SUPPLIER_LEAD_TIMES[supplier_id]
        # Reliability: occasional suppliers are less reliable
        reliability   = round(random.uniform(0.75, 0.98), 2)
        rows.append({
            "supplier_id"          : supplier_id,
            "supplier_name"        : sup_name,
            "contact_email"        : sup_email,
            "sku_id"               : sku_id,
            "sku_name"             : sku_name,
            "base_lead_time_days"  : lead_time,
            "adjusted_lead_time_days": lead_time,   # updated by feedback
            "min_order_qty"        : MIN_ORDER_QTY[sku_id],
            "reliability_score"    : reliability,
            "payment_terms_days"   : 30,
            "active"               : True,
        })

    df = pd.DataFrame(rows)
    df.to_csv(DATA_DIR / "supplier_data.csv", index=False)
    print(f"  ✔ supplier_data.csv       ({len(df)} rows)")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 4. Supplier Feedback (delivery performance)
# ══════════════════════════════════════════════════════════════════════════════
def generate_supplier_feedback() -> pd.DataFrame:
    start = date(2024, 1, 1)
    rows = []
    feedback_id = 1

    # Generate ~40 feedback records across 6 months
    for _ in range(40):
        sku_id      = random.choice([s[0] for s in SKUS])
        supplier_id = SKU_SUPPLIER[sku_id]
        lead_time   = SUPPLIER_LEAD_TIMES[supplier_id]

        order_date     = start + timedelta(days=random.randint(0, 150))
        expected_date  = order_date + timedelta(days=lead_time)

        # 30% chance of delay; delays range 1–10 days
        if random.random() < 0.30:
            delay_days    = random.randint(1, 10)
            actual_date   = expected_date + timedelta(days=delay_days)
            reason_choices = [
                "Port congestion causing shipment hold",
                "Supplier production backlog",
                "Customs clearance delay",
                "Weather disruption at origin warehouse",
                "Raw material shortage at supplier facility",
            ]
            reason = random.choice(reason_choices)
            status = "delayed"
        else:
            delay_days  = 0
            actual_date = expected_date - timedelta(days=random.randint(0, 1))
            reason      = "On time"
            status      = "on_time"

        rows.append({
            "feedback_id"      : f"FB-{feedback_id:04d}",
            "supplier_id"      : supplier_id,
            "sku_id"           : sku_id,
            "order_date"       : order_date.isoformat(),
            "expected_delivery": expected_date.isoformat(),
            "actual_delivery"  : actual_date.isoformat(),
            "delay_days"       : delay_days,
            "delay_reason"     : reason,
            "status"           : status,
            "recorded_by"      : "system",
        })
        feedback_id += 1

    df = pd.DataFrame(rows)
    df.sort_values("order_date", inplace=True)
    df.to_csv(DATA_DIR / "supplier_feedback.csv", index=False)
    print(f"  ✔ supplier_feedback.csv   ({len(df)} rows)")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 5. Knowledge-base documents (for RAG)
# ══════════════════════════════════════════════════════════════════════════════
def create_knowledge_base():
    kb_dir = DATA_DIR / "knowledge_base"
    kb_dir.mkdir(exist_ok=True)

    # Document 1 – Inventory Policy
    (kb_dir / "inventory_policy.txt").write_text("""
INVENTORY MANAGEMENT POLICY — WH-01
=====================================

1. REORDER POINT (ROP)
   ROP = (Average Daily Usage × Lead Time Days) + Safety Stock
   All purchase orders MUST be raised when stock hits or drops below ROP.

2. SAFETY STOCK
   Safety Stock = Z × σ_d × √L
   Where:
     Z    = Service-level z-score  (95% SL → Z = 1.65)
     σ_d  = Standard deviation of daily demand
     L    = Supplier lead time in days
   Default service level: 95%

3. ECONOMIC ORDER QUANTITY (EOQ)
   EOQ = √(2 × D × S / H)
   Where:
     D = Annual demand (units)
     S = Ordering cost per order ($50 default)
     H = Annual holding cost per unit (unit_cost × 0.20)
   EOQ is the recommended order quantity unless MOQ is higher.

4. MAXIMUM STOCK LEVEL
   Max Stock = ROP + EOQ × 1.5
   Stock must not exceed Max Stock to prevent over-capitalisation.

5. STOCKOUT PROTOCOL
   If current_stock < safety_stock, escalate immediately to Inventory Manager.
   Do NOT wait for the next review cycle.

6. ORDER APPROVAL LIMITS
   - Orders < $5,000  : Auto-approved by system
   - Orders $5,000–$50,000 : Requires Inventory Manager approval
   - Orders > $50,000 : Requires CFO sign-off

7. DATA RETENTION
   Sales data retained: 24 months
   Supplier feedback retained: 36 months
   PII fields (emails, names) must NOT appear in system logs.
""", encoding="utf-8")

    # Document 2 – Supplier Guidelines
    (kb_dir / "supplier_guidelines.txt").write_text("""
SUPPLIER ENGAGEMENT GUIDELINES
================================

1. PREFERRED SUPPLIER SELECTION
   Suppliers are ranked by: reliability_score DESC, lead_time_days ASC.
   Minimum acceptable reliability score: 0.75

2. LEAD TIME ADJUSTMENT POLICY
   If a supplier delays > 3 times in a 90-day window, their adjusted_lead_time
   is increased by 20% (rounded up to nearest day) to protect stock levels.
   The adjustment resets after 90 consecutive on-time deliveries.

3. FEEDBACK RECORDING
   Every delivery (on-time or delayed) MUST be recorded in supplier_feedback.csv.
   Delay reasons should be one of the standard categories:
     - Port congestion
     - Production backlog
     - Customs delay
     - Weather disruption
     - Raw material shortage
     - Other (with free-text note)

4. COMMUNICATION PROTOCOL
   For delays > 5 days: Notify Procurement Manager within 24 hours.
   For delays > 10 days: Trigger alternate supplier sourcing review.

5. SUPPLIER SCORECARD REVIEW
   Quarterly review of all supplier reliability scores.
   Suppliers with score < 0.80 are placed on a performance improvement plan.

6. MINIMUM ORDER QUANTITIES (MOQ)
   MOQ must be respected in all purchase orders.
   If EOQ < MOQ, order quantity = MOQ.

7. PAYMENT TERMS
   Standard: Net-30.
   Early payment discount available: 2% if paid within 10 days.
""", encoding="utf-8")

    # Document 3 – Replenishment Rules
    (kb_dir / "replenishment_rules.txt").write_text("""
STOCK REPLENISHMENT DECISION RULES
=====================================

RULE 1 — TRIGGER CONDITION
  Replenishment is triggered when:  current_stock ≤ reorder_point
  The agent must check all SKUs at least once per day.

RULE 2 — ORDER QUANTITY
  order_qty = max(EOQ, MOQ)
  Round up to the nearest MOQ multiple if EOQ is not a multiple of MOQ.

RULE 3 — SUPPLIER DELAY BUFFER
  If a supplier has had ≥ 2 delays in the last 60 days:
    adjusted_lead_time = base_lead_time × 1.25
    Recalculate ROP using adjusted_lead_time.

RULE 4 — DEMAND SPIKE HANDLING
  If last-7-day average demand > 1.5× rolling-30-day average:
    Apply a 25% buffer to the order quantity.
    Flag as "demand spike detected" in the recommendation.

RULE 5 — SAFETY STOCK REVIEW CYCLE
  Safety stock parameters are reviewed every 30 days.
  If σ_d changed by > 15%, recalculate safety stock and ROP.

RULE 6 — MULTI-SUPPLIER SOURCING
  If primary supplier reliability < 0.80, split order:
    70% primary supplier, 30% alternate (lowest lead time).

RULE 7 — ESCALATION TRIGGERS
  Always escalate to human analyst when:
    (a) Order value > $50,000
    (b) Confidence score < 0.60
    (c) Stock is already in stockout (current_stock = 0)
    (d) Demand forecast uncertainty > 30%

RULE 8 — SAFETY & COMPLIANCE
  The agent MUST NOT directly execute purchase orders.
  It generates recommendations only; humans approve and execute.
  All recommendations include a confidence score and reasoning chain.
""", encoding="utf-8")

    print(f"  ✔ knowledge_base/          (3 documents created)")


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n📦 Generating sample datasets …\n")
    generate_sales_data()
    generate_inventory_data()
    generate_supplier_data()
    generate_supplier_feedback()
    create_knowledge_base()
    print("\n✅ All datasets ready in ./data/\n")
