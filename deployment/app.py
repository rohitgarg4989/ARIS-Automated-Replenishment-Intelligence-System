"""
ARIS — Streamlit Web UI
========================
Full visual interface for the AI Stock Replenishment Agent.

Run: streamlit run deployment/app.py
"""

import sys
from pathlib import Path

# Ensure project root is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st
import pandas as pd
import json
from datetime import datetime

from deployment.config import PROJECT_NAME, PROJECT_VERSION, TEAM, DATA_DIR, STORE_DIR, LLM_MODE
from agent.core_agent import OrchestratorAgent
from tools.tool_registry import TOOL_REGISTRY, execute_tool
from tools.schemas import (
    CALCULATE_ROP_SCHEMA, CALCULATE_EOQ_SCHEMA, CALCULATE_SAFETY_STOCK_SCHEMA,
    ANALYZE_SALES_VELOCITY_SCHEMA, FORECAST_DEMAND_SCHEMA, DETECT_DEMAND_SPIKE_SCHEMA,
    GET_INVENTORY_STATUS_SCHEMA, GENERATE_REORDER_RECOMMENDATION_SCHEMA,
    GET_SUPPLIER_LEAD_TIME_SCHEMA, RECORD_SUPPLIER_FEEDBACK_SCHEMA,
    ANALYZE_SUPPLIER_PERFORMANCE_SCHEMA,
)

# ══════════════════════════════════════════════════════════════════════════════
# Page Config
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="ARIS — Stock Replenishment Agent",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════════
# Initialize Agent (cached)
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_resource
def get_agent():
    return OrchestratorAgent()

agent = get_agent()

# ══════════════════════════════════════════════════════════════════════════════
# Sidebar Navigation
# ══════════════════════════════════════════════════════════════════════════════
st.sidebar.image("https://img.icons8.com/fluency/96/warehouse.png", width=64)
st.sidebar.title("ARIS")
st.sidebar.caption(f"v{PROJECT_VERSION} | {LLM_MODE.upper()} mode")

page = st.sidebar.radio("Navigate", [
    "🏠 Dashboard",
    "💬 Chat with Agent",
    "🛠️ Tool Explorer",
    "📊 Inventory Status",
    "🚚 Supplier Analysis",
    "🧠 Memory & Adaptation",
    "📋 Evaluation Results",
    "🏗️ Architecture",
])

st.sidebar.divider()
st.sidebar.info(f"**{TEAM}**\nCapstone Project — IIT Madras")


# ══════════════════════════════════════════════════════════════════════════════
# Helper: Load data
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data
def load_inventory():
    return pd.read_csv(DATA_DIR / "inventory_data.csv")

@st.cache_data
def load_sales():
    return pd.read_csv(DATA_DIR / "sales_data.csv")

@st.cache_data
def load_suppliers():
    return pd.read_csv(DATA_DIR / "supplier_data.csv")

@st.cache_data
def load_feedback():
    return pd.read_csv(DATA_DIR / "supplier_feedback.csv")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Dashboard
