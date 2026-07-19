"""Phase 9 tests: the eleven distinct edge-case paths named in
`Implementation Plan - MVP 1.md`. Each path is run through the real,
end-to-end pipeline (`agents.graph.run_graph`, not a narrower unit) where
that is meaningful, so "runs without error or crash" is checked against
what the app itself actually does, not an isolated function call.

Case 11 (corrupted SpecialistResult) already has dedicated unit coverage in
`tests/test_validation.py::test_corrupted_allocated_amount_is_replaced_by_deterministic_fallback`;
the test below additionally exercises it through the full graph, since a
node-level corruption and Phase 4's own direct-call test are not
necessarily the same code path.
"""

import copy
import json
from pathlib import Path

import pytest

from agents import graph as g
from utils import finance_calc as fc
from utils import ingestion
from utils.contracts import validate_profile

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"
GOLDEN_DIR = FIXTURES_DIR / "golden"


def _load(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def _run_full_pipeline(profile: dict):
    transactions_df = fc._transactions_to_frame(profile.get("transactions") or [])
    flags = ingestion.detect_data_quality_issues(transactions_df) if not transactions_df.empty else []
    snapshot = fc.calculate_financial_snapshot(profile, data_quality_flags=flags)
    trends = fc.compute_trends(profile, snapshot)
    findings = fc.derive_findings(snapshot, trends)
    risks = fc.derive_risks(snapshot, findings)
    snapshot["risk_flags"] = fc.project_risk_flags(risks)
    return g.run_graph(profile, snapshot, findings, risks, trends)


# --------------------------------------------------------------------------
# 1. Invalid input (fails validate_profile)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("fixture_name", ["invalid_bad_budget_split.json", "invalid_negative_debt_balance.json"])
def test_invalid_input_reports_issues_without_crashing(fixture_name):
    profile = _load(FIXTURES_DIR / fixture_name)
    issues = validate_profile(profile)  # must not raise
    assert issues  # and must genuinely flag something


# --------------------------------------------------------------------------
# 2. Zero debts / 5. Zero goals (one fixture covers both)
# --------------------------------------------------------------------------

def test_zero_debts_and_zero_goals_runs_without_crashing():
    profile = _load(FIXTURES_DIR / "empty_debts_goals_profile.json")
    assert profile["debts"] == []
    assert profile["goals"] == []
    result = _run_full_pipeline(profile)
    assert result["debt_result"]["allocated_amount"] == 0.0 or result["debt_result"]["allocated_amount"] is None
    assert result["goal_result"] == []
    assert result["validation_result"]["valid"]


# --------------------------------------------------------------------------
# 3. Exactly one debt
# --------------------------------------------------------------------------

def test_exactly_one_debt_runs_without_crashing():
    profile = _load(FIXTURES_DIR / "valid_profile.json")
    assert len(profile["debts"]) == 1
    result = _run_full_pipeline(profile)
    assert result["debt_result"]["supporting_tables"]["avalanche"]["payoff_order"] == [profile["debts"][0]["name"]]


# --------------------------------------------------------------------------
# 4. Multiple debts (exercises avalanche ordering)
# --------------------------------------------------------------------------

def test_multiple_debts_exercise_avalanche_ordering():
    profile = _load(FIXTURES_DIR / "valid_profile.json")
    profile = copy.deepcopy(profile)
    profile["debts"] = [
        {"name": "Low APR Loan", "balance": 5000.0, "apr": 4.0, "min_payment": 100.0},
        {"name": "High APR Card", "balance": 2000.0, "apr": 27.0, "min_payment": 60.0},
        {"name": "Mid APR Loan", "balance": 8000.0, "apr": 12.0, "min_payment": 150.0},
    ]
    result = _run_full_pipeline(profile)
    avalanche = result["debt_result"]["supporting_tables"]["avalanche"]
    assert avalanche["payoff_order"] == ["High APR Card", "Mid APR Loan", "Low APR Loan"]
    snowball = result["debt_result"]["supporting_tables"]["snowball"]
    assert snowball["payoff_order"] == ["High APR Card", "Low APR Loan", "Mid APR Loan"]


# --------------------------------------------------------------------------
# 6. Unknown/unmatched transaction category
# --------------------------------------------------------------------------

def test_unmatched_transaction_category_is_flagged_other_and_runs_without_crashing():
    import pandas as pd

    raw = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-05", "2026-01-10"]),
        "description": ["Totally Unrecognizable Merchant Co", "Whole Foods"],
        "amount": [-42.0, -100.0],
    })
    tagged = ingestion.tag_transaction_types(ingestion.categorize_with_confidence(raw))
    review_items = ingestion.build_review_items(tagged)
    assert len(review_items) == 1
    assert review_items[0]["suggested_category"] == "Other"

    profile = _load(FIXTURES_DIR / "valid_profile.json")
    profile = copy.deepcopy(profile)
    profile["transactions"] = [
        {
            "date": str(row["date"].date()), "description": row["description"], "amount": float(row["amount"]),
            "category": row["category"], "category_confidence": float(row["category_confidence"]),
            "needs_review": bool(row["needs_review"]), "transaction_type": row["transaction_type"],
        }
        for _, row in tagged.iterrows()
    ]
    result = _run_full_pipeline(profile)
    assert result["validation_result"] is not None  # ran to completion


