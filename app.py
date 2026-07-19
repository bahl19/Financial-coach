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
    {"name": "Credit Card", "balance": 45000.0, "apr": 36.0, "min_payment": 3500.0},
    {"name": "Car Loan", "balance": 150000.0, "apr": 9.5, "min_payment": 4200.0},
]

_DEBT_COLUMN_HELP = {
    "name": "What you're calling this debt - shown in the payoff plan and roadmap.",
    "balance": "The total amount you currently owe on this debt.",
    "apr": "Annual Percentage Rate - the yearly interest cost on the outstanding balance. "
           "Higher-APR debt is prioritized for extra payments.",
    "min_payment": "The minimum monthly payment required to keep this debt current.",
}
_GOAL_COLUMN_HELP = {
    "name": "What you're saving toward - shown in the roadmap and goal tracker.",
    "amount": "The total amount you need to reach this goal.",
    "months": "How many months you want to reach it in - a shorter timeline needs a higher monthly contribution.",
    "current": "How much you've already saved toward this specific goal.",
    "priority": "high/medium/low - when surplus is tight, higher-priority goals are funded first.",
}

DEFAULT_GOALS = [
    {"name": "Emergency Fund Boost", "amount": 75000.0, "months": 6, "current": 15000.0, "priority": "high"},
    {"name": "Vacation", "amount": 100000.0, "months": 10, "current": 10000.0, "priority": "medium"},
]

@st.cache_data
def load_sample_transactions() -> pd.DataFrame:
    df = pd.read_csv(os.path.join(DATA_DIR, "sample_transactions.csv"))
    df["date"] = pd.to_datetime(df["date"])
    return df


def _suggest_monthly_income(categorized_df: pd.DataFrame):
    """A starting point for Step 3's income field, not a substitute for
    confirming it: the average observed monthly income (via the same
    monthly_cashflow() aggregation the rest of the app already uses) is a
    more robust point estimate than any single transaction - a salary that
    varies slightly month to month, or one atypical month, does not swing
    the suggestion the way "just the most recent transaction" would. The
    user still edits/confirms a number already grounded in their own data
    instead of typing one from scratch that might silently disagree with it.

    `current_savings` gets no equivalent suggestion - a transaction ledger
    has no concept of a current account balance (only cash movements over
    the uploaded window), so there is nothing honest to derive it from;
    inventing one would violate "unknown data is None, never a fabricated
    number." That field stays user-entered only."""
    if categorized_df.empty:
        return None
    monthly = fc.monthly_cashflow(categorized_df)
    if monthly.empty or not (monthly["income"] > 0).any():
        return None
    return float(monthly["income"].mean())


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
        "confirmed_monthly_expenses": fields["confirmed_monthly_expenses"],
        "current_savings": fields["current_savings"],
        "current_investments": fields["current_investments"],
        "debts": fields["debts"],
        "goals": fields["goals"],
        "constraints": fields["constraints"],
        "assumptions": fields["assumptions"] or default_assumptions(),
    }


def _suggest_average_monthly_expenses(categorized_df: pd.DataFrame) -> float:
    """Step 3's expenses pre-fill: the same transaction-derived average
    `calculate_financial_snapshot()` would use if the user never touched
    this field. Unlike current_savings, an "average monthly expenses"
    figure genuinely is computable from the transaction history alone -
    this suggestion is a starting point the user confirms or overrides,
    exactly like the income suggestion above."""
    if categorized_df.empty:
        return 0.0
    monthly = fc.monthly_cashflow(categorized_df)
    return float(monthly["expenses"].mean()) if not monthly.empty else 0.0


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
            "amount": st.column_config.NumberColumn(disabled=True, format="₹%.2f"),
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

income_suggestion = _suggest_monthly_income(working_df)
expense_suggestion = _suggest_average_monthly_expenses(working_df)
# Only substitutes a suggestion when nothing has been confirmed yet - once
# a field is set (by the user, on any earlier rerun), that confirmed value
# always wins over a freshly recomputed suggestion.
income_default = fields["monthly_income"] if fields["monthly_income"] is not None else (income_suggestion or 0.0)
expenses_default = (
    fields["confirmed_monthly_expenses"] if fields["confirmed_monthly_expenses"] is not None else expense_suggestion
)

