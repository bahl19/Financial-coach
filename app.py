"""AI Financial Coach - Streamlit UI (Implementation Plan - MVP 1.md, Phase 8).

A thin controller: gather input, call public functions in `utils.*` and
`agents.graph`, render the returned contracts. Any financial logic here is
logic that will diverge from the module that already owns it - this file
performs no arithmetic of its own.

The UI is the only writer to `st.session_state`, and it writes exclusively
through `utils.app_state` (Phase 8's standing constraint) - domain
components stay pure and return values.

Screen sequence: upload/questionnaire -> category review -> income/savings/
debts/goals/assumptions confirmation -> analysis (Overview, specialist
tabs, chat) -> scenario preview -> report/tracker download. Specialist tabs
and chat are both served from the one `run_graph()` invocation each rerun
computes at most once - there is exactly one orchestration path.
"""

import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agents import graph as g
from agents.orchestrator import build_chat_reply
from utils import app_state
from utils import finance_calc as fc
from utils import ingestion
from utils import reporting as rp
from utils import scenarios as sc
from utils.contracts import default_assumptions, validate_profile
from utils.llm import is_live

st.set_page_config(page_title="AI Financial Coach", page_icon="\U0001f4b0", layout="wide")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

DEFAULT_DEBTS = [
    {"name": "Credit Card", "balance": 4200.0, "apr": 22.9, "min_payment": 120.0},
    {"name": "Student Loan", "balance": 18500.0, "apr": 5.8, "min_payment": 210.0},
]

DEFAULT_GOALS = [
    {"name": "Emergency Fund Boost", "amount": 3000.0, "months": 6, "current": 500.0, "priority": "high"},
    {"name": "Vacation", "amount": 4000.0, "months": 10, "current": 200.0, "priority": "medium"},
]

@st.cache_data
def load_sample_transactions() -> pd.DataFrame:
    df = pd.read_csv(os.path.join(DATA_DIR, "sample_transactions.csv"))
    df["date"] = pd.to_datetime(df["date"])
    return df


def _categorized_df_to_transactions(df: pd.DataFrame) -> list:
    transactions = []
    for _, row in df.iterrows():
        date_value = row["date"]
        date_str = date_value.strftime("%Y-%m-%d") if hasattr(date_value, "strftime") else str(date_value)
        transactions.append({
            "date": date_str,
            "description": str(row["description"]),
            "amount": float(row["amount"]),
            "category": row["category"],
            "category_confidence": float(row["category_confidence"]),
            "needs_review": bool(row["needs_review"]),
            "transaction_type": row["transaction_type"],
        })
    return transactions


def _build_profile(categorized_df: pd.DataFrame) -> dict:
    fields = app_state.get_profile_fields()
    return {
        "schema_version": "1.0",
        "transactions": _categorized_df_to_transactions(categorized_df),
        "monthly_income": fields["monthly_income"],
        "current_savings": fields["current_savings"],
        "debts": fields["debts"],
        "goals": fields["goals"],
        "constraints": fields["constraints"],
        "assumptions": fields["assumptions"] or default_assumptions(),
    }


# Phase 10 (UX & Narrative Polish): presentation only - these map already-
# computed IDs to their already-computed titles for on-screen display. They
# invent no new label and change no finding/risk/trend/action's own fields;
# the downloadable report (utils.reporting) still shows the raw IDs
# alongside every title for anyone who wants exact traceability.
_SEVERITY_ICON = {"critical": "\U0001f534", "high": "\U0001f7e0", "medium": "\U0001f7e1", "low": "⚪", "positive": "\U0001f7e2"}


def _id_label_maps(findings: list, risks: list, trends: list, roadmap: dict) -> tuple:
    finding_titles = {f["finding_id"]: f["title"] for f in findings}
    risk_labels = {r["risk_id"]: f"{r['category'].replace('_', ' ').title()} risk" for r in risks}
    trend_labels = {t["trend_id"]: t["metric"].replace("_", " ").title() for t in trends}
    action_titles = {a["action_id"]: a["title"] for a in roadmap["actions"]}
    return finding_titles, risk_labels, trend_labels, action_titles


def _humanize_ids(ids: list, *label_maps: dict) -> str:
    if not ids:
        return "_none_"
    labels = []
    for item_id in ids:
        label = next((m[item_id] for m in label_maps if item_id in m), None)
        labels.append(label or item_id)
    return ", ".join(labels)


