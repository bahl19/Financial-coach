"""Phase 0 tests: utils/contracts.py and the committed fixtures.

Each test maps directly to one Phase 0 exit-gate item in
`Implementation Plan - MVP 1.md`. Golden-fixture *expected outputs* are not
tested here - they don't exist until Phase 6 (Golden Fixture Freeze). This
file only proves the golden *inputs* are loadable and internally represent
the scenario their filename claims, so a later phase built against a
mislabeled fixture fails immediately here rather than confusingly downstream.
"""

import json
from pathlib import Path

import pytest

from utils import contracts

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"
GOLDEN_DIR = FIXTURES_DIR / "golden"

MVP2_CONTRACT_NAMES = (
    "PreferenceProfile",
    "DecisionContext",
    "EvidenceQuery",
    "EvidenceBundle",
    "StrategyPolicy",
    "PlanValidation",
)


def _load(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


# --------------------------------------------------------------------------
# default_assumptions()
# --------------------------------------------------------------------------

def test_default_assumptions_is_internally_valid():
    assumptions = contracts.default_assumptions()
    assert contracts.validate_assumptions(assumptions) == []


def test_default_assumptions_ratios_sum_to_one():
    assumptions = contracts.default_assumptions()
    total = assumptions["needs_ratio"] + assumptions["wants_ratio"] + assumptions["savings_ratio"]
    assert total == pytest.approx(1.0)


# --------------------------------------------------------------------------
# Gate: "Rejects a budget split that does not total 1.0"
# --------------------------------------------------------------------------

def test_validate_assumptions_rejects_bad_budget_split():
    profile = _load(FIXTURES_DIR / "invalid_bad_budget_split.json")
    issues = contracts.validate_assumptions(profile["assumptions"])
    assert any("total 1.0" in issue for issue in issues)


def test_validate_assumptions_accepts_a_split_that_sums_to_one():
    assumptions = contracts.default_assumptions()
    assert contracts.validate_assumptions(assumptions) == []


def test_validate_profile_surfaces_the_same_bad_split():
    profile = _load(FIXTURES_DIR / "invalid_bad_budget_split.json")
    issues = contracts.validate_profile(profile)
    assert any("total 1.0" in issue for issue in issues)


# --------------------------------------------------------------------------
# Gate: "Rejects debt balances or minimum payments below zero"
# --------------------------------------------------------------------------

def test_validate_profile_rejects_negative_debt_balance_and_min_payment():
    profile = _load(FIXTURES_DIR / "invalid_negative_debt_balance.json")
    issues = contracts.validate_profile(profile)
    assert any("balance must be >= 0" in issue for issue in issues)
    assert any("min_payment must be >= 0" in issue for issue in issues)


def test_validate_profile_accepts_zero_balance_and_zero_apr():
    profile = _load(FIXTURES_DIR / "valid_profile.json")
    profile["debts"] = [{"name": "Paid Off Loan", "balance": 0.0, "apr": 0.0, "min_payment": 0.0}]
    assert contracts.validate_profile(profile) == []


# --------------------------------------------------------------------------
# Gate: "Accepts an empty debt or goals list"
# --------------------------------------------------------------------------

def test_validate_profile_accepts_empty_debts_and_goals():
    profile = _load(FIXTURES_DIR / "empty_debts_goals_profile.json")
    assert profile["debts"] == []
    assert profile["goals"] == []
    assert contracts.validate_profile(profile) == []


def test_validate_profile_accepts_missing_debts_and_goals_keys():
    profile = _load(FIXTURES_DIR / "empty_debts_goals_profile.json")
    del profile["debts"]
    del profile["goals"]
    assert contracts.validate_profile(profile) == []


# --------------------------------------------------------------------------
# Gate: "Unknown values preserved as None, never coerced to zero"
# --------------------------------------------------------------------------

def test_validate_profile_does_not_flag_none_as_invalid():
    """A None (unknown) monthly_income/current_savings must not be treated as
    a negative-value violation, and must not raise - it is simply unknown."""
    profile = _load(FIXTURES_DIR / "valid_profile.json")
    profile["monthly_income"] = None
    profile["current_savings"] = None
    issues = contracts.validate_profile(profile)
    assert not any("monthly_income" in issue for issue in issues)
    assert not any("current_savings" in issue for issue in issues)


def test_validate_profile_does_not_coerce_none_debt_fields_to_zero():
    profile = _load(FIXTURES_DIR / "valid_profile.json")
    profile["debts"] = [{"name": "Unknown Amounts", "balance": None, "apr": None, "min_payment": None}]
    # None is "unknown", not "negative" - must not be rejected as if it were 0 or below.
    issues = contracts.validate_profile(profile)
    assert issues == []


def test_validate_assumptions_treats_none_as_missing_not_zero():
    assumptions = contracts.default_assumptions()
    assumptions["needs_ratio"] = None
    issues = contracts.validate_assumptions(assumptions)
    assert any("needs_ratio is required" in issue for issue in issues)
    # Must not report it as out-of-range (which would imply it was compared as if it were 0).
    assert not any("needs_ratio must be between 0 and 1" in issue for issue in issues)


# --------------------------------------------------------------------------
# Currency/region: assumptions.currency and assumptions.region validation
# --------------------------------------------------------------------------

def test_default_assumptions_currency_and_region_are_valid():
    assumptions = contracts.default_assumptions()
    assert assumptions["currency"] in contracts.SUPPORTED_CURRENCIES
    assert assumptions["region"] in contracts.SUPPORTED_REGIONS
    assert contracts.validate_assumptions(assumptions) == []


def test_validate_assumptions_accepts_every_supported_currency_and_region():
    for currency in contracts.SUPPORTED_CURRENCIES:
        for region in contracts.SUPPORTED_REGIONS:
            assumptions = {**contracts.default_assumptions(), "currency": currency, "region": region}
            assert contracts.validate_assumptions(assumptions) == []


def test_validate_assumptions_rejects_unknown_currency():
    assumptions = contracts.default_assumptions()
    assumptions["currency"] = "GBP"
    issues = contracts.validate_assumptions(assumptions)
    assert any("currency" in issue for issue in issues)


def test_validate_assumptions_rejects_unknown_region():
    assumptions = contracts.default_assumptions()
    assumptions["region"] = "eu"
    issues = contracts.validate_assumptions(assumptions)
    assert any("region" in issue for issue in issues)


def test_validate_assumptions_treats_missing_currency_and_region_as_valid():
    # currency/region are Optional - absent is "use the default," not an error.
    assumptions = contracts.default_assumptions()
    del assumptions["currency"]
    del assumptions["region"]
    assert contracts.validate_assumptions(assumptions) == []


# --------------------------------------------------------------------------
# Gate: "fixtures/*.json and fixtures/golden/*.input.json exist and load
# without error"
# --------------------------------------------------------------------------

ALL_FIXTURE_FILES = sorted(FIXTURES_DIR.glob("*.json")) + sorted(GOLDEN_DIR.glob("*.input.json"))


def test_at_least_the_required_fixtures_exist():
    required = {
        FIXTURES_DIR / "valid_profile.json",
        FIXTURES_DIR / "invalid_bad_budget_split.json",
        FIXTURES_DIR / "invalid_negative_debt_balance.json",
        FIXTURES_DIR / "empty_debts_goals_profile.json",
        FIXTURES_DIR / "example_finding.json",
        FIXTURES_DIR / "example_trend.json",
        FIXTURES_DIR / "example_risk.json",
        FIXTURES_DIR / "example_specialist_result.json",
        GOLDEN_DIR / "stable_high_surplus.input.json",
        GOLDEN_DIR / "negative_cashflow.input.json",
        GOLDEN_DIR / "income_drop_rising_dining.input.json",
    }
    missing = {str(p) for p in required if not p.exists()}
    assert not missing, f"missing required fixtures: {missing}"


@pytest.mark.parametrize("path", ALL_FIXTURE_FILES, ids=lambda p: p.name)
def test_every_committed_fixture_loads_as_valid_json(path):
    data = _load(path)
    assert isinstance(data, dict)
    assert data  # not empty


def test_valid_profile_fixture_passes_validation():
    profile = _load(FIXTURES_DIR / "valid_profile.json")
    assert contracts.validate_profile(profile) == []


def test_example_finding_has_required_severity_and_fact_or_inference_values():
    finding = _load(FIXTURES_DIR / "example_finding.json")
    assert finding["severity"] in contracts.SEVERITIES
    assert finding["urgency"] in contracts.URGENCIES
    assert finding["fact_or_inference"] in contracts.FACT_OR_INFERENCE_VALUES
    assert finding["fact_or_inference"] != "hypothesis"


def test_example_risk_has_required_severity_value():
    risk = _load(FIXTURES_DIR / "example_risk.json")
    assert risk["severity"] in contracts.SEVERITIES
    assert risk["urgency"] in contracts.URGENCIES


def test_example_trend_has_required_direction_value():
    trend = _load(FIXTURES_DIR / "example_trend.json")
    assert trend["direction"] in contracts.TREND_DIRECTIONS


def test_example_specialist_result_allocated_amount_is_not_computed_ad_hoc():
    """Contract-shape check only: allocated_amount must be present as a
    plain numeric field a validator can compare directly against
    roadmap.allocation - not embedded only in the narrative string."""
    result = _load(FIXTURES_DIR / "example_specialist_result.json")
    assert isinstance(result["allocated_amount"], (int, float))
    assert result["recommends_action_ids"]
    assert result["why_allocated"] in result["recommends_action_ids"]


# --------------------------------------------------------------------------
# Golden-fixture sanity checks (fixture-integrity only - not pipeline tests;
# the pipeline that would validate these doesn't exist until later phases)
# --------------------------------------------------------------------------

def _monthly_totals(profile: dict) -> dict:
    """Minimal, dependency-free month -> (income, expenses) aggregation used
    only to sanity-check that a golden fixture represents the scenario its
    filename claims. Deliberately not reused by Phase 1+ - the real
    aggregation is `utils/finance_calc.py`'s to own."""
    totals: dict = {}
    for txn in profile["transactions"]:
        month = txn["date"][:7]
        income, expense = totals.setdefault(month, [0.0, 0.0])
        if txn["amount"] > 0:
            totals[month][0] += txn["amount"]
        else:
            totals[month][1] += -txn["amount"]
    return totals


def test_negative_cashflow_golden_fixture_actually_has_negative_cashflow():
    profile = _load(GOLDEN_DIR / "negative_cashflow.input.json")
    totals = _monthly_totals(profile)
    assert len(totals) >= 2
    for month, (income, expenses) in totals.items():
        assert expenses > income, f"{month}: expected expenses > income to represent negative cashflow"


def test_stable_high_surplus_golden_fixture_has_consistent_positive_surplus():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    totals = _monthly_totals(profile)
    assert len(totals) >= 2
    surpluses = [income - expenses for income, expenses in totals.values()]
    assert all(s > 0 for s in surpluses)
    assert max(surpluses) - min(surpluses) < 0.25 * max(surpluses), "surplus should be stable across months"


def test_income_drop_rising_dining_golden_fixture_shows_both_trends():
    profile = _load(GOLDEN_DIR / "income_drop_rising_dining.input.json")
    totals = _monthly_totals(profile)
    months = sorted(totals)
    assert len(months) >= 3
    incomes = [totals[m][0] for m in months]
    assert incomes[-1] < incomes[0] * 0.7, "income should drop sharply by the last month"

    dining_by_month: dict = {}
    for txn in profile["transactions"]:
        if txn["category"] == "Dining Out":
            month = txn["date"][:7]
            dining_by_month[month] = dining_by_month.get(month, 0.0) + (-txn["amount"])
    dining_months = sorted(dining_by_month)
    assert dining_by_month[dining_months[-1]] > dining_by_month[dining_months[0]] * 1.5, (
        "dining spend should rise sharply by the last month"
    )


# --------------------------------------------------------------------------
# Gate: "No MVP 2 contract exists anywhere in the codebase"
# --------------------------------------------------------------------------

CODE_DIRS = ("agents", "utils")
CODE_FILES_TO_SCAN = [
    p
    for d in CODE_DIRS
    for p in (REPO_ROOT / d).glob("*.py")
] + [REPO_ROOT / "app.py"]


@pytest.mark.parametrize("path", CODE_FILES_TO_SCAN, ids=lambda p: p.name)
def test_no_mvp2_contract_name_appears_in_mvp1_source(path):
    source = path.read_text()
    for name in MVP2_CONTRACT_NAMES:
        assert name not in source, f"{path.name} references MVP 2 contract {name!r} - not allowed in MVP 1"


def test_contracts_module_defines_no_mvp2_contract():
    defined = set(dir(contracts))
    for name in MVP2_CONTRACT_NAMES:
        assert name not in defined


# --------------------------------------------------------------------------
# contracts.py is a pure leaf module (dependency inversion / Standing Context)
# --------------------------------------------------------------------------

def test_contracts_module_imports_nothing_project_specific():
    source = (REPO_ROOT / "utils" / "contracts.py").read_text()
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("from agents") or stripped.startswith("import agents"):
            pytest.fail("utils/contracts.py must not import from agents/")
        if stripped.startswith("from utils.") or stripped.startswith("from utils import"):
            pytest.fail("utils/contracts.py must not import from other utils modules")