st.subheader("Income & expenses")
col1, col2 = st.columns(2)
monthly_income = col1.number_input(
    "Monthly income (₹)", min_value=0.0, value=float(income_default), step=100.0, key="monthly_income_input",
    help=(
        f"Pre-filled from your average observed monthly income (₹{income_suggestion:,.0f}) in the uploaded "
        "data - confirm or adjust if that's not representative." if income_suggestion is not None
        else "No income transaction found in the uploaded data - enter this manually."
    ),
)
confirmed_monthly_expenses = col2.number_input(
    "Monthly expenses (₹)", min_value=0.0, value=float(expenses_default), step=100.0, key="expenses_input",
    help=(
        f"Pre-filled from your average observed monthly spending (₹{expense_suggestion:,.0f}) in the uploaded "
        "data - confirm or adjust if a month here wasn't typical. This figure replaces the transaction-derived "
        "average everywhere in the analysis once confirmed."
    ),
)

st.subheader("Savings")
col3, col4 = st.columns(2)
current_savings = col3.number_input(
    "Current savings balance (₹)", min_value=0.0, value=float(fields["current_savings"] or 0.0), step=100.0,
    key="current_savings_input",
    help="Your current balance isn't in the transaction history (it only shows cash movements, not an account "
         "balance) - this is always entered manually.",
)
savings_apy = col4.number_input(
    "Interest rate you're currently earning on it (% APY)", min_value=0.0,
    value=float(current_assumptions.get("savings_apy", 0.04)) * 100, step=0.25, key="apy_input",
    help="The annual interest rate your savings account currently pays - used to project how this balance grows.",
) / 100.0

st.subheader("Investments")
col5, col6 = st.columns(2)
current_investments = col5.number_input(
    "Current investment total (₹)", min_value=0.0, value=float(fields["current_investments"] or 0.0), step=100.0,
    key="current_investments_input",
    help="Combined current value of mutual funds, stocks, PPF, FDs held as investments, etc. - separate from your "
         "savings account balance above.",
)
investment_cagr_input = col6.number_input(
    "CAGR you're presently earning (%)", min_value=0.0,
    value=(float(current_assumptions.get("investment_cagr") or 0.0) * 100), step=0.25, key="investment_cagr_input",
    help="Your investments' compound annual growth rate. When this clears your savings APY by a meaningful margin, "
         "the roadmap routes further surplus toward investment contribution instead of plain savings.",
)
investment_cagr = (investment_cagr_input / 100.0) if current_investments > 0 else None

st.subheader("Debts")
debts_df = pd.DataFrame(fields["debts"] or DEFAULT_DEBTS)
edited_debts = st.data_editor(
    debts_df, num_rows="dynamic", width="stretch", key="debts_editor",
    column_config={
        col: st.column_config.Column(help=help_text) for col, help_text in _DEBT_COLUMN_HELP.items()
    },
)
debts = edited_debts.dropna().to_dict("records")

st.subheader("Goals")
goals_df = pd.DataFrame(fields["goals"] or DEFAULT_GOALS)
edited_goals = st.data_editor(
    goals_df, num_rows="dynamic", width="stretch", key="goals_editor",
    column_config={
        col: st.column_config.Column(help=help_text) for col, help_text in _GOAL_COLUMN_HELP.items()
    },
)
goals = edited_goals.dropna().to_dict("records")

# minimum_monthly_buffer and emergency_fund_months (target) are no longer
# confirmed here - they live in the Scenario Comparison section below the
# tabs (Step 5) as "preview, then apply" controls instead of an upfront ask.
assumptions = {**current_assumptions, "savings_apy": savings_apy, "investment_cagr": investment_cagr}
constraints = fields["constraints"] or {"minimum_monthly_buffer": 0.0, "protected_categories": []}

