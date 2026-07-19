"""Phase 3 tests: the five refactored specialist agents.

Each test maps to a Phase 3 exit-gate item concerning structured specialist
output and the double-allocation fix itself.
"""

import re
from pathlib import Path

import pandas as pd

from agents.budget_agent import BudgetAdvisorAgent
from agents.debt_agent import DebtAnalyzerAgent
from agents.goal_agent import GoalPlannerAgent
from agents.savings_agent import SavingsStrategyAgent
from agents.spending_agent import SpendingAnalyzerAgent
from utils import finance_calc as fc

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_SPECIALIST_RESULT_KEYS = {
    "schema_version", "agent", "narrative", "allocated_amount", "why_allocated",
    "expected_effect", "tradeoffs", "what_to_monitor", "finding_refs", "trend_refs",
    "recommends_action_ids", "supporting_tables", "live",
}


def _transactions_df(rows):
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


SAMPLE_TRANSACTIONS = _transactions_df([
    {"date": "2026-03-01", "description": "Employer Payroll", "amount": 6000.0, "category": "Income"},
    {"date": "2026-03-05", "description": "Whole Foods", "amount": -400.0, "category": "Groceries"},
    {"date": "2026-04-01", "description": "Employer Payroll", "amount": 6000.0, "category": "Income"},
    {"date": "2026-04-05", "description": "Whole Foods", "amount": -420.0, "category": "Groceries"},
])


# --------------------------------------------------------------------------
# Gate: "Every specialist returns a complete SpecialistResult"
# --------------------------------------------------------------------------

def test_spending_agent_returns_a_complete_specialist_result():
    result = SpendingAnalyzerAgent().run(transactions=SAMPLE_TRANSACTIONS)
    assert REQUIRED_SPECIALIST_RESULT_KEYS.issubset(result.keys())
    assert result["allocated_amount"] is None  # spending does not allocate money


def test_budget_agent_returns_a_complete_specialist_result():
    by_cat = fc.spending_by_category(SAMPLE_TRANSACTIONS)
    monthly = fc.monthly_cashflow(SAMPLE_TRANSACTIONS)
    result = BudgetAdvisorAgent().run(by_category=by_cat, monthly_cashflow=monthly, monthly_income=6000.0)
    assert REQUIRED_SPECIALIST_RESULT_KEYS.issubset(result.keys())
    assert result["allocated_amount"] is None  # budget does not allocate money


def test_debt_agent_returns_a_complete_specialist_result():
    debts = [{"name": "Card", "balance": 3000.0, "apr": 22.0, "min_payment": 100.0}]
    result = DebtAnalyzerAgent().run(
        debts=debts, extra_debt_payment=250.0, action_id="ACTION_ACCELERATE_DEBT",
        finding_refs=["FINDING_HIGH_DEBT_BURDEN"], trend_refs=[],
    )
    assert REQUIRED_SPECIALIST_RESULT_KEYS.issubset(result.keys())


def test_savings_agent_returns_a_complete_specialist_result():
    monthly = fc.monthly_cashflow(SAMPLE_TRANSACTIONS)
    result = SavingsStrategyAgent().run(
        monthly_cashflow=monthly, current_savings=2000.0, savings_contribution=500.0,
        action_id="ACTION_GROW_SAVINGS", finding_refs=[], trend_refs=[],
    )
    assert REQUIRED_SPECIALIST_RESULT_KEYS.issubset(result.keys())


def test_goal_agent_returns_a_list_of_complete_specialist_results():
    goals = [{"name": "Vacation", "amount": 2000.0, "months": 4, "current": 200.0, "priority": "high"}]
    results = GoalPlannerAgent().run(
        goals=goals, goal_contributions={"Vacation": 300.0},
        action_ids_by_goal={"Vacation": "ACTION_FUND_GOAL_VACATION"},
    )
    assert isinstance(results, list)
    assert len(results) == 1
    assert REQUIRED_SPECIALIST_RESULT_KEYS.issubset(results[0].keys())


def test_goal_agent_returns_empty_list_for_no_goals():
    assert GoalPlannerAgent().run(goals=[], goal_contributions={}) == []


# --------------------------------------------------------------------------
# Gate: "allocated_amount is copied from roadmap.allocation, never
# computed locally" / "debt, savings, and goal quote the exact dollar
# figures in roadmap.allocation"
# --------------------------------------------------------------------------

def test_debt_agent_allocated_amount_exactly_matches_what_it_was_given():
    debts = [{"name": "Card", "balance": 3000.0, "apr": 22.0, "min_payment": 100.0}]
    given_amount = 733.21  # an arbitrary, non-round number - if the agent
    # were still computing its own share (e.g. surplus * 0.3), this exact
    # figure could never appear in its output by coincidence.
    result = DebtAnalyzerAgent().run(debts=debts, extra_debt_payment=given_amount, action_id="X")
    assert result["allocated_amount"] == given_amount
    assert f"{given_amount:,.0f}" in result["narrative"]


def test_savings_agent_allocated_amount_exactly_matches_what_it_was_given():
    monthly = fc.monthly_cashflow(SAMPLE_TRANSACTIONS)
    given_amount = 611.47
    result = SavingsStrategyAgent().run(
        monthly_cashflow=monthly, current_savings=1000.0, savings_contribution=given_amount, action_id="X",
    )
    assert result["allocated_amount"] == given_amount
    assert f"{given_amount:,.0f}" in result["narrative"]


# --------------------------------------------------------------------------
# Bug found while adding investment tracking: savings_projection() was
# always called without `apr`, silently defaulting to 4% and ignoring
# whatever savings_apy the user actually confirmed.
# --------------------------------------------------------------------------