# --------------------------------------------------------------------------
# 7. Negative cashflow (gross_surplus <= 0)
# --------------------------------------------------------------------------

def test_negative_cashflow_runs_without_crashing():
    profile = _load(GOLDEN_DIR / "negative_cashflow.input.json")
    result = _run_full_pipeline(profile)
    transactions_df = fc._transactions_to_frame(profile["transactions"])
    snapshot = fc.calculate_financial_snapshot(profile, data_quality_flags=ingestion.detect_data_quality_issues(transactions_df))
    assert snapshot["metrics"]["gross_surplus"] <= 0
    assert snapshot["metrics"]["allocatable_surplus"] == 0.0
    assert result["roadmap_result"]["allocation"]["savings_contribution"] == 0.0


# --------------------------------------------------------------------------
# 8. Zero income
# --------------------------------------------------------------------------

def test_zero_income_runs_without_crashing():
    profile = _load(FIXTURES_DIR / "valid_profile.json")
    profile = copy.deepcopy(profile)
    profile["monthly_income"] = 0.0
    for txn in profile["transactions"]:
        if txn["category"] == "Income":
            txn["amount"] = 0.0
    result = _run_full_pipeline(profile)
    transactions_df = fc._transactions_to_frame(profile["transactions"])
    snapshot = fc.calculate_financial_snapshot(profile, data_quality_flags=ingestion.detect_data_quality_issues(transactions_df))
    # guarded divisions: zero income must produce None, never a ZeroDivisionError or a fabricated 0
    assert snapshot["metrics"]["debt_to_income_percent"] is None
    assert snapshot["metrics"]["savings_rate_percent"] is None
    assert result["validation_result"] is not None


# --------------------------------------------------------------------------
# 9. Partial trailing month
# --------------------------------------------------------------------------

def test_partial_trailing_month_is_flagged_and_runs_without_crashing():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    transactions_df = fc._transactions_to_frame(profile["transactions"])
    flags = ingestion.detect_data_quality_issues(transactions_df)
    assert any(flag["code"] == "PARTIAL_TRAILING_MONTH" for flag in flags)
    result = _run_full_pipeline(profile)
    assert result["validation_result"] is not None


# --------------------------------------------------------------------------
# 10. Duplicate transactions
# --------------------------------------------------------------------------

def test_duplicate_transactions_are_flagged_and_run_without_crashing():
    profile = _load(FIXTURES_DIR / "data_quality_duplicate_and_missing_month.json")
    transactions_df = fc._transactions_to_frame(profile["transactions"])
    flags = ingestion.detect_data_quality_issues(transactions_df)
    assert any(flag["code"] == "DUPLICATE_TRANSACTIONS" for flag in flags)
    result = _run_full_pipeline(profile)
    assert result["validation_result"] is not None


# --------------------------------------------------------------------------
# 11. Corrupted SpecialistResult (validator catches it and falls back) -
# exercised through the full graph, not just utils.validation directly.
# --------------------------------------------------------------------------

def test_corrupted_specialist_result_is_caught_and_falls_back_through_the_full_graph():
    profile = _load(FIXTURES_DIR / "valid_profile.json")
    transactions_df = fc._transactions_to_frame(profile["transactions"])
    flags = ingestion.detect_data_quality_issues(transactions_df)
    snapshot = fc.calculate_financial_snapshot(profile, data_quality_flags=flags)
    trends = fc.compute_trends(profile, snapshot)
    findings = fc.derive_findings(snapshot, trends)
    risks = fc.derive_risks(snapshot, findings)
    snapshot["risk_flags"] = fc.project_risk_flags(risks)

    state = {"profile": profile, "snapshot": snapshot, "findings": findings, "risks": risks, "trends": trends}
    state.update(g.spending_node(state))
    state.update(g.roadmap_node(state))
    state.update(g.budget_node(state))
    state.update(g.savings_node(state))
    state.update(g.debt_node(state))
    state.update(g.goal_node(state))

    # Corrupt the debt specialist's allocated_amount so it disagrees with
    # roadmap.allocation.debt_extra_payment - exactly the class of bug
    # Phase 3/4 exist to catch.
    state["debt_result"] = dict(state["debt_result"])
    state["debt_result"]["allocated_amount"] = (state["debt_result"]["allocated_amount"] or 0.0) + 999.0

    state.update(g.validation_node(state))
    state.update(g.coach_node(state))

    assert state["validation_result"]["fallback_used"] is True
    assert not state["validation_result"]["valid"]
    assert state["debt_result"]["allocated_amount"] == state["roadmap_result"]["allocation"]["debt_extra_payment"]