def _run_pipeline(profile: dict):
    """The one place profile -> (snapshot, trends, findings, risks, graph_result)
    is computed - Overview, specialist tabs, chat, scenario preview, and the
    report/tracker download all read from this same call's output."""
    transactions_df = fc._transactions_to_frame(profile.get("transactions") or [])
    flags = ingestion.detect_data_quality_issues(transactions_df) if not transactions_df.empty else []
    snapshot = fc.calculate_financial_snapshot(profile, data_quality_flags=flags)
    trends = fc.compute_trends(profile, snapshot)
    findings = fc.derive_findings(snapshot, trends)
    risks = fc.derive_risks(snapshot, findings)
    snapshot["risk_flags"] = fc.project_risk_flags(risks)
    graph_result = g.run_graph(profile, snapshot, findings, risks, trends)
    return (profile, snapshot, trends, findings, risks), graph_result


app_state.init_state()

# ---------------------------------------------------------------- sidebar --
with st.sidebar:
    st.title("\U0001f4b0 AI Financial Coach")
    st.caption("A multi-agent financial coach")
    st.markdown(f"**LLM status:** {'\U0001f7e2 Connected via OpenRouter' if is_live() else '\U0001f7e1 Offline mode (rule-based fallback)'}")
    if not is_live():
        st.caption("Set OPENROUTER_API_KEY in .env to enable full LLM-generated narratives.")

    st.divider()
    st.subheader("Step 1 - Your data")
    uploaded = st.file_uploader("Upload transactions (CSV or PDF)", type=["csv", "pdf"])
    if uploaded is not None:
        try:
            app_state.set_raw_transactions(ingestion.load_transactions(uploaded))
            st.success(f"Loaded {len(app_state.get_raw_transactions())} transactions.")
        except Exception as e:
            st.error(str(e))

    if st.button("Load sample data", width="stretch", key="load_sample_button"):
        app_state.set_raw_transactions(load_sample_transactions())
        st.success("Sample data loaded.")

# ------------------------------------------------------------------- main --
st.title("\U0001f4b0 AI Financial Coach")

raw_transactions = app_state.get_raw_transactions()
if raw_transactions is None:
    st.info("\U0001f448 Load sample data or upload a transactions file in the sidebar to get started.")
    st.caption("CSV format: columns `date`, `description`, `amount` -- expenses negative, income/deposits positive.")
    st.stop()

# --------------------------------------------------------- Step 2: review --
st.header("Step 2 - Review categorization")
working_df = ingestion.tag_transaction_types(ingestion.categorize_with_confidence(raw_transactions))
review_items = ingestion.build_review_items(working_df)

if review_items:
    st.caption(
        f"{len(review_items)} transaction(s) could not be matched to a category automatically. "
        "Pick the correct category for each one below."
    )
    review_df = pd.DataFrame(review_items)[["transaction_index", "description", "amount", "suggested_category"]]
    review_df = review_df.rename(columns={"suggested_category": "category"})
    known_categories = sorted(set(ingestion.CATEGORY_KEYWORDS) | {"Income", "Other"})
    edited_review = st.data_editor(
        review_df, width="stretch", key="review_editor",
        column_config={
            "transaction_index": st.column_config.NumberColumn(disabled=True),
            "description": st.column_config.TextColumn(disabled=True),
            "amount": st.column_config.NumberColumn(disabled=True, format="$%.2f"),
            "category": st.column_config.SelectboxColumn(options=known_categories, required=True),
        },
    )
    corrections = dict(zip(edited_review["transaction_index"], edited_review["category"]))
    working_df = ingestion.apply_category_corrections(working_df, corrections)
else:
    st.caption("Every transaction matched a category automatically - nothing to review.")

app_state.set_categorized_df(working_df)

with st.expander("View categorized transactions"):
    st.dataframe(working_df.sort_values("date", ascending=False), width="stretch")

# --------------------------------------------------- Step 3: confirmation --
st.header("Step 3 - Confirm your details")
fields = app_state.get_profile_fields()
current_assumptions = fields["assumptions"] or default_assumptions()

