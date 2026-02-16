import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import firebase_admin
import google.generativeai as genai
import pandas as pd
import streamlit as st
from firebase_admin import credentials, firestore

st.set_page_config(page_title="JobBoss CNC ERP", page_icon="🏭", layout="wide")


@dataclass(frozen=True)
class ModuleDefinition:
    name: str
    owner: str
    objective: str
    primary_collections: list[str]
    kpi_fields: list[str]
    workflows: list[str]


MODULES: dict[str, ModuleDefinition] = {
    "CRM & Quoting": ModuleDefinition(
        name="CRM & Quoting",
        owner="Sales / Estimating",
        objective="Convert RFQs into profitable CNC jobs with consistent quoting rules.",
        primary_collections=["jobs", "events"],
        kpi_fields=["quote_value", "estimated_hours", "margin_pct", "win_rate"],
        workflows=[
            "RFQ triage",
            "Estimator workload",
            "Quote follow-up cadence",
            "Quote-to-job conversion",
        ],
    ),
    "Job Management": ModuleDefinition(
        name="Job Management",
        owner="Production Control",
        objective="Manage travelers, operation status, and WIP for every active job.",
        primary_collections=["jobs", "machines", "signals"],
        kpi_fields=["wip_jobs", "at_risk_jobs", "actual_vs_estimated_hours"],
        workflows=[
            "Traveler readiness",
            "Operation progress",
            "Hot job escalation",
            "WIP aging",
        ],
    ),
    "Scheduling": ModuleDefinition(
        name="Scheduling",
        owner="Planner",
        objective="Build finite-capacity plans that maximize spindle utilization and OTD.",
        primary_collections=["machines", "jobs", "events"],
        kpi_fields=["machine_load", "queue_hours", "otd_risk", "setup_overlap"],
        workflows=[
            "Daily dispatch list",
            "Bottleneck balancing",
            "Setup family batching",
            "Rush job insertion",
        ],
    ),
    "Inventory & Tool Crib": ModuleDefinition(
        name="Inventory & Tool Crib",
        owner="Tool Crib / Materials",
        objective="Prevent stockouts of tools and raw materials without overstocking.",
        primary_collections=["tools", "jobs", "signals"],
        kpi_fields=["stockout_risk", "tool_life", "inventory_turns"],
        workflows=[
            "Critical tool watchlist",
            "Reorder trigger automation",
            "Usage forecast",
            "Tool life exception review",
        ],
    ),
    "Purchasing": ModuleDefinition(
        name="Purchasing",
        owner="Buyer",
        objective="Issue and expedite POs while improving supplier performance.",
        primary_collections=["tools", "events", "jobs"],
        kpi_fields=["po_cycle_days", "supplier_otd", "expedite_count"],
        workflows=[
            "PO queue review",
            "Late PO recovery",
            "Supplier scorecard",
            "Critical shortage escalation",
        ],
    ),
    "Quality": ModuleDefinition(
        name="Quality",
        owner="Quality Engineer",
        objective="Catch defects early and close corrective actions quickly.",
        primary_collections=["events", "signals", "jobs"],
        kpi_fields=["ppm_defects", "ncr_count", "cpk_alerts"],
        workflows=[
            "FAI checklist",
            "In-process inspection",
            "NCR triage",
            "Corrective action closure",
        ],
    ),
    "Shipping & Invoicing": ModuleDefinition(
        name="Shipping & Invoicing",
        owner="Shipping / Accounting",
        objective="Ship complete orders on promise date and invoice same day.",
        primary_collections=["jobs", "events"],
        kpi_fields=["ready_to_ship", "invoice_lag_days", "ship_on_time"],
        workflows=[
            "Pack list readiness",
            "Carrier planning",
            "Invoice queue management",
            "Shipment exception response",
        ],
    ),
    "Maintenance": ModuleDefinition(
        name="Maintenance",
        owner="Maintenance Lead",
        objective="Reduce unplanned downtime with PM and predictive maintenance actions.",
        primary_collections=["machines", "signals", "events"],
        kpi_fields=["mtbf", "mttr", "downtime_hours", "downtime_cost"],
        workflows=[
            "PM calendar",
            "Condition-based alerts",
            "Downtime root-cause review",
            "Spare parts planning",
        ],
    ),
}