app_state.set_profile_fields(
    # monthly_income also drives the "required inputs" gate below - a
    # widget-default 0.0 is treated as "not yet entered" there. current_savings
    # has no such gate: a literal, deliberate (or default/untouched) ₹0 is a
    # real, computable answer, and collapsing it to None would silently turn
    # emergency_fund_months into "unknown" for a user who genuinely has no
    # savings - the exact "a real zero must not become None" failure mode
    # Phase 11's rehearsal exists to catch. confirmed_monthly_expenses and
    # current_investments follow the same "a real zero is real" reasoning.
    monthly_income=monthly_income or None, current_savings=current_savings,
    confirmed_monthly_expenses=confirmed_monthly_expenses, current_investments=current_investments or None,
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
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Health score", f"{snapshot['health_score']}/100", snapshot["health_band"])
    c2.metric("Gross surplus", f"₹{metrics['gross_surplus']:,.0f}" if metrics.get("gross_surplus") is not None else "unknown")
    c3.metric("Allocatable surplus", f"₹{metrics['allocatable_surplus']:,.0f}" if metrics.get("allocatable_surplus") is not None else "unknown")
    c4.metric("Total debt", f"₹{metrics['total_debt']:,.0f}")
    c5.metric("Net worth", f"₹{metrics['net_worth']:,.0f}" if metrics.get("net_worth") is not None else "unknown")

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
        f"₹{roadmap['allocation']['buffer_reserved']:,.2f}"
    )
    for action in sorted(roadmap["actions"], key=lambda a: a["priority"]):
        icon = _SEVERITY_ICON.get(action["severity"], "")
        st.markdown(
            f"{action['priority']}. {icon} **{action['title']}** ({action['timeframe']}): ₹{action['monthly_amount']:,.2f}/mo"
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
            st.markdown(f"**{goal['name']}** -- ₹{goal.get('current', 0):,.0f} / ₹{goal['amount']:,.0f}")
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

# --------------------------------------------------- Step 5: scenario comparison --
# A single section below the tabs - never duplicated into the Overview or
# any specialist tab. Nothing here commits until Step 3's confirmed values
# are re-entered and Step 4 is re-run; every comparison below is a
# read-only "what if," built from utils.finance_calc/utils.scenarios
# functions this app already trusts (simulate_payoff, savings_projection,
# required_monthly_contribution_with_growth, compare_scenarios) - no new
# modeling, no LLM involved anywhere in this section.
st.header("Step 5 - Compare scenarios")
st.caption("Explore what-if changes to your plan. Nothing here changes your confirmed plan above.")

_PRESET_RATES = (("Fixed Deposit (FD)", 0.065), ("PPF", 0.071), ("Equity SIP (illustrative)", 0.12))
_SCENARIO_METRIC_LABELS = {
    "gross_surplus": "Gross surplus", "allocatable_surplus": "Allocatable surplus",
    "savings_rate_percent": "Savings rate (%)", "debt_to_income_percent": "Debt-to-income (%)",
    "emergency_fund_months": "Emergency fund (months)", "health_score": "Health score",
}

scenario_tabs = st.tabs([
    "Plan assumptions", "Idle savings vs. investing", "Cut discretionary spending",
    "Prepay debt vs. invest", "FD / PPF / SIP for a goal",
])

# --- Plan assumptions (buffer + emergency fund target - moved off Step 3) ---
with scenario_tabs[0]:
    st.caption("Adjust the buffer or emergency fund target to preview its effect on the plan.")
    with st.form("scenario_form"):
        sc1, sc2 = st.columns(2)
        preview_buffer = sc1.number_input(
            "Preview: minimum monthly buffer (₹)", min_value=0.0,
            value=float(constraints["minimum_monthly_buffer"]), step=50.0,
        )
        preview_ef_months = sc2.number_input(
            "Preview: emergency fund target (months)", min_value=0.0,
            value=float(assumptions["emergency_fund_months"]), step=1.0,
        )
        preview_clicked = st.form_submit_button("Preview scenario")

    if preview_clicked:
        issues = sc.validate_assumption_updates(profile, {"emergency_fund_months": preview_ef_months})
        if issues:
            st.error("\n".join(issues))
        else:
            adjusted_profile = sc.apply_assumptions(profile, {"emergency_fund_months": preview_ef_months})
            adjusted_profile["constraints"] = {**adjusted_profile["constraints"], "minimum_monthly_buffer": preview_buffer}
            (_, adjusted_snapshot, _, _, _), _ = _run_pipeline(adjusted_profile)
            comparison = sc.compare_scenarios(snapshot, adjusted_snapshot)
            app_state.set_scenario_preview(comparison)

    scenario_preview = app_state.get_scenario_preview()
    if scenario_preview:
        preview_df = pd.DataFrame(scenario_preview).T.rename(index=_SCENARIO_METRIC_LABELS)
        preview_df.index.name = "Metric"
        st.dataframe(preview_df, width="stretch")

# --- Idle savings vs. investing it ---
with scenario_tabs[1]:
    st.caption("Compare leaving an amount in savings versus moving it into your investments, at your confirmed rates.")
    ic1, ic2, ic3 = st.columns(3)
    idle_amount = ic1.number_input(
        "Amount to compare (₹)", min_value=0.0, value=float(current_savings), step=1000.0, key="idle_amount_input",
    )
    idle_horizon_years = ic2.number_input("Over how many years?", min_value=1, value=5, step=1, key="idle_horizon_input")
    idle_cagr_pct = ic3.number_input(
        "Investment CAGR to compare against (%)", min_value=0.0,
        value=(investment_cagr * 100) if investment_cagr else 12.0, step=0.5, key="idle_cagr_input",
    )
    if idle_amount > 0:
        horizon_months = int(idle_horizon_years * 12)
        savings_outcome = fc.savings_projection(idle_amount, 0.0, months=horizon_months, apr=savings_apy)
        investment_outcome = fc.savings_projection(idle_amount, 0.0, months=horizon_months, apr=idle_cagr_pct / 100.0)
        oc1, oc2 = st.columns(2)
        oc1.metric(f"Staying in savings ({savings_apy * 100:.1f}% APY)", f"₹{savings_outcome[-1]['balance']:,.0f}")
        oc2.metric(f"Moved to investment ({idle_cagr_pct:.1f}% CAGR)", f"₹{investment_outcome[-1]['balance']:,.0f}")
        st.caption(f"Difference over {idle_horizon_years:.0f} year(s): ₹{investment_outcome[-1]['balance'] - savings_outcome[-1]['balance']:,.0f}")

# --- Cut discretionary spending by X% ---
with scenario_tabs[2]:
    st.caption("Preview the effect of cutting discretionary (non-essential, non-savings) spending.")
    wants_categories = {
        t["category"] for t in profile["transactions"]
        if t["category"] not in fc.NEEDS_CATS and t["category"] not in fc.SAVINGS_CATS and t["category"] != "Income"
    }
    if not wants_categories:
        st.caption("No discretionary categories found in your transaction history.")
    else:
        cut_percent = st.slider("Cut discretionary spending by:", min_value=0, max_value=50, value=10, step=5, format="%d%%")
        st.caption(f"Categories treated as discretionary: {', '.join(sorted(wants_categories))}")
        if cut_percent > 0:
            reduced_profile = sc.apply_expense_reduction(profile, wants_categories, reduction_fraction=cut_percent / 100.0)
            # A confirmed_monthly_expenses override reflects the *actual*
            # (pre-cut) spending pattern - left in place, it would shadow
            # every transaction change this scenario just made, and the
            # comparison would show zero effect no matter the cut. Clearing
            # it lets the reduced transactions' own average through, which
            # is what "if I cut spending" should actually show.
            reduced_profile["confirmed_monthly_expenses"] = None
            (_, reduced_snapshot, _, _, _), _ = _run_pipeline(reduced_profile)
            comparison = sc.compare_scenarios(snapshot, reduced_snapshot)
            preview_df = pd.DataFrame(comparison).T.rename(index=_SCENARIO_METRIC_LABELS)
            preview_df.index.name = "Metric"
            st.dataframe(preview_df, width="stretch")

# --- Prepay debt vs. invest the surplus ---
with scenario_tabs[3]:
    st.caption("Compare paying extra toward debt against investing the same amount instead.")
    if not profile["debts"]:
        st.caption("No debts on file - nothing to compare here.")
    else:
        pc1, pc2 = st.columns(2)
        prepay_amount = pc1.number_input(
            "Extra monthly amount to compare (₹)", min_value=0.0,
            value=float(roadmap["allocation"]["debt_extra_payment"] or 500.0), step=100.0, key="prepay_amount_input",
        )
        prepay_strategy = pc2.selectbox("Payoff strategy", ["avalanche", "snowball"], key="prepay_strategy_input")
        prepay_cagr_pct = st.number_input(
            "Investment CAGR to compare against (%)", min_value=0.0,
            value=(investment_cagr * 100) if investment_cagr else 12.0, step=0.5, key="prepay_cagr_input",
        )
        if prepay_amount > 0:
            with_extra = fc.simulate_payoff(profile["debts"], extra_monthly=prepay_amount, strategy=prepay_strategy)
            baseline = fc.simulate_payoff(profile["debts"], extra_monthly=0.0, strategy=prepay_strategy)
            interest_saved = baseline["total_interest"] - with_extra["total_interest"]
            invested_instead = fc.savings_projection(0.0, prepay_amount, months=with_extra["months_to_payoff"], apr=prepay_cagr_pct / 100.0)
            pc3, pc4 = st.columns(2)
            pc3.metric(
                f"Prepay debt ({with_extra['months_to_payoff']} months to debt-free)",
                f"₹{interest_saved:,.0f} interest saved",
            )
            pc4.metric(
                f"Invest instead over the same {with_extra['months_to_payoff']} months ({prepay_cagr_pct:.1f}% CAGR)",
                f"₹{invested_instead[-1]['balance']:,.0f}",
            )

# --- FD vs PPF vs Equity SIP for a goal ---
with scenario_tabs[4]:
    st.caption("Compare the monthly contribution required to reach a goal at a few common Indian rate benchmarks.")
    if not profile["goals"]:
        st.caption("Add a goal in Step 3 to compare rates for it.")
    else:
        goal_names = [g["name"] for g in profile["goals"]]
        selected_goal_name = st.selectbox("Goal", goal_names, key="goal_rate_compare_input")
        selected_goal = next(g for g in profile["goals"] if g["name"] == selected_goal_name)
        rate_rows = [
            {
                "Option": label,
                "Rate": f"{rate * 100:.1f}%",
                "Required monthly contribution": fc.required_monthly_contribution_with_growth(
                    selected_goal["amount"], selected_goal["months"], selected_goal.get("current", 0.0), rate,
                ),
            }
            for label, rate in _PRESET_RATES
        ]
        rate_df = pd.DataFrame(rate_rows)
        rate_df["Required monthly contribution"] = rate_df["Required monthly contribution"].map(lambda v: f"₹{v:,.0f}")
        st.dataframe(rate_df, width="stretch", hide_index=True)
        st.caption("These rates are illustrative benchmarks, not a recommendation or a guarantee of future returns.")

# --------------------------------------------------- Step 6: download --------
st.header("Step 6 - Download your report")
report_package = rp.build_report(profile, snapshot, trends, findings, risks, roadmap, coach_summary)
dl1, dl2 = st.columns(2)
dl1.download_button(
    "\U0001f4c4 Download report (Markdown)", data=report_package["report_markdown"],
    file_name=f"{report_package['filename_stem']}.md", mime="text/markdown",
)
_TRACKER_COLUMN_LABELS = {
    "month": "Month", "planned_savings": "Planned Savings (₹)",
    "extra_debt_payment": "Extra Debt Payment (₹)", "goal_contributions": "Goal Contributions (₹)",
}
tracker_csv = pd.DataFrame(report_package["tracker_rows"]).rename(columns=_TRACKER_COLUMN_LABELS).to_csv(index=False)
dl2.download_button(
    "\U0001f4ca Download tracker (CSV)", data=tracker_csv,
    file_name=f"{report_package['filename_stem']}_tracker.csv", mime="text/csv",
)
