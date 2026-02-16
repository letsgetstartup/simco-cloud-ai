import json
import os
from dataclasses import dataclass

import firebase_admin
import google.generativeai as genai
import pandas as pd
import streamlit as st
from firebase_admin import credentials, firestore

# --- APP CONFIGURATION ---
st.set_page_config(page_title="JobBoss CNC ERP Clone", page_icon="🏭", layout="wide")


@dataclass(frozen=True)
class ModuleDefinition:
    name: str
    objective: str
    primary_collections: list[str]
    kpi_fields: list[str]
    suggested_actions: list[str]


MODULES: dict[str, ModuleDefinition] = {
    "CRM & Quoting": ModuleDefinition(
        name="CRM & Quoting",
        objective="Track RFQs, estimate machining hours, and convert quotes to jobs.",
        primary_collections=["jobs", "events", "machines"],
        kpi_fields=["quote_value", "estimated_hours", "win_rate"],
        suggested_actions=[
            "Prioritize open RFQs expiring in <7 days",
            "Flag quotes with margin below 18%",
            "Recommend next-best follow-up for top accounts",
        ],
    ),
    "Job Management": ModuleDefinition(
        name="Job Management",
        objective="Control travelers, operation routing, and WIP status.",
        primary_collections=["jobs", "machines", "signals"],
        kpi_fields=["wip_jobs", "on_time_rate", "scrap_risk"],
        suggested_actions=[
            "Detect late operations by machine cell",
            "Escalate jobs at risk of missing ship date",
            "Recommend setup reduction opportunities",
        ],
    ),
    "Scheduling": ModuleDefinition(
        name="Scheduling",
        objective="Optimize finite-capacity schedules across CNC machines and shifts.",
        primary_collections=["machines", "jobs", "events"],
        kpi_fields=["capacity_load", "bottleneck_machine", "queue_hours"],
        suggested_actions=[
            "Move overflow jobs from overloaded machines",
            "Identify best machine for rush work",
            "Surface setup-family batching opportunities",
        ],
    ),
    "Inventory & Tool Crib": ModuleDefinition(
        name="Inventory & Tool Crib",
        objective="Manage raw stock, inserts, holders, and consumables.",
        primary_collections=["tools", "jobs", "signals"],
        kpi_fields=["stockout_risk", "tool_life", "inventory_turns"],
        suggested_actions=[
            "Highlight tools under safety stock",
            "Forecast insert demand for next 2 weeks",
            "Recommend reorder quantities by supplier lead time",
        ],
    ),
    "Purchasing": ModuleDefinition(
        name="Purchasing",
        objective="Handle PO creation, vendor performance, and expedite workflows.",
        primary_collections=["tools", "events", "jobs"],
        kpi_fields=["po_cycle_days", "supplier_otd", "price_variance"],
        suggested_actions=[
            "Detect late supplier shipments",
            "Find alternate suppliers for critical shortages",
            "Identify repeated expedite fees",
        ],
    ),
    "Quality": ModuleDefinition(
        name="Quality",
        objective="Monitor NCRs, first article inspections, and process capability signals.",
        primary_collections=["events", "signals", "jobs"],
        kpi_fields=["ppm_defects", "ncr_count", "cpk_alerts"],
        suggested_actions=[
            "Link alarms to likely nonconformance causes",
            "Prioritize high-cost quality escapes",
            "Generate corrective action checklist",
        ],
    ),
    "Shipping & Invoicing": ModuleDefinition(
        name="Shipping & Invoicing",
        objective="Coordinate pack/ship readiness and billing throughput.",
        primary_collections=["jobs", "events", "machines"],
        kpi_fields=["ready_to_ship", "invoice_backlog", "ship_on_time"],
        suggested_actions=[
            "Identify jobs complete but not invoiced",
            "Predict late shipments in next 72 hours",
            "Surface billing blockers from missing paperwork",
        ],
    ),
    "Maintenance": ModuleDefinition(
        name="Maintenance",
        objective="Run preventive/predictive maintenance and reduce unplanned downtime.",
        primary_collections=["machines", "signals", "events"],
        kpi_fields=["mtbf", "mttr", "downtime_cost"],
        suggested_actions=[
            "Rank machines by failure risk",
            "Recommend PM windows from load forecasts",
            "Estimate downtime cost avoided by interventions",
        ],
    ),
}