col1, col2 = st.columns(2)
monthly_income = col1.number_input(
    "Monthly income ($)", min_value=0.0, value=float(fields["monthly_income"] or 0.0), step=100.0, key="monthly_income_input",
)
current_savings = col2.number_input(
    "Current savings ($)", min_value=0.0, value=float(fields["current_savings"] or 0.0), step=100.0, key="current_savings_input",
)

st.subheader("Debts")
debts_df = pd.DataFrame(fields["debts"] or DEFAULT_DEBTS)
edited_debts = st.data_editor(debts_df, num_rows="dynamic", width="stretch", key="debts_editor")
debts = edited_debts.dropna().to_dict("records")

st.subheader("Goals")
goals_df = pd.DataFrame(fields["goals"] or DEFAULT_GOALS)
edited_goals = st.data_editor(goals_df, num_rows="dynamic", width="stretch", key="goals_editor")
goals = edited_goals.dropna().to_dict("records")

st.subheader("Constraints & assumptions")
c1, c2, c3 = st.columns(3)
buffer_value = c1.number_input(
    "Minimum monthly buffer ($)", min_value=0.0,
    value=float((fields["constraints"] or {}).get("minimum_monthly_buffer", 0.0)), step=50.0, key="buffer_input",
)
emergency_months = c2.number_input(
    "Emergency fund target (months)", min_value=0.0, value=float(current_assumptions.get("emergency_fund_months", 3)),
    step=1.0, key="emergency_months_input",
)
savings_apy = c3.number_input(
    "Savings APY (%)", min_value=0.0, value=float(current_assumptions.get("savings_apy", 0.04)) * 100, step=0.5,
    key="apy_input",
) / 100.0

assumptions = {**current_assumptions, "emergency_fund_months": emergency_months, "savings_apy": savings_apy}
constraints = {"minimum_monthly_buffer": buffer_value, "protected_categories": (fields["constraints"] or {}).get("protected_categories", [])}

app_state.set_profile_fields(
    # monthly_income also drives the "required inputs" gate below - a
    # widget-default 0.0 is treated as "not yet entered" there. current_savings
    # has no such gate: a literal, deliberate (or default/untouched) $0 is a
    # real, computable answer, and collapsing it to None would silently turn
    # emergency_fund_months into "unknown" for a user who genuinely has no
    # savings - the exact "a real zero must not become None" failure mode
    # Phase 11's rehearsal exists to catch.
    monthly_income=monthly_income or None, current_savings=current_savings,
    debts=debts, goals=goals, constraints=constraints, assumptions=assumptions,
)

profile_preview = _build_profile(working_df)
validation_issues = validate_profile(profile_preview)
if profile_preview["monthly_income"] is None:
    validation_issues = ["monthly_income is required"] + validation_issues

if validation_issues:
    st.error("Fix the following before running analysis:\n" + "\n".join(f"- {issue}" for issue in validation_issues))

analyze_clicked = st.button(
    "\U0001f680 Confirm & run analysis", type="primary", disabled=bool(validation_issues), key="analyze_button",
)
if analyze_clicked and not validation_issues:
    with st.spinner("Running the deterministic pipeline and specialist agents..."):
        pipeline_inputs, graph_result = _run_pipeline(profile_preview)
    app_state.set_analysis_result(pipeline_inputs, graph_result)
    app_state.confirm_profile()

if not app_state.is_profile_confirmed() or app_state.get_graph_result() is None:
    st.info("Confirm your details above and click **Confirm & run analysis** to continue.")
    st.stop()

# ------------------------------------------------------- Step 4: analysis --
profile, snapshot, trends, findings, risks = app_state.get_pipeline_inputs()
graph_result = app_state.get_graph_result()
roadmap = graph_result["roadmap_result"]
coach_summary = graph_result["coach_summary"]
validation_result = graph_result["validation_result"]

st.header("Step 4 - Analysis")

if validation_result.get("fallback_used"):
    st.warning(
        "⚠️ One or more specialist narratives failed a consistency check and were replaced with a "
        "deterministic, rule-based explanation instead. Nothing about your numbers changed - only the wording."
    )

tabs = st.tabs([
    "\U0001f4ca Overview", "\U0001f9fe Spending", "\U0001f4b3 Debt Payoff", "\U0001f3e6 Savings",
    "\U0001f4cb Budget", "\U0001f3af Goals", "\U0001f4ac Ask the Coach",
])

