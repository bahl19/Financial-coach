"""Phase 3 tests: utils/scenarios.py."""

import copy
import json
from pathlib import Path

import pytest

from utils import finance_calc as fc
from utils import scenarios

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"
GOLDEN_DIR = FIXTURES_DIR / "golden"


def _load(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


# --------------------------------------------------------------------------
# Gate: "Previewing a scenario does not mutate the base profile"
# --------------------------------------------------------------------------

def test_apply_assumptions_does_not_mutate_the_base_profile():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    original_needs_ratio = profile["assumptions"]["needs_ratio"]

    adjusted = scenarios.apply_assumptions(profile, {"needs_ratio": 0.6, "wants_ratio": 0.2, "savings_ratio": 0.2})

    assert profile["assumptions"]["needs_ratio"] == original_needs_ratio
    assert adjusted["assumptions"]["needs_ratio"] == 0.6
    assert adjusted is not profile
    assert adjusted["transactions"] is not profile["transactions"] or adjusted["transactions"] == profile["transactions"]


def test_apply_assumptions_does_not_mutate_nested_transactions_either():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    original_first_amount = profile["transactions"][0]["amount"]

    adjusted = scenarios.apply_assumptions(profile, {"emergency_fund_months": 6})
    adjusted["transactions"][0]["amount"] = -99999.0  # mutate the copy

    assert profile["transactions"][0]["amount"] == original_first_amount


def test_apply_assumptions_preserves_unrelated_assumption_fields():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    adjusted = scenarios.apply_assumptions(profile, {"emergency_fund_months": 6})
    assert adjusted["assumptions"]["currency"] == profile["assumptions"]["currency"]
    assert adjusted["assumptions"]["emergency_fund_months"] == 6


# --------------------------------------------------------------------------
# Gate: "Invalid ratios and negative rates return validation issues"
# --------------------------------------------------------------------------

def test_validate_assumption_updates_catches_a_broken_ratio_sum():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    issues = scenarios.validate_assumption_updates(profile, {"savings_ratio": 0.9})  # breaks the sum-to-1.0
    assert any("total 1.0" in issue for issue in issues)


def test_validate_assumption_updates_catches_a_negative_emergency_fund_months():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    issues = scenarios.validate_assumption_updates(profile, {"emergency_fund_months": -2})
    assert any("emergency_fund_months" in issue for issue in issues)


def test_validate_assumption_updates_accepts_a_consistent_change():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    issues = scenarios.validate_assumption_updates(
        profile, {"needs_ratio": 0.4, "wants_ratio": 0.3, "savings_ratio": 0.3}
    )
    assert issues == []


# --------------------------------------------------------------------------
# compare_scenarios
# --------------------------------------------------------------------------

def test_compare_scenarios_reports_a_delta_for_each_metric():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    base_snapshot = fc.calculate_financial_snapshot(profile)

    adjusted_profile = scenarios.apply_assumptions(profile, {"emergency_fund_months": 12})
    adjusted_snapshot = fc.calculate_financial_snapshot(adjusted_profile)

    comparison = scenarios.compare_scenarios(base_snapshot, adjusted_snapshot)
    assert "gross_surplus" in comparison
    assert comparison["gross_surplus"]["base"] == base_snapshot["metrics"]["gross_surplus"]
    assert comparison["gross_surplus"]["adjusted"] == adjusted_snapshot["metrics"]["gross_surplus"]


def test_compare_scenarios_handles_a_none_metric_without_crashing():
    """Unconfirmed income (None), not zero debt, is what genuinely produces
    a None metric - zero debt correctly produces 0.0 (a known fact), as
    established in test_finance_calc.py's equivalent case."""
    profile = _load(FIXTURES_DIR / "empty_debts_goals_profile.json")
    profile["monthly_income"] = None
    snapshot = fc.calculate_financial_snapshot(profile)
    assert snapshot["metrics"]["debt_to_income_percent"] is None

    comparison = scenarios.compare_scenarios(snapshot, snapshot)
    assert comparison["debt_to_income_percent"]["delta"] is None


# --------------------------------------------------------------------------
# apply_expense_reduction(): Scenario Comparison's "cut discretionary
# spending by X%" template. Which categories count as discretionary is the
# caller's decision (scenarios.py depends on Component 1/contracts only).
# --------------------------------------------------------------------------

def test_apply_expense_reduction_scales_down_only_the_named_categories():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    dining_before = sum(
        t["amount"] for t in profile["transactions"] if t["category"] == "Dining Out"
    )
    adjusted = scenarios.apply_expense_reduction(profile, {"Dining Out"}, reduction_fraction=0.5)
    dining_after = sum(
        t["amount"] for t in adjusted["transactions"] if t["category"] == "Dining Out"
    )
    other_before = sum(t["amount"] for t in profile["transactions"] if t["category"] != "Dining Out")
    other_after = sum(t["amount"] for t in adjusted["transactions"] if t["category"] != "Dining Out")

    assert dining_after == pytest.approx(dining_before * 0.5)
    assert other_after == pytest.approx(other_before)  # untouched categories unaffected


def test_apply_expense_reduction_does_not_mutate_the_base_profile():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    original = copy.deepcopy(profile)
    scenarios.apply_expense_reduction(profile, {"Dining Out"}, reduction_fraction=0.2)
    assert profile == original


def test_apply_expense_reduction_never_touches_income_even_if_named():
    """A defensive guard, not an expected real input: even if a caller
    mistakenly names "Income" as a category to reduce, only negative
    (expense) transactions are ever scaled - income is never touched."""
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    income_before = sum(t["amount"] for t in profile["transactions"] if t["category"] == "Income")
    adjusted = scenarios.apply_expense_reduction(profile, {"Income"}, reduction_fraction=0.5)
    income_after = sum(t["amount"] for t in adjusted["transactions"] if t["category"] == "Income")
    assert income_after == income_before