def get_db():
    try:
        if not firebase_admin._apps:
            cred = None
            key_dict = None

            manual = st.session_state.get("manual_firebase_json")
            if manual:
                try:
                    key_dict = json.loads(manual)
                except Exception as exc:
                    st.sidebar.error(f"Manual Firebase JSON is invalid: {exc}")

            if not key_dict:
                if "firebase" in st.secrets:
                    key_dict = dict(st.secrets["firebase"])
                elif "FIREBASE_KEY" in st.secrets:
                    try:
                        key_dict = json.loads(st.secrets["FIREBASE_KEY"])
                    except Exception:
                        key_dict = None

            if key_dict and "private_key" in key_dict:
                key = str(key_dict["private_key"])
                key = key.replace("-----BEGIN PRIVATE KEY-----", "")
                key = key.replace("-----END PRIVATE KEY-----", "")
                key = key.replace("_____BEGIN PRIVATE KEY_____", "")
                key = key.replace("_____END PRIVATE KEY_____", "")
                key = key.replace("\\n", "\n").strip()
                key_dict["private_key"] = f"-----BEGIN PRIVATE KEY-----\n{key}\n-----END PRIVATE KEY-----\n"

            if key_dict:
                try:
                    cred = credentials.Certificate(key_dict)
                except Exception as exc:
                    st.sidebar.error(f"Firebase certificate error: {exc}")

            if not cred and os.path.exists("firebase_key.json"):
                cred = credentials.Certificate("firebase_key.json")

            if cred:
                firebase_admin.initialize_app(cred)
            else:
                return None

        return firestore.client()
    except Exception as exc:
        st.sidebar.error(f"Firestore unavailable: {exc}")
        return None


@st.cache_data(ttl=120)
def load_collection_data(collection_name: str, limit: int = 250) -> pd.DataFrame:
    db = get_db()
    if not db:
        return pd.DataFrame()
    try:
        docs = db.collection(collection_name).limit(limit).stream()
        rows = [doc.to_dict() for doc in docs]
        if not rows:
            return pd.DataFrame()
        return pd.json_normalize(rows)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def build_demo_dataset(module_name: str) -> pd.DataFrame:
    module = MODULES[module_name]
    now = datetime.now(timezone.utc)
    rows = []
    for i in range(1, 16):
        due = (now + timedelta(days=i - 8)).date().isoformat()
        rows.append(
            {
                "job_id": f"JB-{1200 + i}",
                "customer": ["AeroCast", "HydraValve", "ProtoMotion", "Northline"][(i - 1) % 4],
                "part": ["Valve Body", "Impeller", "Housing", "Bracket"][(i - 1) % 4],
                "machine": ["Haas VF2", "Mazak QT200", "Doosan DNM"][(i - 1) % 3],
                "status": ["Queued", "Setup", "In Process", "Inspection", "Ready to Ship"][(i - 1) % 5],
                "priority": ["Normal", "Rush", "Critical"][(i - 1) % 3],
                "due_date": due,
                "estimated_hours": round(2.0 + i * 0.8, 1),
                "actual_hours": round(2.5 + i * 0.9, 1),
                "quote_value": 1200 + i * 220,
                "margin_pct": round(14 + i * 1.1, 1),
                "risk_score": round(30 + i * 3.2, 1),
                "module": module.name,
                "owner": module.owner,
            }
        )
    return pd.DataFrame(rows)


def merge_data_for_module(module_name: str) -> tuple[pd.DataFrame, str]:
    module = MODULES[module_name]
    source_frames = []
    for collection in module.primary_collections:
        df = load_collection_data(collection)
        if not df.empty:
            df["_source_collection"] = collection
            source_frames.append(df)

    if not source_frames:
        return build_demo_dataset(module_name), "demo"

    live = pd.concat(source_frames, ignore_index=True)
    if "risk_score" not in live.columns:
        live["risk_score"] = 50
    return live, "firebase"


def to_json_context(df: pd.DataFrame, max_rows: int = 40) -> str:
    sample = df.head(max_rows).copy()
    for col in sample.columns:
        if pd.api.types.is_datetime64_any_dtype(sample[col]):
            sample[col] = sample[col].astype(str)
    return sample.to_json(orient="records")


def ask_module_agent(api_key: str, module: ModuleDefinition, data: pd.DataFrame, user_query: str) -> str:
    top_risks = data.sort_values("risk_score", ascending=False).head(3) if "risk_score" in data.columns else data.head(3)
    risk_jobs = ", ".join(top_risks.iloc[:, 0].astype(str).tolist()) if not top_risks.empty else "No active jobs"

    if not api_key:
        actions = "\n".join([f"- {workflow}" for workflow in module.workflows])
        return (
            f"### {module.name} Agent ({module.owner})\n"
            f"**Objective:** {module.objective}\n\n"
            f"**High-risk jobs/orders:** {risk_jobs}\n\n"
            "**Recommended workflow focus:**\n"
            f"{actions}\n\n"
            f"**Interpreted request:** _{user_query}_"
        )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-pro")
    prompt = f"""
You are the ERP AI specialist for module: {module.name}
Module owner: {module.owner}
Objective: {module.objective}
KPIs: {', '.join(module.kpi_fields)}
Workflows: {', '.join(module.workflows)}

Data sample:
{to_json_context(data)}

User request:
{user_query}

Return markdown with:
1. Executive diagnosis (max 6 bullets)
2. Prioritized actions (P1/P2/P3)
3. KPI impact estimate table
4. Risks and assumptions
5. Next 3 actions the module owner should take today
"""
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as exc:
        return f"Agent error ({module.name}): {exc}"


