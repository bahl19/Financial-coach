"""Phase 1 tests: utils/finance_calc.py additions (Component 3).

Each test maps to a Phase 1 exit-gate item in `Implementation Plan - MVP 1.md`
that concerns the financial core, surplus/allocation semantics, or the
health score.
"""

import json
from pathlib import Path

import pytest

from utils import finance_calc as fc
from utils import ingestion

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"
GOLDEN_DIR = FIXTURES_DIR / "golden"

ALL_PROFILE_FIXTURES = (
    sorted(p for p in FIXTURES_DIR.glob("*.json"))
    + sorted(GOLDEN_DIR.glob("*.input.json"))
)


def _load(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def _snapshot_for(profile: dict) -> dict:
    """Composes Component 2's data-quality detection with Component 3's
    snapshot calculation exactly as a future graph node will - this proves
    the two components wire together without either importing the other."""
    df = fc._transactions_to_frame(profile.get("transactions") or [])
    flags = ingestion.detect_data_quality_issues(df) if not df.empty else []
    return fc.calculate_financial_snapshot(profile, data_quality_flags=flags)


# --------------------------------------------------------------------------
# Gate: "allocatable_surplus is never negative, and equals
# max(0, gross_surplus - required_commitments - minimum_monthly_buffer)
# for every Phase 0 fixture"
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", ALL_PROFILE_FIXTURES, ids=lambda p: p.name)
def test_allocatable_surplus_matches_formula_and_is_never_negative(path):
    profile = _load(path)
    snapshot = _snapshot_for(profile)
    metrics = snapshot["metrics"]

    if metrics["gross_surplus"] is None:
        pytest.skip(f"{path.name} has no confirmed monthly_income")

    expected = max(
        0.0,
        metrics["gross_surplus"] - metrics["required_commitments"] - (profile.get("constraints") or {}).get(
            "minimum_monthly_buffer", 0.0
        ),
    )
    assert metrics["allocatable_surplus"] == pytest.approx(expected)
    assert metrics["allocatable_surplus"] >= 0.0


# --------------------------------------------------------------------------
# Gate: "gross_surplus <= 0 forces allocatable_surplus == 0 (verified with
# the negative-cashflow golden input)"
# --------------------------------------------------------------------------

def test_negative_cashflow_golden_fixture_forces_zero_allocatable_surplus():
    profile = _load(GOLDEN_DIR / "negative_cashflow.input.json")
    snapshot = _snapshot_for(profile)
    metrics = snapshot["metrics"]

    assert metrics["gross_surplus"] is not None
    assert metrics["gross_surplus"] <= 0
    assert metrics["allocatable_surplus"] == 0.0


def test_calculate_allocatable_surplus_directly_for_zero_and_negative_gross_surplus():
    assert fc.calculate_allocatable_surplus(0.0, commitments=0.0, minimum_buffer=0.0) == 0.0
    assert fc.calculate_allocatable_surplus(-500.0, commitments=0.0, minimum_buffer=0.0) == 0.0


def test_calculate_gross_surplus_and_allocatable_surplus_propagate_none_for_unknown_income():
    gross = fc.calculate_gross_surplus(None, average_monthly_expenses=2000.0)
    assert gross is None
    assert fc.calculate_allocatable_surplus(gross, commitments=0.0, minimum_buffer=0.0) is None


# --------------------------------------------------------------------------
# required_commitments: the double-counting guard this phase exists to add
# --------------------------------------------------------------------------

def test_required_commitments_is_zero_when_debt_payment_history_covers_minimums():
    profile = _load(FIXTURES_DIR / "valid_profile.json")
    df = fc._transactions_to_frame(profile["transactions"])
    # valid_profile.json's single Debt Payment transaction is -120.0, matching
    # the one debt's min_payment of 120.0 exactly - already fully reflected.
    commitments = fc.required_commitments(profile["debts"], df)
    assert commitments == pytest.approx(0.0)


def test_required_commitments_covers_only_the_unreflected_shortfall():
    debts = [{"name": "New Loan", "balance": 1000.0, "apr": 5.0, "min_payment": 200.0}]
    df = fc._transactions_to_frame([
        {
            "date": "2026-05-01", "description": "Employer Payroll", "amount": 5000.0,
            "category": "Income", "category_confidence": 1.0, "needs_review": False, "transaction_type": "income",
        },
    ])
    # No Debt Payment transactions at all yet - the full minimum is unreflected.
    commitments = fc.required_commitments(debts, df)
    assert commitments == pytest.approx(200.0)


def test_required_commitments_never_double_subtracts_a_minimum_already_in_expenses():
    """The core of the fix this phase exists for: a $120 minimum already
    paid (and therefore already inside average_monthly_expenses via the
    Debt Payment category) must not also appear in required_commitments."""
    debts = [{"name": "Credit Card", "balance": 4200.0, "apr": 22.9, "min_payment": 120.0}]
    df = fc._transactions_to_frame([
        {
            "date": "2026-05-15", "description": "Visa Payment", "amount": -120.0,
            "category": "Debt Payment", "category_confidence": 1.0, "needs_review": False,
            "transaction_type": "debt_payment",
        },
    ])
    assert fc.required_commitments(debts, df) == pytest.approx(0.0)


# --------------------------------------------------------------------------
# Gate: "Debt balances never become negative in payoff timelines"
# --------------------------------------------------------------------------

def test_payoff_timeline_never_shows_a_negative_balance():
    debts = [
        {"name": "Card A", "balance": 500.0, "apr": 24.0, "min_payment": 50.0},
        {"name": "Card B", "balance": 200.0, "apr": 18.0, "min_payment": 30.0},
    ]
    for strategy in ("avalanche", "snowball"):
        result = fc.simulate_payoff(debts, extra_monthly=100.0, strategy=strategy)
        assert all(entry["total_balance"] >= 0.0 for entry in result["timeline"])


# --------------------------------------------------------------------------
# Gate: "A user with no debt gets an empty/explicit debt-free result, not
# a crash"
# --------------------------------------------------------------------------

def test_no_debt_profile_gives_explicit_debt_free_comparison_not_a_crash():
    profile = _load(FIXTURES_DIR / "empty_debts_goals_profile.json")
    snapshot = _snapshot_for(profile)
    assert snapshot["debt_comparison"] == {"avalanche": None, "snowball": None}
    assert snapshot["metrics"]["total_debt"] == 0.0
    assert snapshot["metrics"]["required_commitments"] == 0.0


def test_no_debt_profile_has_zero_debt_to_income_and_no_health_penalty():
    """No debt means a debt-to-income ratio of exactly 0% - a known fact,
    not an unknown one, so it is 0.0 rather than None (unlike
    required_commitments/total_debt, which are also correctly 0.0 here for
    the same reason). What must hold regardless of representation: zero
    debt never reduces the health score."""
    profile = _load(FIXTURES_DIR / "empty_debts_goals_profile.json")
    snapshot = _snapshot_for(profile)
    assert snapshot["metrics"]["debt_to_income_percent"] == 0.0

    score, _ = fc.calculate_health_score(snapshot["metrics"], profile.get("assumptions") or {})
    full_debt_component_metrics = {**snapshot["metrics"], "debt_to_income_percent": None}
    score_with_none, _ = fc.calculate_health_score(full_debt_component_metrics, profile.get("assumptions") or {})
    assert score == score_with_none, "0% and 'no debt at all' must earn the same full credit"


# --------------------------------------------------------------------------
# calculate_health_score
# --------------------------------------------------------------------------

def test_health_score_is_always_bounded_0_to_100():
    extreme_metrics = {
        "savings_rate_percent": 500.0,
        "emergency_fund_months": 100.0,
        "debt_to_income_percent": 0.0,
        "gross_surplus": 10_000.0,
    }
    score, _ = fc.calculate_health_score(extreme_metrics, {})
    assert 0 <= score <= 100

    terrible_metrics = {
        "savings_rate_percent": -500.0,
        "emergency_fund_months": 0.0,
        "debt_to_income_percent": 90.0,
        "gross_surplus": -5000.0,
    }
    score, _ = fc.calculate_health_score(terrible_metrics, {})
    assert 0 <= score <= 100


def test_health_score_handles_all_missing_metrics_without_crashing():
    score, band = fc.calculate_health_score({}, {})
    assert 0 <= score <= 100
    assert isinstance(band, str)


def test_health_band_thresholds_are_monotonic_with_score():
    high_score, high_band = fc.calculate_health_score(
        {"savings_rate_percent": 25.0, "emergency_fund_months": 6.0, "debt_to_income_percent": 5.0,
         "gross_surplus": 1000.0}, {},
    )
    low_score, low_band = fc.calculate_health_score(
        {"savings_rate_percent": 0.0, "emergency_fund_months": 0.0, "debt_to_income_percent": 45.0,
         "gross_surplus": -100.0}, {},
    )
    assert high_score > low_score
    assert high_band != low_band


# --------------------------------------------------------------------------
# calculate_financial_snapshot: composition, no LLM, no crash on empty input
# --------------------------------------------------------------------------

def test_calculate_financial_snapshot_never_calls_out_to_an_llm(monkeypatch):
    """Deterministic-core boundary: nothing in this module may import an
    LLM client. This asserts the module has no such dependency at all."""
    import utils.finance_calc as module
    source = Path(module.__file__).read_text()
    assert "openai" not in source.lower()
    assert "openrouter" not in source.lower()


def test_calculate_financial_snapshot_handles_empty_transactions_without_crashing():
    profile = {
        "schema_version": "1.0",
        "transactions": [],
        "monthly_income": 4000.0,
        "current_savings": 1000.0,
        "debts": [],
        "goals": [],
        "constraints": {"minimum_monthly_buffer": 0.0, "protected_categories": []},
        "assumptions": {
            "currency": "USD", "needs_ratio": 0.5, "wants_ratio": 0.3, "savings_ratio": 0.2,
            "savings_apy": 0.04, "emergency_fund_months": 3,
        },
    }
    snapshot = fc.calculate_financial_snapshot(profile)
    assert snapshot["metrics"]["average_monthly_expenses"] == 0.0
    assert snapshot["data_quality_flags"] == []


def test_calculate_financial_snapshot_surfaces_validation_issues_from_contracts():
    profile = _load(FIXTURES_DIR / "invalid_negative_debt_balance.json")
    snapshot = fc.calculate_financial_snapshot(profile)
    assert any("balance must be >= 0" in issue for issue in snapshot["validation_issues"])


@pytest.mark.parametrize("path", ALL_PROFILE_FIXTURES, ids=lambda p: p.name)
def test_calculate_financial_snapshot_never_crashes_on_any_committed_fixture(path):
    profile = _load(path)
    snapshot = _snapshot_for(profile)
    assert snapshot["schema_version"] == "1.0"
    assert 0 <= snapshot["health_score"] <= 100