# --- AUTHENTICATION HANDLER ---
def get_db():
    try:
        if not firebase_admin._apps:
            cred = None

            if "manual_firebase_json" in st.session_state and st.session_state.manual_firebase_json:
                try:
                    key_dict = json.loads(st.session_state.manual_firebase_json)
                    st.sidebar.success("Using manually provided Firebase JSON")
                except Exception as e:
                    st.sidebar.error(f"Manual JSON Error: {e}")
                    key_dict = None
            else:
                raw_data = None
                if "firebase" in st.secrets:
                    raw_data = dict(st.secrets["firebase"])
                elif "FIREBASE_KEY" in st.secrets:
                    try:
                        raw_data = json.loads(st.secrets["FIREBASE_KEY"])
                    except Exception:
                        raw_data = None

                key_dict = dict(raw_data) if raw_data else None

            if key_dict and "private_key" in key_dict:
                pk = str(key_dict["private_key"])
                content = pk.replace("-----BEGIN PRIVATE KEY-----", "")
                content = content.replace("-----END PRIVATE KEY-----", "")
                content = content.replace("_____BEGIN PRIVATE KEY_____", "")
                content = content.replace("_____END PRIVATE KEY____", "")
                content = content.replace("\\n", "\n").strip()
                key_dict["private_key"] = (
                    "-----BEGIN PRIVATE KEY-----\n"
                    f"{content}\n"
                    "-----END PRIVATE KEY-----\n"
                )

            if key_dict:
                try:
                    cred = credentials.Certificate(key_dict)
                except Exception as cert_err:
                    st.sidebar.error(f"Certificate Error: {cert_err}")

            if not cred and os.path.exists("firebase_key.json"):
                cred = credentials.Certificate("firebase_key.json")

            if cred:
                firebase_admin.initialize_app(cred)
            else:
                return None

        return firestore.client()
    except Exception as e:
        st.error(f"DB Error: {e}")
        return None


@st.cache_data(ttl=300)
def build_demo_dataset(module_name: str) -> pd.DataFrame:
    module = MODULES[module_name]
    rows = []
    for i in range(1, 13):
        rows.append(
            {
                "work_order": f"WO-{1000+i}",
                "customer": ["AeroCast", "HydraValve", "ProtoMotion"][i % 3],
                "machine": ["Haas VF2", "Mazak QT200", "Doosan DNM"][i % 3],
                "status": ["Queued", "In Process", "Inspection", "Ready to Ship"][i % 4],
                "priority": ["Normal", "Rush", "Critical"][i % 3],
                "estimated_hours": round(3 + (i * 0.8), 1),
                "actual_hours": round(2.5 + (i * 0.9), 1),
                "quote_value": 1600 + (i * 190),
                "margin_pct": round(15 + (i * 1.3), 1),
                "risk_score": round(35 + (i * 2.7), 1),
                "module": module.name,
                "objective": module.objective,
            }
        )
    return pd.DataFrame(rows)


def ask_module_agent(api_key: str, module: ModuleDefinition, data: pd.DataFrame, user_query: str) -> str:
    if not api_key:
        high_risk = data.sort_values("risk_score", ascending=False).head(3)
        high_risk_orders = ", ".join(high_risk["work_order"].tolist())
        return (
            f"### {module.name} Agent (Local Mode)\n"
            f"Objective: {module.objective}\n\n"
            f"Top risk work orders: **{high_risk_orders}**.\n"
            "Recommended immediate actions:\n"
            + "\n".join([f"- {a}" for a in module.suggested_actions])
            + f"\n\nUser request interpreted as: _{user_query}_"
        )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-pro")
    context = data.head(30).to_json(orient="records")
    prompt = f"""
You are the dedicated ERP specialist for the module '{module.name}' in a CNC machine shop.

Module objective: {module.objective}
Primary collections: {', '.join(module.primary_collections)}
KPIs to emphasize: {', '.join(module.kpi_fields)}
Preferred actions: {', '.join(module.suggested_actions)}

Data sample:
{context}

User request:
{user_query}

Respond with:
1) concise diagnosis
2) prioritized action plan
3) KPI impact estimate (directional if needed)
4) next 3 follow-up questions
"""
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Agent error for {module.name}: {e}"