# --- Overview -----------------------------------------------------------
with tabs[0]:
    metrics = snapshot["metrics"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Health score", f"{snapshot['health_score']}/100", snapshot["health_band"])
    c2.metric("Gross surplus", f"${metrics['gross_surplus']:,.0f}" if metrics.get("gross_surplus") is not None else "unknown")
    c3.metric("Allocatable surplus", f"${metrics['allocatable_surplus']:,.0f}" if metrics.get("allocatable_surplus") is not None else "unknown")
    c4.metric("Total debt", f"${metrics['total_debt']:,.0f}")

    data_quality_flags = snapshot.get("data_quality_flags") or []
    if data_quality_flags:
        with st.container(border=True):
            st.markdown("**⚠️ Data limitations affecting these numbers:**")
            for flag in data_quality_flags:
                st.markdown(f"- {flag['detail']}")

    finding_titles, risk_labels, trend_labels, action_titles = _id_label_maps(findings, risks, trends, roadmap)

    st.subheader("\U0001f9ed Coach summary")
    st.markdown(f"**Overall health:** {coach_summary['overall_health']}")
    st.markdown("**Top priorities:** " + _humanize_ids(coach_summary["top_priorities"], action_titles))
    st.markdown("**Critical risks:** " + _humanize_ids(coach_summary["critical_risks"], risk_labels))
    st.markdown("**Important patterns:** " + _humanize_ids(coach_summary["important_patterns"], finding_titles))
    st.markdown("**Positive changes:** " + _humanize_ids(coach_summary["positive_changes"], finding_titles))
    st.caption(coach_summary["assumptions_and_limitations"])

    st.subheader("\U0001f6e3️ Roadmap")
    st.caption(
        f"Buffer reserved (planning constraint, not a distributed transfer): "
        f"${roadmap['allocation']['buffer_reserved']:,.2f}"
    )
    for action in sorted(roadmap["actions"], key=lambda a: a["priority"]):
        icon = _SEVERITY_ICON.get(action["severity"], "")
        st.markdown(
            f"{action['priority']}. {icon} **{action['title']}** ({action['timeframe']}): ${action['monthly_amount']:,.2f}/mo"
        )
        st.caption(action["rationale"])

# --- Spending ------------------------------------------------------------
with tabs[1]:
    spending_result = graph_result["spending_result"]
    st.subheader("Spending Analyzer")
    st.markdown(spending_result["narrative"])
    by_cat = spending_result["supporting_tables"]["by_category"]
    if not by_cat.empty:
        fig = px.pie(by_cat, names="category", values="amount", hole=0.4)
        st.plotly_chart(fig, width="stretch")
    monthly = spending_result["supporting_tables"]["monthly_cashflow"]
    if not monthly.empty:
        fig2 = go.Figure()
        fig2.add_bar(x=monthly["month"], y=monthly["income"], name="Income")
        fig2.add_bar(x=monthly["month"], y=monthly["expenses"], name="Expenses")
        fig2.update_layout(barmode="group", height=350)
        st.plotly_chart(fig2, width="stretch")

# --- Debt ------------------------------------------------------------------
with tabs[2]:
    debt_result = graph_result["debt_result"]
    st.subheader("Debt Analyzer")
    st.markdown(debt_result["narrative"])
    avalanche = debt_result["supporting_tables"].get("avalanche")
    snowball = debt_result["supporting_tables"].get("snowball")
    if avalanche:
        c1, c2 = st.columns(2)
        c1.metric("Avalanche: months to debt-free", avalanche["months_to_payoff"])
        c2.metric("Snowball: months to debt-free", snowball["months_to_payoff"])

# --- Savings -----------------------------------------------------------------
with tabs[3]:
    savings_result = graph_result["savings_result"]
    st.subheader("Savings Strategist")
    st.markdown(savings_result["narrative"])

# --- Budget --------------------------------------------------------------
with tabs[4]:
    budget_result = graph_result["budget_result"]
    st.subheader("Budget Advisor")
    st.markdown(budget_result["narrative"])

# --- Goals ---------------------------------------------------------------
with tabs[5]:
    st.subheader("Goal Planner")
    goal_results = graph_result["goal_result"]
    if not goal_results:
        st.caption("Add a goal in Step 3 to get a plan.")
    for gr in goal_results:
        goal = gr["supporting_tables"]["goal"]
        with st.container(border=True):
            st.markdown(f"**{goal['name']}** -- ${goal.get('current', 0):,.0f} / ${goal['amount']:,.0f}")
            progress = min(goal.get("current", 0) / goal["amount"], 1.0) if goal["amount"] else 0.0
            st.progress(progress)
            st.markdown(gr["narrative"])

# --- Chat ----------------------------------------------------------------------
with tabs[6]:
    st.subheader("\U0001f4ac Ask the Coach")
    st.caption("Ask about your debt, savings, budget, spending, or goals - answers are drawn from the same analysis above, not a separate agent call.")
    for role, msg in app_state.get_chat_history():
        with st.chat_message(role):
            st.markdown(msg)

    query = st.chat_input("e.g. Should I pay off my credit card or save more?")
    if query:
        app_state.append_chat("user", query)
        with st.chat_message("user"):
            st.markdown(query)
        with st.chat_message("assistant"):
            reply = build_chat_reply(query, graph_result)
            st.markdown(reply)
        app_state.append_chat("assistant", reply)

# --------------------------------------------------- Step 5: scenario preview --
st.header("Step 5 - Preview a scenario")
st.caption("Adjust an assumption to preview its effect - nothing here changes your confirmed plan until you apply it.")
with st.form("scenario_form"):
    sc1, sc2, sc3 = st.columns(3)
    preview_buffer = sc1.number_input("Preview: minimum monthly buffer ($)", min_value=0.0, value=float(constraints["minimum_monthly_buffer"]), step=50.0)
    preview_apy = sc2.number_input("Preview: savings APY (%)", min_value=0.0, value=float(assumptions["savings_apy"]) * 100, step=0.5) / 100.0
    preview_ef_months = sc3.number_input("Preview: emergency fund target (months)", min_value=0.0, value=float(assumptions["emergency_fund_months"]), step=1.0)
    preview_clicked = st.form_submit_button("Preview scenario")

if preview_clicked:
    updates = {"savings_apy": preview_apy, "emergency_fund_months": preview_ef_months}
    issues = sc.validate_assumption_updates(profile, updates)
    if issues:
        st.error("\n".join(issues))
    else:
        adjusted_profile = sc.apply_assumptions(profile, updates)
        adjusted_profile["constraints"] = {**adjusted_profile["constraints"], "minimum_monthly_buffer": preview_buffer}
        (_, adjusted_snapshot, _, _, _), _ = _run_pipeline(adjusted_profile)
        comparison = sc.compare_scenarios(snapshot, adjusted_snapshot)
        app_state.set_scenario_preview(comparison)

_SCENARIO_METRIC_LABELS = {
    "gross_surplus": "Gross surplus", "allocatable_surplus": "Allocatable surplus",
    "savings_rate_percent": "Savings rate (%)", "debt_to_income_percent": "Debt-to-income (%)",
    "emergency_fund_months": "Emergency fund (months)", "health_score": "Health score",
}

scenario_preview = app_state.get_scenario_preview()
if scenario_preview:
    preview_df = pd.DataFrame(scenario_preview).T.rename(index=_SCENARIO_METRIC_LABELS)
    preview_df.index.name = "Metric"
    st.dataframe(preview_df, width="stretch")

# --------------------------------------------------- Step 6: download --------
st.header("Step 6 - Download your report")
report_package = rp.build_report(profile, snapshot, trends, findings, risks, roadmap, coach_summary)
dl1, dl2 = st.columns(2)
dl1.download_button(
    "\U0001f4c4 Download report (Markdown)", data=report_package["report_markdown"],
    file_name=f"{report_package['filename_stem']}.md", mime="text/markdown",
)
_TRACKER_COLUMN_LABELS = {
    "month": "Month", "planned_savings": "Planned Savings ($)",
    "extra_debt_payment": "Extra Debt Payment ($)", "goal_contributions": "Goal Contributions ($)",
}
tracker_csv = pd.DataFrame(report_package["tracker_rows"]).rename(columns=_TRACKER_COLUMN_LABELS).to_csv(index=False)
dl2.download_button(
    "\U0001f4ca Download tracker (CSV)", data=tracker_csv,
    file_name=f"{report_package['filename_stem']}_tracker.csv", mime="text/csv",
)