# ══════════════════════════════════════════════════════════════════════════════
if page == "🏠 Dashboard":
    st.title("📦 ARIS — Inventory Intelligence Dashboard")
    st.markdown("*AI-powered stock replenishment decision support system*")

    inv = load_inventory()
    sales = load_sales()
    suppliers = load_suppliers()

    col1, col2, col3, col4 = st.columns(4)

    reorder_needed = 0
    for _, row in inv.iterrows():
        result = execute_tool("get_inventory_status", sku_id=row["sku_id"])
        if result.get("health_status") == "REORDER_NEEDED":
            reorder_needed += 1

    col1.metric("Total SKUs", len(inv))
    col2.metric("⚠️ Need Reorder", reorder_needed, delta=f"{reorder_needed} urgent")
    col3.metric("Suppliers", suppliers["supplier_id"].nunique())
    col4.metric("Sales Records", f"{len(sales):,}")

    st.divider()

    st.subheader("📊 Inventory Health Overview")

    health_data = []
    for _, row in inv.iterrows():
        result = execute_tool("get_inventory_status", sku_id=row["sku_id"])
        health_data.append({
            "SKU": row["sku_id"],
            "Name": result.get("sku_name", ""),
            "Current Stock": result.get("current_stock", 0),
            "Reorder Point": result.get("reorder_point", 0),
            "Safety Stock": result.get("safety_stock", 0),
            "Status": result.get("health_status", ""),
        })

    health_df = pd.DataFrame(health_data)

    def highlight_status(val):
        if val == "REORDER_NEEDED":
            return "background-color: #ffcccc"
        elif val == "OK":
            return "background-color: #ccffcc"
        elif val == "STOCKOUT":
            return "background-color: #ff6666; color: white"
        return ""

    st.dataframe(
        health_df.style.applymap(highlight_status, subset=["Status"]),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("📈 Daily Sales Volume (All SKUs)")
    sales_daily = sales.groupby("date")["units_sold"].sum().reset_index()
    sales_daily["date"] = pd.to_datetime(sales_daily["date"])
    st.line_chart(sales_daily.set_index("date")["units_sold"])


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Chat with Agent
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💬 Chat with Agent":
    st.title("💬 Chat with ARIS Agent")
    st.caption("Ask any inventory, supplier, or reorder question in plain English.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("metadata"):
                meta = msg["metadata"]
                st.caption(
                    f"Confidence: {meta['confidence']:.0%} | "
                    f"Latency: {meta['latency_ms']}ms | "
                    f"Escalated: {'Yes ⚠️' if meta['escalated'] else 'No'}"
                )

    if not st.session_state.messages:
        st.markdown("**Try these queries:**")
        examples = [
            "Does SKU-008 need reordering?",
            "Calculate the EOQ for SKU-001",
            "What is the safety stock for SKU-010 at 98% service level?",
            "How has supplier SUP-B been performing?",
            "Which SKUs are below their reorder point?",
            "Show me sales velocity for SKU-005",
        ]
        cols = st.columns(2)
        for i, ex in enumerate(examples):
            if cols[i % 2].button(ex, key=f"ex_{i}"):
                st.session_state.messages.append({"role": "user", "content": ex})
                st.rerun()

    if prompt := st.chat_input("Ask ARIS about your inventory..."):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = agent.run(prompt)

            st.markdown(response.answer)
            st.caption(
                f"Confidence: {response.confidence:.0%} | "
                f"Latency: {response.latency_ms}ms | "
                f"Escalated: {'Yes ⚠️' if response.escalated else 'No'}"
            )

            if response.plan_trace:
                with st.expander("🔍 Agent Reasoning Trace"):
                    for step in response.plan_trace:
                        st.code(step)

        st.session_state.messages.append({
            "role": "assistant",
            "content": response.answer,
            "metadata": {
                "confidence": response.confidence,
                "latency_ms": response.latency_ms,
                "escalated": response.escalated,
            }
        })


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Tool Explorer
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🛠️ Tool Explorer":
    st.title("🛠️ Tool Catalogue — 11 Self-Defined Tools")

    ALL_SCHEMAS = [
        ANALYZE_SALES_VELOCITY_SCHEMA, FORECAST_DEMAND_SCHEMA,
        DETECT_DEMAND_SPIKE_SCHEMA, GET_INVENTORY_STATUS_SCHEMA,
        CALCULATE_SAFETY_STOCK_SCHEMA, CALCULATE_ROP_SCHEMA,
        CALCULATE_EOQ_SCHEMA, GENERATE_REORDER_RECOMMENDATION_SCHEMA,
        GET_SUPPLIER_LEAD_TIME_SCHEMA, RECORD_SUPPLIER_FEEDBACK_SCHEMA,
        ANALYZE_SUPPLIER_PERFORMANCE_SCHEMA,
    ]

    tool_data = []
    for schema in ALL_SCHEMAS:
        params = schema.get("parameters", {}).get("properties", {})
        required = schema.get("parameters", {}).get("required", [])
        tool_data.append({
            "Tool": schema["name"],
            "Description": schema["description"][:80] + "...",
            "Parameters": ", ".join(params.keys()),
            "Required": ", ".join(required),
        })

    st.dataframe(pd.DataFrame(tool_data), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("🧪 Try a Tool")

    tool_name = st.selectbox("Select Tool", sorted(TOOL_REGISTRY.keys()))

    selected_schema = None
    for s in ALL_SCHEMAS:
        if s["name"] == tool_name:
            selected_schema = s
            break

    if selected_schema:
        with st.expander("📄 JSON Schema", expanded=False):
            st.json(selected_schema)

        params = selected_schema.get("parameters", {}).get("properties", {})
        st.markdown(f"**Parameters for `{tool_name}`:**")
        kwargs = {}
        for pname, pinfo in params.items():
            ptype = pinfo.get("type", "string")
            desc = pinfo.get("description", "")
            default = pinfo.get("default", "")

            if ptype == "number":
                kwargs[pname] = st.number_input(f"{pname} ({desc})", value=float(default) if default else 0.95)
            elif ptype == "integer":
                kwargs[pname] = st.number_input(f"{pname} ({desc})", value=int(default) if default else 30, step=1)
            elif ptype == "boolean":
                kwargs[pname] = st.checkbox(f"{pname} ({desc})", value=bool(default))
            else:
                kwargs[pname] = st.text_input(f"{pname} ({desc})", value=str(default) if default else "SKU-001")

        if st.button("▶️ Execute Tool", type="primary"):
            clean_kwargs = {k: v for k, v in kwargs.items() if v != "" and v is not None}
            with st.spinner(f"Executing {tool_name}..."):
                result = execute_tool(tool_name, **clean_kwargs)

            if result.get("status") == "error":
                st.error(f"Error: {result['message']}")
            else:
                st.success("Tool executed successfully!")
                st.json(result)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Inventory Status
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Inventory Status":
    st.title("📊 Detailed Inventory Analysis")

    inv = load_inventory()
    sku_id = st.selectbox("Select SKU", inv["sku_id"].tolist())

    if sku_id:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📦 Inventory Status")
            status = execute_tool("get_inventory_status", sku_id=sku_id)
            if status.get("status") != "error":
                health = status.get("health_status", "UNKNOWN")
                color = "🟢" if health == "OK" else "🟡" if health == "REORDER_NEEDED" else "🔴"
                st.markdown(f"### {color} {status.get('sku_name', sku_id)}")
                st.metric("Current Stock", f"{status.get('current_stock', 0)} units")
                st.metric("Reorder Point", f"{status.get('reorder_point', 0)} units")
                st.metric("Safety Stock", f"{status.get('safety_stock', 0)} units")
                st.metric("Health", health)

        with col2:
            st.subheader("📐 Calculations")

            rop = execute_tool("calculate_rop", sku_id=sku_id)
            eoq = execute_tool("calculate_eoq", sku_id=sku_id)
            ss = execute_tool("calculate_safety_stock", sku_id=sku_id, service_level=0.95)

            if rop.get("status") != "error":
                st.code(rop.get("formula", ""), language=None)
                st.metric("ROP", f"{rop.get('reorder_point', 0)} units")

            if eoq.get("status") != "error":
                st.code(eoq.get("formula", ""), language=None)
                st.metric("EOQ", f"{eoq.get('eoq', 0)} units")

            if ss.get("status") != "error":
                st.code(ss.get("formula", ""), language=None)
                st.metric("Safety Stock", f"{ss.get('safety_stock', 0)} units")

        st.divider()

        st.subheader(f"📈 Sales History — {sku_id}")
        sales = load_sales()
        sku_sales = sales[sales["sku_id"] == sku_id].copy()
        sku_sales["date"] = pd.to_datetime(sku_sales["date"])
        sku_sales = sku_sales.sort_values("date")
        st.line_chart(sku_sales.set_index("date")["units_sold"])


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Supplier Analysis
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🚚 Supplier Analysis":
    st.title("🚚 Supplier Performance Dashboard")

    suppliers = load_suppliers()
    supplier_ids = suppliers["supplier_id"].unique().tolist()
    selected_sup = st.selectbox("Select Supplier", supplier_ids)

    if selected_sup:
        perf = execute_tool("analyze_supplier_performance", supplier_id=selected_sup, lookback_days=180)

        if perf.get("status") != "error":
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Supplier", perf.get("supplier_name", selected_sup))
            col2.metric("On-Time Rate", f"{perf.get('on_time_pct', 0):.0f}%")
            col3.metric("Avg Delay", f"{perf.get('avg_delay_days', 0):.1f} days")
            col4.metric("Reliability", f"{perf.get('current_reliability_score', 0):.2f}")

            action = perf.get("action", "N/A")
            if "Improvement" in action or "Consider" in action:
                st.warning(f"⚠️ Recommended Action: **{action}**")
            else:
                st.success(f"✅ Recommended Action: **{action}**")

        st.divider()

        st.subheader("📋 Delivery History")
        feedback = load_feedback()
        sup_feedback = feedback[feedback["supplier_id"] == selected_sup].copy()
        if not sup_feedback.empty:
            st.dataframe(sup_feedback.tail(20), use_container_width=True, hide_index=True)
        else:
            st.info("No delivery records found for this supplier.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Memory & Adaptation
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🧠 Memory & Adaptation":
    st.title("🧠 Memory System & Adaptive Behaviour")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📝 Long-Term Memory")
        ltm_path = STORE_DIR / "long_term_memory.json"
        if ltm_path.exists():
            with open(ltm_path) as f:
                ltm = json.load(f)
            recs_key = "past_recommendations" if "past_recommendations" in ltm else "recommendations"
            if ltm.get(recs_key):
                recs = ltm[recs_key][-10:]
                st.markdown(f"**{len(ltm.get(recs_key, []))} total recommendations stored**")
                for rec in reversed(recs):
                    st.markdown(
                        f"- **{rec.get('sku_id')}** → {rec.get('recommended_qty', rec.get('qty', '?'))} units "
                        f"(conf: {rec.get('confidence', '?')}) at {rec.get('logged_at', rec.get('timestamp', '?'))[:16]}"
                    )
            else:
                st.info("No recommendations stored yet. Run some queries first!")
        else:
            st.info("Memory file not created yet.")

    with col2:
        st.subheader("🔄 Adaptation Parameters")
        adapt_path = STORE_DIR / "adaptation_params.json"
        if adapt_path.exists():
            with open(adapt_path) as f:
                adapt = json.load(f)

            multiplier = adapt.get("safety_stock_multiplier", 1.0)
            feedback_hist = adapt.get("feedback_history", [])
            total_fb = len(feedback_hist)
            negative = sum(1 for fb in feedback_hist if not fb.get("was_helpful", True))

            st.metric("Safety Stock Multiplier", f"{multiplier:.2f}×")
            st.metric("Total Feedback Events", total_fb)
            st.metric("Negative Feedback", negative)

            if total_fb > 0:
                neg_rate = negative / total_fb
                st.progress(neg_rate, text=f"Negative rate: {neg_rate:.0%}")

                if multiplier > 1.0:
                    st.warning(
                        f"⚠️ Multiplier increased to {multiplier:.2f}× due to "
                        f"{neg_rate:.0%} negative feedback rate. "
                        f"Safety stock is being inflated by {(multiplier-1)*100:.0f}%."
                    )
                else:
                    st.success("✅ No adaptation needed — feedback is positive.")
        else:
            st.info("No adaptation data yet.")

    st.divider()
    st.subheader("📐 How Adaptation Works")
    st.markdown("""
    ```
    IF negative_feedback_rate > 40%:
        safety_stock_multiplier += 0.05  (capped at 1.5×)

    IF negative_feedback_rate < 20%:
        safety_stock_multiplier -= 0.02  (floored at 1.0×)

    Applied: Safety Stock = base_SS × multiplier
    ```

    This means the agent **learns from user feedback** — if users keep rejecting
    recommendations as "too low", the system gradually increases safety stock buffers.
    """)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Evaluation Results
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Evaluation Results":
    st.title("📋 Evaluation Results")

    eval_path = ROOT / "logs" / "evaluation_results.json"

    if eval_path.exists():
        with open(eval_path) as f:
            results = json.load(f)

        passed = sum(1 for r in results if r["passed"])
        total = len(results)

        col1, col2, col3 = st.columns(3)
        col1.metric("Pass Rate", f"{passed}/{total} ({passed/total*100:.0f}%)")
        col2.metric("Avg Confidence", f"{sum(r['confidence'] for r in results)/total:.0%}")
        col3.metric("Avg Latency", f"{sum(r['latency_ms'] for r in results)/total:.0f}ms")

        st.divider()

        eval_df = pd.DataFrame([{
            "ID": r["id"],
            "Category": r["category"],
            "Pass": "✅" if r["passed"] else "❌",
            "KW Score": f"{r['kw_score']:.0%}",
            "Confidence": f"{r['confidence']:.0%}",
            "Latency": f"{r['latency_ms']}ms",
            "Failure": r.get("failure_reason", "—"),
        } for r in results])

        st.dataframe(eval_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No evaluation results found. Run `python scripts/run_evaluation.py` first.")
        if st.button("Run Evaluation Now"):
            import subprocess
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "run_evaluation.py")],
                capture_output=True, text=True, cwd=str(ROOT)
            )
            st.code(result.stdout[-2000:] if result.stdout else result.stderr[-2000:])
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Architecture
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🏗️ Architecture":
    st.title("🏗️ System Architecture")

    st.markdown("""
    ## The 5-Step Orchestrator Loop

    Every query goes through this pipeline:
    """)

    cols = st.columns(5)
    steps = [
        ("1️⃣ PERCEIVE", "Extract intent,\nentities, safety"),
        ("2️⃣ PLAN", "Route to tools,\nretrieve KB context"),
        ("3️⃣ ACT", "Execute tools,\ncompute formulas"),
        ("4️⃣ VALIDATE", "Confidence score,\nHITL check"),
        ("5️⃣ RESPOND", "Format answer,\nsave to memory"),
    ]
    for col, (title, desc) in zip(cols, steps):
        col.markdown(f"**{title}**")
        col.caption(desc)
        col.markdown("→")

    st.divider()

    st.markdown("""
    ## Tool Categories

    | Category | Tools | Purpose |
    |----------|-------|---------|
    | **Sales** | `analyze_sales_velocity`, `forecast_demand`, `detect_demand_spike` | Demand analysis |
    | **Inventory** | `get_inventory_status`, `calculate_safety_stock`, `calculate_rop`, `calculate_eoq`, `generate_reorder_recommendation` | Stock calculations |
    | **Supplier** | `get_supplier_lead_time`, `record_supplier_feedback`, `analyze_supplier_performance` | Supplier management |

    ## Safety Layers

    | Layer | Trigger | Action |
    |-------|---------|--------|
    | Pattern Detection | "delete", "execute", "bypass" | Immediate refusal |
    | Confidence Check | conf < 60% | HITL escalation |
    | Value Check | order > $50,000 | HITL escalation |
    | Stockout Detection | current_stock = 0 | HITL escalation |
    | PII Protection | emails in output | Mask as `***@***.com` |

    ## Key Formulas

    | Formula | Expression |
    |---------|-----------|
    | **ROP** | `(Avg Daily Demand × Lead Time) + Safety Stock` |
    | **Safety Stock** | `Z × σ_demand × √(Lead Time)` |
    | **EOQ** | `√(2 × Annual Demand × Ordering Cost / Holding Cost)` |
    """)

    st.divider()
    st.markdown(f"**{TEAM}** | IIT Madras Capstone Project | {datetime.now().strftime('%B %Y')}")