def test_savings_agent_uses_the_confirmed_apy_not_a_hardcoded_default():
    monthly = fc.monthly_cashflow(SAMPLE_TRANSACTIONS)
    result_low_apy = SavingsStrategyAgent().run(
        monthly_cashflow=monthly, current_savings=1000.0, savings_contribution=500.0, savings_apy=0.01,
    )
    result_high_apy = SavingsStrategyAgent().run(
        monthly_cashflow=monthly, current_savings=1000.0, savings_contribution=500.0, savings_apy=0.10,
    )
    low_projection = result_low_apy["supporting_tables"]["projection"]
    high_projection = result_high_apy["supporting_tables"]["projection"]
    assert high_projection[-1]["balance"] > low_projection[-1]["balance"]
    assert "1.0%" in result_low_apy["narrative"]
    assert "10.0%" in result_high_apy["narrative"]


def test_savings_agent_narrates_investment_contribution_when_present():
    monthly = fc.monthly_cashflow(SAMPLE_TRANSACTIONS)
    result = SavingsStrategyAgent().run(
        monthly_cashflow=monthly, current_savings=1000.0, savings_contribution=0.0, savings_apy=0.04,
        investment_contribution=750.0, current_investments=20_000.0, investment_cagr=0.12,
        action_id="ACTION_GROW_INVESTMENT",
    )
    assert result["allocated_amount"] == 750.0  # savings_contribution(0) + investment_contribution(750)
    assert "750" in result["narrative"]
    assert "12.0%" in result["narrative"]
    assert result["supporting_tables"]["investment_projection"] is not None


def test_savings_agent_omits_investment_projection_when_investment_contribution_is_zero():
    monthly = fc.monthly_cashflow(SAMPLE_TRANSACTIONS)
    result = SavingsStrategyAgent().run(
        monthly_cashflow=monthly, current_savings=1000.0, savings_contribution=500.0,
    )
    assert result["supporting_tables"]["investment_projection"] is None
    assert "CAGR" not in result["narrative"]


def test_savings_agent_fallback_narrative_reports_investment_when_present():
    monthly = fc.monthly_cashflow(SAMPLE_TRANSACTIONS)
    agent = SavingsStrategyAgent()
    result = agent.run(
        monthly_cashflow=monthly, current_savings=1000.0, savings_contribution=200.0,
        investment_contribution=300.0, current_investments=10_000.0, investment_cagr=0.10,
    )
    fallback = agent._fallback_narrative(result)
    assert "investment" in fallback.lower()
    assert "300" in fallback


def test_goal_agent_allocated_amount_exactly_matches_what_it_was_given():
    goals = [{"name": "Car", "amount": 5000.0, "months": 10, "current": 0.0, "priority": "medium"}]
    given_amount = 288.19
    results = GoalPlannerAgent().run(goals=goals, goal_contributions={"Car": given_amount})
    assert results[0]["allocated_amount"] == given_amount


def test_goal_missing_from_contributions_gets_exactly_zero_not_a_guess():
    goals = [{"name": "Unfunded Goal", "amount": 5000.0, "months": 10, "current": 0.0, "priority": "low"}]
    results = GoalPlannerAgent().run(goals=goals, goal_contributions={})  # not present at all
    assert results[0]["allocated_amount"] == 0.0


# --------------------------------------------------------------------------
# Gate: "No debts on file" path skips the LLM call entirely (base class's
# summary_text=None short-circuit) and never crashes
# --------------------------------------------------------------------------

def test_debt_agent_with_no_debts_returns_debt_free_message_without_an_llm_call():
    result = DebtAnalyzerAgent().run(debts=[], extra_debt_payment=0.0)
    assert "debt-free" in result["narrative"].lower()
    assert result["live"] is False
    # allocated_amount is 0.0, not None: roadmap.allocation["debt_extra_payment"]
    # is always a concrete float, and debt is an allocating agent (unlike
    # spending/budget, which never allocate and so are legitimately None).
    assert result["allocated_amount"] == 0.0


# --------------------------------------------------------------------------
# Gate: "savings and budget consume spending_result instead of
# recomputing monthly_cashflow/spending_by_category"
# --------------------------------------------------------------------------

def test_budget_agent_never_calls_spending_by_category_itself():
    source = (REPO_ROOT / "agents" / "budget_agent.py").read_text()
    assert "spending_by_category" not in source
    assert "actual_budget_split_from_categories" in source


def test_savings_agent_never_calls_monthly_cashflow_itself():
    source = (REPO_ROOT / "agents" / "savings_agent.py").read_text()
    assert "monthly_cashflow(" not in source  # only reads the passed-in monthly_cashflow argument


# --------------------------------------------------------------------------
# Gate: "grep -rn '\* 0\.3|\* 0\.5' agents/ returns no allocation-related
# matches" - run the literal check the plan specifies.
# --------------------------------------------------------------------------

def test_no_hardcoded_surplus_percentage_anywhere_in_agents():
    pattern = re.compile(r"\* 0\.3\b|\* 0\.5\b")
    offending = []
    for path in (REPO_ROOT / "agents").glob("*.py"):
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if pattern.search(line):
                offending.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offending, "hardcoded surplus percentage found:\n" + "\n".join(offending)


# --------------------------------------------------------------------------
# Structural: every specialist is interchangeable behind BaseAgent (Liskov)
# --------------------------------------------------------------------------

def test_all_specialists_share_the_same_result_contract_via_base_agent():
    from agents.base import BaseAgent
    for cls in (SpendingAnalyzerAgent, DebtAnalyzerAgent, SavingsStrategyAgent, BudgetAdvisorAgent, GoalPlannerAgent):
        assert issubclass(cls, BaseAgent)
        assert cls.run is BaseAgent.run or cls is GoalPlannerAgent  # GoalPlannerAgent is the one documented exception
