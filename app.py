import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agents.data_agent import DataIngestionAgent
from agents.orchestrator import OrchestratorAgent
from utils import finance_calc as fc
from utils.llm import is_live

st.set_page_config(page_title="AI Financial Coach", page_icon="\U0001f4b0", layout="wide")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

DEFAULT_DEBTS = [
    {"name": "Credit Card", "balance": 4200.0, "apr": 22.9, "min_payment": 120.0},
    {"name": "Student Loan", "balance": 18500.0, "apr": 5.8, "min_payment": 210.0},
    {"name": "Auto Loan", "balance": 9800.0, "apr": 6.5, "min_payment": 260.0},
]

DEFAULT_GOALS = [
    {"name": "Emergency Fund Boost", "amount": 3000.0, "months": 6, "current": 500.0},
    {"name": "Hawaii Vacation", "amount": 4000.0, "months": 10, "current": 200.0},
]


@st.cache_resource
def get_orchestrator():
    return OrchestratorAgent()


@st.cache_data
def load_sample_transactions():
    df = pd.read_csv(os.path.join(DATA_DIR, "sample_transactions.csv"))
    df["date"] = pd.to_datetime(df["date"])
    return df


for key, default in [
    ("transactions", None),
    ("debts", DEFAULT_DEBTS.copy()),
    ("goals", DEFAULT_GOALS.copy()),
    ("monthly_income", 6200.0),
    ("current_savings", 2500.0),
    ("chat_history", []),
    ("report", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

orchestrator = get_orchestrator()
ingest_agent = DataIngestionAgent()

# ---------------------------------------------------------------- sidebar --
with st.sidebar:
    st.title("\U0001f4b0 AI Financial Coach")
    st.caption("A multi-agent financial advisor")
    st.markdown(f"**LLM status:** {'\U0001f7e2 Connected via OpenRouter' if is_live() else '\U0001f7e1 Offline mode (rule-based fallback)'}")
    if not is_live():
        st.caption("Set OPENROUTER_API_KEY in .env to enable full LLM-generated narratives.")

    st.divider()
    st.subheader("1. Your data")
    uploaded = st.file_uploader("Upload transactions (CSV or PDF)", type=["csv", "pdf"])
    if uploaded is not None:
        try:
            st.session_state.transactions = ingest_agent.load(uploaded)
            st.session_state.report = None
            st.success(f"Loaded {len(st.session_state.transactions)} transactions.")
        except Exception as e:
            st.error(str(e))

    if st.button("Load sample data", use_container_width=True):
        st.session_state.transactions = load_sample_transactions()
        st.session_state.debts = DEFAULT_DEBTS.copy()
        st.session_state.goals = DEFAULT_GOALS.copy()
        st.session_state.report = None
        st.success("Sample data loaded.")

    st.session_state.monthly_income = st.number_input(
        "Monthly income ($)", min_value=0.0, value=float(st.session_state.monthly_income), step=100.0
    )
    st.session_state.current_savings = st.number_input(
        "Current savings ($)", min_value=0.0, value=float(st.session_state.current_savings), step=100.0
    )

    st.divider()
    st.subheader("2. Debts")
    with st.expander("Edit debts", expanded=False):
        debts_df = pd.DataFrame(st.session_state.debts)
        edited = st.data_editor(debts_df, num_rows="dynamic", use_container_width=True, key="debts_editor")
        st.session_state.debts = edited.dropna().to_dict("records")

    st.subheader("3. Goals")
    with st.expander("Edit goals", expanded=False):
        goals_df = pd.DataFrame(st.session_state.goals)
        edited_g = st.data_editor(goals_df, num_rows="dynamic", use_container_width=True, key="goals_editor")
        st.session_state.goals = edited_g.dropna().to_dict("records")

    st.divider()
    run_clicked = st.button("\U0001f680 Run full agent analysis", type="primary", use_container_width=True)

# ------------------------------------------------------------------- main --
if st.session_state.transactions is None:
    st.info("\U0001f448 Load sample data or upload a transactions file in the sidebar to get started.")
    st.caption(
        "CSV format: columns `date`, `description`, `amount` -- expenses negative, "
        "income/deposits positive."
    )
    st.stop()

df = fc.categorize_transactions(st.session_state.transactions)


def build_context():
    return {
        "transactions": df,
        "monthly_income": st.session_state.monthly_income,
        "current_savings": st.session_state.current_savings,
        "debts": st.session_state.debts,
        "goals": st.session_state.goals,
    }


if run_clicked or st.session_state.report is None:
    with st.spinner("Orchestrator is dispatching specialist agents..."):
        st.session_state.report = orchestrator.run_full_report(build_context())

report = st.session_state.report

tabs = st.tabs(
    ["\U0001f4ca Overview", "\U0001f9fe Spending", "\U0001f4b3 Debt Payoff", "\U0001f3e6 Savings",
     "\U0001f4cb Budget", "\U0001f3af Goals", "\U0001f4ac Ask the Coach"]
)

# --- Overview ---------------------------------------------------------------
with tabs[0]:
    monthly = fc.monthly_cashflow(df)
    avg_exp = monthly["expenses"].mean() if not monthly.empty else 0
    total_debt = sum(d["balance"] for d in st.session_state.debts)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Monthly income", f"${st.session_state.monthly_income:,.0f}")
    c2.metric("Avg monthly expenses", f"${avg_exp:,.0f}")
    c3.metric("Total debt", f"${total_debt:,.0f}")
    c4.metric("Current savings", f"${st.session_state.current_savings:,.0f}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Cash flow by month")
        fig = go.Figure()
        fig.add_bar(x=monthly["month"], y=monthly["income"], name="Income")
        fig.add_bar(x=monthly["month"], y=monthly["expenses"], name="Expenses")
        fig.update_layout(barmode="group", height=350)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.subheader("Spending by category")
        by_cat = fc.spending_by_category(df)
        fig2 = px.pie(by_cat, names="category", values="amount", hole=0.4)
        fig2.update_layout(height=350)
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("\U0001f9ed Coach summary")
    for key in ["spending", "debt", "savings", "budget"]:
        st.markdown(report[key]["narrative"])
        st.markdown("---")

# --- Spending -----------------------------------------------------------
with tabs[1]:
    st.subheader("Spending Analyzer Agent")
    st.markdown(report["spending"]["narrative"])
    by_cat = report["spending"]["by_category"]
    st.bar_chart(by_cat.set_index("category"))
    st.subheader("Month-over-month trends")
    trends = report["spending"]["trends"]
    if not trends.empty:
        st.dataframe(trends, use_container_width=True)
    else:
        st.caption("Not enough months of history to compute trends yet.")
    st.subheader("Raw transactions")
    st.dataframe(df.sort_values("date", ascending=False), use_container_width=True)

# --- Debt -----------------------------------------------------------------
with tabs[2]:
    st.subheader("Debt Analyzer Agent")
    st.markdown(report["debt"]["narrative"])
    ava, sno = report["debt"]["avalanche"], report["debt"]["snowball"]
    if ava:
        c1, c2 = st.columns(2)
        c1.metric("Avalanche: months to debt-free", ava["months_to_payoff"])
        c1.metric("Avalanche: total interest", f"${ava['total_interest']:,.0f}")
        c2.metric("Snowball: months to debt-free", sno["months_to_payoff"])
        c2.metric("Snowball: total interest", f"${sno['total_interest']:,.0f}")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[t["month"] for t in ava["timeline"]], y=[t["total_balance"] for t in ava["timeline"]],
            name="Avalanche",
        ))
        fig.add_trace(go.Scatter(
            x=[t["month"] for t in sno["timeline"]], y=[t["total_balance"] for t in sno["timeline"]],
            name="Snowball",
        ))
        fig.update_layout(title="Total debt balance over time", xaxis_title="Month", yaxis_title="Balance ($)", height=400)
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            f"Payoff order -- Avalanche: {' → '.join(ava['payoff_order'])} | "
            f"Snowball: {' → '.join(sno['payoff_order'])}"
        )

