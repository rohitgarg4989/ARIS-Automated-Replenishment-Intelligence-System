# ARIS — Skill Definition

## Skill: Stock Replenishment Analysis

### Description
ARIS (Automated Replenishment Intelligence System) analyses inventory data, computes optimal reorder points and quantities, evaluates supplier performance, and generates purchase order recommendations.

### Capabilities
- Calculate Reorder Points (ROP) using demand analysis and lead times
- Compute Economic Order Quantity (EOQ) for cost optimization
- Determine Safety Stock levels based on service level targets
- Analyse sales velocity and detect demand spikes
- Track supplier lead times and delivery performance
- Record supplier feedback and adjust parameters
- Generate full replenishment recommendations with confidence scores
- Enforce safety guardrails and HITL escalation

### Tools
1. `analyze_sales_velocity` — Daily demand statistics
2. `forecast_demand` — Weighted moving average forecasting
3. `detect_demand_spike` — Spike detection with buffer recommendations
4. `get_inventory_status` — Current stock health assessment
5. `calculate_safety_stock` — Z-score based buffer calculation
6. `calculate_rop` — Reorder point computation
7. `calculate_eoq` — Economic order quantity optimization
8. `generate_reorder_recommendation` — Full recommendation with reasoning
9. `get_supplier_lead_time` — Base and adjusted lead times
10. `record_supplier_feedback` — Delivery event recording
11. `analyze_supplier_performance` — Supplier scorecard analysis

### Input
Natural language queries about inventory, suppliers, or reorder decisions.

### Output
Structured recommendations with SUMMARY, ANALYSIS, RECOMMENDATION, CONFIDENCE, and NEXT STEPS.