def ask_orchestrator_agent(api_key: str, module_outputs: dict[str, str], strategy_prompt: str) -> str:
    merged = "\n\n".join([f"[{k}]\n{v}" for k, v in module_outputs.items()])
    if not api_key:
        return (
            "### ERP Orchestrator (Local Mode)\n"
            "Cross-module consensus:\n"
            "- Protect throughput by rebalancing constrained machines first.\n"
            "- Guard margin by prioritizing high-value jobs with low quality risk.\n"
            "- Prevent stockouts for tools tied to rush work orders.\n"
            f"\nPlanning focus: _{strategy_prompt}_"
        )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-pro")
    prompt = f"""
You are the master ERP orchestrator for a small CNC shop.
Synthesize these module-agent outputs into one integrated operations plan.

Module outputs:
{merged}

Strategic prompt from management:
{strategy_prompt}

Output format:
- 30/60/90 day plan
- sequencing by module owner
- dependencies and risks
- measurable targets
"""
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Orchestrator error: {e}"


def render_module_overview() -> None:
    st.subheader("ERP Module Map (JobBoss-style for CNC)")
    cols = st.columns(4)
    for idx, (module_name, module) in enumerate(MODULES.items()):
        with cols[idx % 4]:
            st.markdown(f"**{module_name}**")
            st.caption(module.objective)
            st.write("Collections:", ", ".join(module.primary_collections))


def main():
    st.title("🏭 JobBoss ERP Clone for Small CNC Shops")
    st.markdown(
        "This workspace models a JobBoss-style ERP with an AI agent embedded in every core module "
        "plus a master orchestrator agent for cross-functional execution."
    )

    with st.sidebar:
        st.header("System Setup")
        api_key = st.text_input("Gemini API Key (optional)", type="password")

        with st.expander("Firebase override (optional)"):
            manual_json = st.text_area("Paste Firebase JSON", height=120)
            if manual_json:
                st.session_state.manual_firebase_json = manual_json

        db = get_db()
        if db:
            st.success("Firebase connected")
        else:
            st.info("Running in demo mode with generated ERP data")

        st.divider()
        st.markdown("### Clone capabilities")
        st.write("- Role-based module views")
        st.write("- Job traveler and WIP analytics")
        st.write("- Scheduling + bottleneck insights")
        st.write("- Quality, purchasing, shipping, invoicing")
        st.write("- Agent in every module + orchestrator")

    overview_tab, module_tab, orchestrator_tab = st.tabs(
        ["Executive Overview", "Module Agent Workbench", "Cross-Module Orchestrator"]
    )

    with overview_tab:
        render_module_overview()
        st.divider()
        st.subheader("CNC Shop KPI Snapshot")
        metric_cols = st.columns(5)
        metric_cols[0].metric("On-Time Delivery", "92.4%", "+1.8%")
        metric_cols[1].metric("Shop Utilization", "84.1%", "+2.1%")
        metric_cols[2].metric("Quote Win Rate", "43.6%", "+4.4%")
        metric_cols[3].metric("Scrap / Rework", "3.7%", "-0.6%")
        metric_cols[4].metric("Invoice Lag", "2.9 days", "-0.8d")

    with module_tab:
        module_name = st.selectbox("Select ERP module", list(MODULES.keys()))
        module = MODULES[module_name]
        dataset = build_demo_dataset(module_name)

        left, right = st.columns([1.2, 1])
        with left:
            st.markdown(f"### {module.name}")
            st.caption(module.objective)
            st.dataframe(dataset, width="stretch")
        with right:
            st.markdown("### Agent Controls")
            st.write("Suggested workflows:")
            for action in module.suggested_actions:
                st.write(f"- {action}")

            question = st.text_area(
                "Ask this module agent",
                placeholder="Example: Which active jobs are most likely to miss promised delivery and why?",
            )
            if st.button("Run Module Agent", type="primary") and question:
                response = ask_module_agent(api_key, module, dataset, question)
                st.markdown(response)

    with orchestrator_tab:
        st.subheader("ERP Master Agent")
        st.caption("Collect module recommendations and synthesize into one operating plan.")

        selected_modules = st.multiselect(
            "Modules to include",
            list(MODULES.keys()),
            default=["Job Management", "Scheduling", "Inventory & Tool Crib", "Quality"],
        )
        strategy_prompt = st.text_area(
            "Management objective",
            value="Increase throughput 12% next quarter without additional headcount.",
        )

        if st.button("Run Orchestrator", type="primary"):
            if not selected_modules:
                st.warning("Select at least one module")
            else:
                outputs = {}
                for selected in selected_modules:
                    module = MODULES[selected]
                    sample = build_demo_dataset(selected)
                    outputs[selected] = ask_module_agent(
                        api_key,
                        module,
                        sample,
                        "Provide your top operational recommendations for this quarter.",
                    )
                final_plan = ask_orchestrator_agent(api_key, outputs, strategy_prompt)
                st.markdown(final_plan)


if __name__ == "__main__":
    main()