def ask_orchestrator_agent(api_key: str, module_outputs: dict[str, str], strategy_prompt: str) -> str:
    merged = "\n\n".join([f"## {module}\n{output}" for module, output in module_outputs.items()])

    if not api_key:
        return (
            "### ERP Orchestrator (Local Mode)\n"
            "**30 days:** stabilize bottlenecks, lock dispatch priorities, cut expedite leakage.\n"
            "**60 days:** reduce setup overlap losses, improve supplier OTD, tighten quality gates.\n"
            "**90 days:** sustain OTD >95%, push invoice lag below 2 days, reduce downtime >15%.\n\n"
            f"**Management strategy interpreted:** _{strategy_prompt}_"
        )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-pro")
    prompt = f"""
You are the master ERP orchestrator for a small CNC shop.
Create one integrated plan based on module outputs below.

{merged}

Management strategy:
{strategy_prompt}

Format:
- 30/60/90 day plan with owner per line
- dependency map across modules
- top 5 risks + mitigations
- measurable KPI targets
- weekly operating cadence recommendation
"""
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as exc:
        return f"Orchestrator error: {exc}"


def render_module_catalog() -> None:
    st.subheader("CNC ERP Module Map")
    grid = st.columns(4)
    for index, module in enumerate(MODULES.values()):
        with grid[index % 4]:
            st.markdown(f"**{module.name}**")
            st.caption(f"Owner: {module.owner}")
            st.write(module.objective)
            st.write("KPIs:", ", ".join(module.kpi_fields[:3]))


def render_kpis() -> None:
    cols = st.columns(6)
    cols[0].metric("On-Time Delivery", "93.1%", "+1.4%")
    cols[1].metric("Shop Utilization", "85.2%", "+1.9%")
    cols[2].metric("Quote Win Rate", "44.8%", "+2.7%")
    cols[3].metric("Scrap/Rework", "3.4%", "-0.4%")
    cols[4].metric("Invoice Lag", "2.4 days", "-0.5d")
    cols[5].metric("Unplanned Downtime", "27.5 hrs/mo", "-3.1h")


def main():
    st.title("🏭 JobBoss-Style ERP Clone for Small CNC Shops")
    st.write(
        "A full-stack ERP operating cockpit with an AI agent in every module and a cross-module orchestrator."
    )

    with st.sidebar:
        st.header("Configuration")
        api_key = st.text_input("Gemini API Key (optional)", type="password")

        with st.expander("Firebase setup (optional)"):
            manual_json = st.text_area("Paste service account JSON", height=140)
            if manual_json:
                st.session_state.manual_firebase_json = manual_json

        db = get_db()
        st.success("Firebase connected") if db else st.info("Demo mode (generated data)")

        st.divider()
        st.markdown("### Included capabilities")
        for line in [
            "CRM/quoting + estimate intelligence",
            "job travelers + WIP controls",
            "finite scheduling + bottleneck alerts",
            "tool crib + purchasing automation",
            "quality/NCR and maintenance workflows",
            "shipping + same-day invoicing support",
        ]:
            st.write(f"- {line}")

    executive_tab, module_tab, orchestrator_tab = st.tabs(
        ["Executive", "Module Workbench", "Master Orchestrator"]
    )

    with executive_tab:
        render_module_catalog()
        st.divider()
        st.subheader("Plant KPI Snapshot")
        render_kpis()

    with module_tab:
        module_name = st.selectbox("Choose module", list(MODULES.keys()))
        module = MODULES[module_name]
        data, source = merge_data_for_module(module_name)

        left, right = st.columns([1.35, 1])
        with left:
            st.markdown(f"### {module.name}")
            st.caption(f"Owner: {module.owner} • Data source: {source}")
            st.dataframe(data.head(200), width="stretch")

        with right:
            st.markdown("### Module Agent")
            st.write("Primary workflows:")
            for item in module.workflows:
                st.write(f"- {item}")

            prompt = st.text_area(
                "Ask this module agent",
                placeholder="Example: Prioritize this week's late-risk work orders and propose recovery actions.",
            )
            if st.button("Run Module Agent", type="primary"):
                if prompt.strip():
                    result = ask_module_agent(api_key, module, data, prompt)
                    st.markdown(result)
                else:
                    st.warning("Please enter a question.")

    with orchestrator_tab:
        st.subheader("Cross-Module Operating Plan")
        include = st.multiselect(
            "Include module outputs",
            list(MODULES.keys()),
            default=["Job Management", "Scheduling", "Inventory & Tool Crib", "Quality", "Maintenance"],
        )
        strategy = st.text_area(
            "Management objective",
            value="Increase throughput by 12% in one quarter with no additional headcount while protecting margin.",
        )

        if st.button("Run Master Orchestrator", type="primary"):
            if not include:
                st.warning("Select at least one module.")
            else:
                with st.spinner("Running module agents and synthesizing plan..."):
                    outputs = {}
                    for module_name in include:
                        module = MODULES[module_name]
                        data, _ = merge_data_for_module(module_name)
                        outputs[module_name] = ask_module_agent(
                            api_key,
                            module,
                            data,
                            "Provide quarterly operational priorities and critical KPI levers.",
                        )
                    plan = ask_orchestrator_agent(api_key, outputs, strategy)
                    st.markdown(plan)


if __name__ == "__main__":
    main()