# --- Savings ----------------------------------------------------------------
with tabs[3]:
    st.subheader("Savings Strategy Agent")
    st.markdown(report["savings"]["narrative"])
    lo, hi = report["savings"]["emergency_fund_target"]
    progress = min(st.session_state.current_savings / hi, 1.0) if hi else 0.0
    st.progress(progress, text=f"Emergency fund progress toward ${hi:,.0f}")
    proj = report["savings"]["projection"]
    fig = px.line(pd.DataFrame(proj), x="month", y="balance", title="Projected savings growth (24 months)")
    st.plotly_chart(fig, use_container_width=True)

# --- Budget -------------------------------------------------------------
with tabs[4]:
    st.subheader("Budget Advisor Agent")
    st.markdown(report["budget"]["narrative"])
    rec, act = report["budget"]["recommended"], report["budget"]["actual"]
    comp_df = pd.DataFrame({
        "bucket": list(rec.keys()),
        "recommended": list(rec.values()),
        "actual": [act.get(k, 0) for k in rec],
    })
    fig = go.Figure()
    fig.add_bar(x=comp_df["bucket"], y=comp_df["recommended"], name="Recommended")
    fig.add_bar(x=comp_df["bucket"], y=comp_df["actual"], name="Actual")
    fig.update_layout(barmode="group", height=350)
    st.plotly_chart(fig, use_container_width=True)

# --- Goals ----------------------------------------------------------------
with tabs[5]:
    st.subheader("Goal Planner Agent")
    goals_result = report.get("goals", {}).get("goals", [])
    if not goals_result:
        st.caption("Add a goal in the sidebar to get a plan.")
    for g in goals_result:
        with st.container(border=True):
            st.markdown(f"**{g['name']}** -- ${g['current']:,.0f} / ${g['amount']:,.0f}")
            progress = min(g["current"] / g["amount"], 1.0) if g["amount"] else 0.0
            st.progress(progress)
            st.markdown(g["narrative"])

# --- Chat -------------------------------------------------------------------
with tabs[6]:
    st.subheader("\U0001f4ac Ask the Coach")
    st.caption(
        "Ask about your debt, savings, budget, spending, or goals -- the orchestrator "
        "routes your question to the right specialist agent(s)."
    )
    for role, msg in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(msg)

    query = st.chat_input("e.g. Should I pay off my credit card or save more?")
    if query:
        st.session_state.chat_history.append(("user", query))
        with st.chat_message("user"):
            st.markdown(query)
        with st.chat_message("assistant"):
            with st.spinner("Routing to specialist agent(s)..."):
                reply = orchestrator.route_chat(query, build_context())
            st.markdown(reply)
        st.session_state.chat_history.append(("assistant", reply))
