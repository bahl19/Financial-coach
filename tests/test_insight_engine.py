"""Phase 2 tests: Trend/Insight/Risk Engine additions to utils/finance_calc.py.

Each test maps to a Phase 2 exit-gate item in `Implementation Plan - MVP 1.md`.
"""

import json
from pathlib import Path

import pytest

from utils import contracts
from utils import finance_calc as fc
from utils import ingestion

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"
GOLDEN_DIR = FIXTURES_DIR / "golden"


def _load(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def _run_pipeline(profile: dict):
    """Composes Phase 1 + Phase 2 exactly as a future graph will: ingestion's
    data-quality detection, the financial snapshot, trends, findings, risks,
    and the risk_flags projection - proving the pieces wire together without
    Component 3 importing Component 2 and without risk_flags ever being
    computed independently of Risk[]."""
    df = fc._transactions_to_frame(profile.get("transactions") or [])
    flags = ingestion.detect_data_quality_issues(df) if not df.empty else []
    snapshot = fc.calculate_financial_snapshot(profile, data_quality_flags=flags)
    trends = fc.compute_trends(profile, snapshot)
    findings = fc.derive_findings(snapshot, trends)
    risks = fc.derive_risks(snapshot, findings)
    snapshot["risk_flags"] = fc.project_risk_flags(risks)
    return snapshot, trends, findings, risks


# --------------------------------------------------------------------------
# Gate: "All 6 trend types compute correctly against the Phase 0 fixtures"
# --------------------------------------------------------------------------

def test_income_expense_surplus_trends_compute_for_a_three_month_fixture():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    snapshot, trends, _, _ = _run_pipeline(profile)
    ids = {t["trend_id"] for t in trends}
    assert "TREND_INCOME" in ids
    assert "TREND_EXPENSES" in ids
    assert "TREND_SURPLUS" in ids


def test_category_spending_trends_compute_per_category():
    profile = _load(GOLDEN_DIR / "income_drop_rising_dining.input.json")
    _, trends, _, _ = _run_pipeline(profile)
    category_trends = [t for t in trends if t["trend_id"].startswith("TREND_CATEGORY_")]
    assert any(t["trend_id"] == "TREND_CATEGORY_DINING_OUT" for t in category_trends)


def test_debt_payment_trend_computes_from_debt_payment_category_history():
    profile = _load(GOLDEN_DIR / "negative_cashflow.input.json")
    _, trends, _, _ = _run_pipeline(profile)
    debt_trend = next((t for t in trends if t["trend_id"] == "TREND_DEBT_PAYMENT"), None)
    assert debt_trend is not None
    assert debt_trend["metric"] == "debt_payment_spend"


def test_savings_contribution_trend_computes_from_savings_category_history():
    profile = _load(FIXTURES_DIR / "savings_contribution_trend.json")
    _, trends, _, _ = _run_pipeline(profile)
    savings_trend = next((t for t in trends if t["trend_id"] == "TREND_SAVINGS_CONTRIBUTIONS"), None)
    assert savings_trend is not None
    assert savings_trend["start_value"] == pytest.approx(200.0)
    assert savings_trend["end_value"] == pytest.approx(500.0)
    assert savings_trend["direction"] == "increasing"


def test_emergency_fund_runway_trend_compares_actual_to_target_not_time():
    profile = _load(GOLDEN_DIR / "negative_cashflow.input.json")
    snapshot, trends, _, _ = _run_pipeline(profile)
    runway = next((t for t in trends if t["trend_id"] == "TREND_EMERGENCY_FUND_RUNWAY"), None)
    assert runway is not None
    assert runway["period"] == "current_vs_target"
    assert runway["start_value"] == profile["assumptions"]["emergency_fund_months"]
    assert runway["end_value"] == pytest.approx(snapshot["metrics"]["emergency_fund_months"])


def test_percent_change_sign_matches_direction_even_with_a_negative_baseline():
    """Regression test for a bug found during Phase 6's manual golden-
    fixture review (not by a failing test): negative_cashflow.input.json's
    monthly net cashflow moves from -675 (March) to -500 (May) - a genuine
    improvement (deficit shrinking) - but the old formula
    (absolute_change / signed start_value) reported percent_change as
    -25.9% and classified it "moderate_decrease", directly contradicting
    direction="increasing". Divides by abs(start_value) instead, so
    percent_change's sign always agrees with direction's sign, regardless
    of whether the baseline itself was negative."""
    trend = fc._build_trend("TEST_TREND", "test_metric", "3_months", start_value=-675.0, end_value=-500.0)
    assert trend["direction"] == "increasing"
    assert trend["percent_change"] > 0, "percent_change must agree in sign with an improving (increasing) direction"
    assert trend["classification"] in ("moderate_increase", "sharp_increase")


def test_sharp_decrease_in_an_essential_category_is_not_labeled_positive():
    """Regression test for a bug found during Phase 6's manual golden-
    fixture review: a sharp decrease in Healthcare spend (negative_cashflow's
    fixture drops from $260 to $0) was labeled severity="positive" with
    "Keep up the trend" - actively bad advice, since a healthcare spending
    drop could mean skipped care, not disciplined saving. Essential/needs
    categories (Rent/Mortgage, Groceries, Utilities, Insurance, Healthcare,
    Transport, Debt Payment - fc.NEEDS_CATS) must not receive the same
    unconditional "positive" label a discretionary category's decrease does."""
    profile = _load(GOLDEN_DIR / "negative_cashflow.input.json")
    _, trends, findings, _ = _run_pipeline(profile)
    healthcare_finding = next(f for f in findings if f["finding_id"] == "FINDING_CATEGORY_HEALTHCARE_CHANGE")
    assert healthcare_finding["severity"] != "positive"
    assert "skipped" in healthcare_finding["recommended_response"].lower() or "intentional" in healthcare_finding["recommended_response"].lower()


def test_sharp_decrease_in_a_discretionary_category_is_still_labeled_positive():
    """The other half of the fix: a genuinely discretionary category (Dining
    Out is not in NEEDS_CATS) dropping sharply should still read as good
    news - the fix narrows the "positive" label, it doesn't remove it."""
    df_rows = [
        {"date": "2026-03-01", "description": "x", "amount": 5000.0, "category": "Income", "category_confidence": 1.0, "needs_review": False, "transaction_type": "income"},
        {"date": "2026-03-05", "description": "x", "amount": -400.0, "category": "Dining", "category_confidence": 1.0, "needs_review": False, "transaction_type": "expense"},
        {"date": "2026-04-01", "description": "x", "amount": 5000.0, "category": "Income", "category_confidence": 1.0, "needs_review": False, "transaction_type": "income"},
        {"date": "2026-04-05", "description": "x", "amount": -50.0, "category": "Dining", "category_confidence": 1.0, "needs_review": False, "transaction_type": "expense"},
    ]
    df = fc._transactions_to_frame(df_rows)
    snapshot = fc.calculate_financial_snapshot({
        "transactions": df_rows, "monthly_income": 5000.0, "current_savings": 0.0, "debts": [], "goals": [],
        "constraints": {"minimum_monthly_buffer": 0.0, "protected_categories": []},
        "assumptions": {"currency": "USD", "needs_ratio": 0.5, "wants_ratio": 0.3, "savings_ratio": 0.2, "savings_apy": 0.04, "emergency_fund_months": 3},
    })
    trends = fc.compute_trends({"transactions": df_rows, "assumptions": {"emergency_fund_months": 3}}, snapshot)
    findings = fc.derive_findings(snapshot, trends)
    dining_finding = next((f for f in findings if f["finding_id"] == "FINDING_CATEGORY_DINING_CHANGE"), None)
    assert dining_finding is not None
    assert dining_finding["severity"] == "positive"


def test_negative_cashflow_golden_fixture_surplus_trend_agrees_with_itself():
    """The concrete real-world instance of the regression above."""
    profile = _load(GOLDEN_DIR / "negative_cashflow.input.json")
    _, trends, _, _ = _run_pipeline(profile)
    surplus_trend = next(t for t in trends if t["trend_id"] == "TREND_SURPLUS")
    if surplus_trend["direction"] == "increasing":
        assert surplus_trend["percent_change"] > 0
        assert surplus_trend["classification"] in ("stable", "moderate_increase", "sharp_increase")


def test_all_six_trend_types_are_exercised_across_the_committed_fixtures():
    """No single fixture need cover every trend type, but across the
    committed set, all 6 must be demonstrated at least once."""
    seen_prefixes = set()
    for path in list(GOLDEN_DIR.glob("*.input.json")) + [FIXTURES_DIR / "savings_contribution_trend.json"]:
        profile = _load(path)
        _, trends, _, _ = _run_pipeline(profile)
        for trend in trends:
            if trend["trend_id"].startswith("TREND_CATEGORY_"):
                seen_prefixes.add("category_spending")
            else:
                seen_prefixes.add(trend["trend_id"])

    required = {
        "TREND_INCOME", "TREND_EXPENSES", "TREND_SURPLUS",
        "category_spending", "TREND_DEBT_PAYMENT", "TREND_SAVINGS_CONTRIBUTIONS",
    }
    assert required.issubset(seen_prefixes), f"missing trend types: {required - seen_prefixes}"


# --------------------------------------------------------------------------
# Gate: "All 8 finding types compute correctly, each with
# severity/urgency/confidence/fact_or_inference populated"
# --------------------------------------------------------------------------

REQUIRED_FINDING_FIELDS = {"severity", "urgency", "confidence", "fact_or_inference"}


def test_every_finding_across_all_fixtures_has_required_fields_populated():
    for path in list(GOLDEN_DIR.glob("*.input.json")) + [
        FIXTURES_DIR / "data_quality_duplicate_and_missing_month.json",
        FIXTURES_DIR / "savings_contribution_trend.json",
    ]:
        profile = _load(path)
        _, _, findings, _ = _run_pipeline(profile)
        for finding in findings:
            missing = REQUIRED_FINDING_FIELDS - set(k for k in finding if finding[k] is not None)
            assert not missing, f"{path.name}: {finding['finding_id']} missing {missing}"
            assert finding["severity"] in contracts.SEVERITIES
            assert finding["urgency"] in contracts.URGENCIES


def test_all_eight_finding_types_are_exercised_across_the_committed_fixtures():
    seen_types = set()
    for path in list(GOLDEN_DIR.glob("*.input.json")) + [
        FIXTURES_DIR / "data_quality_duplicate_and_missing_month.json",
        FIXTURES_DIR / "comprehensive_findings_scenario.json",
    ]:
        profile = _load(path)
        _, _, findings, _ = _run_pipeline(profile)
        seen_types.update(f["type"] for f in findings)

    required_types = {
        "income_trend", "expense_trend", "category_trend", "cashflow",
        "debt_risk", "emergency_fund_risk", "goal_feasibility", "data_quality",
    }
    assert required_types.issubset(seen_types), f"missing finding types: {required_types - seen_types}"


# --------------------------------------------------------------------------
# Gate: "The data-quality finding type is populated from
# snapshot.data_quality_flags and produces findings for the
# duplicate-transaction and missing-month fixture from Phase 1"
# --------------------------------------------------------------------------

def test_data_quality_findings_come_from_the_phase1_duplicate_and_missing_month_fixture():
    profile = _load(FIXTURES_DIR / "data_quality_duplicate_and_missing_month.json")
    _, _, findings, _ = _run_pipeline(profile)
    dq_findings = [f for f in findings if f["type"] == "data_quality"]
    codes = {f["finding_id"] for f in dq_findings}
    assert "FINDING_DATA_QUALITY_DUPLICATE_TRANSACTIONS" in codes
    assert "FINDING_DATA_QUALITY_MISSING_MONTHS" in codes


# --------------------------------------------------------------------------
# Gate: "All 6 risk types compute correctly, each referencing at least one
# finding_id where applicable"
# --------------------------------------------------------------------------

def test_all_six_risk_types_are_exercised_across_the_committed_fixtures():
    seen_categories_or_ids = set()
    for path in list(GOLDEN_DIR.glob("*.input.json")) + [
        FIXTURES_DIR / "comprehensive_findings_scenario.json",
    ]:
        profile = _load(path)
        _, _, _, risks = _run_pipeline(profile)
        seen_categories_or_ids.update(r["risk_id"] for r in risks)

    required_risk_ids = {
        "RISK_NEGATIVE_CASHFLOW",
        "RISK_INSUFFICIENT_EMERGENCY_FUND",
        "RISK_HIGH_INTEREST_DEBT",
        "RISK_HIGH_DEBT_SERVICE_BURDEN",
        "RISK_OVERSPENDING",
        "RISK_GOAL_FAILURE",
    }
    assert required_risk_ids.issubset(seen_categories_or_ids), (
        f"missing risk types: {required_risk_ids - seen_categories_or_ids}"
    )


def test_risks_reference_a_real_finding_id_when_one_exists():
    profile = _load(GOLDEN_DIR / "negative_cashflow.input.json")
    _, _, findings, risks = _run_pipeline(profile)
    finding_ids = {f["finding_id"] for f in findings}

    negative_cashflow_risk = next(r for r in risks if r["risk_id"] == "RISK_NEGATIVE_CASHFLOW")
    assert negative_cashflow_risk["finding_refs"], "expected at least one finding_ref"
    for ref in negative_cashflow_risk["finding_refs"]:
        assert ref in finding_ids, f"risk references a finding_id that doesn't exist: {ref}"


# --------------------------------------------------------------------------
# Gate: "No Finding is tagged hypothesis"
# --------------------------------------------------------------------------

def test_no_finding_is_ever_tagged_hypothesis():
    for path in list(GOLDEN_DIR.glob("*.input.json")) + [
        FIXTURES_DIR / "data_quality_duplicate_and_missing_month.json",
        FIXTURES_DIR / "savings_contribution_trend.json",
    ]:
        profile = _load(path)
        _, _, findings, _ = _run_pipeline(profile)
        for finding in findings:
            assert finding["fact_or_inference"] != "hypothesis"
            assert finding["fact_or_inference"] in ("fact", "deterministic_inference")


# --------------------------------------------------------------------------
# Gate: "The income-drop-plus-rising-dining golden input produces the
# expected Trend/Finding IDs with correct classification"
# --------------------------------------------------------------------------

def test_income_drop_rising_dining_produces_expected_trends_and_findings():
    profile = _load(GOLDEN_DIR / "income_drop_rising_dining.input.json")
    _, trends, findings, _ = _run_pipeline(profile)

    income_trend = next(t for t in trends if t["trend_id"] == "TREND_INCOME")
    assert income_trend["direction"] == "decreasing"
    # -45.16% magnitude falls in the documented "moderate" band (15-50%), not
    # "sharp" (>=50%) - the finding layer's own -30% threshold is what
    # correctly escalates this to a critical finding below, independently of
    # the trend's generic classification label.
    assert income_trend["classification"] == "moderate_decrease"

    dining_trend = next(t for t in trends if t["trend_id"] == "TREND_CATEGORY_DINING_OUT")
    assert dining_trend["direction"] == "increasing"
    assert dining_trend["classification"] == "sharp_increase"

    finding_ids = {f["finding_id"] for f in findings}
    assert "FINDING_INCOME_DROP" in finding_ids
    income_drop = next(f for f in findings if f["finding_id"] == "FINDING_INCOME_DROP")
    assert income_drop["severity"] == "critical"
    assert income_drop["urgency"] == "immediate"

    assert "FINDING_CATEGORY_DINING_OUT_CHANGE" in finding_ids
    dining_finding = next(f for f in findings if f["finding_id"] == "FINDING_CATEGORY_DINING_OUT_CHANGE")
    assert dining_finding["severity"] == "medium"


# --------------------------------------------------------------------------
# Gate: "risk_flags (legacy) is a correct projection of the new Risk
# objects, not independently computed"
# --------------------------------------------------------------------------

def test_risk_flags_is_exactly_the_projection_of_risks_not_independently_computed():
    profile = _load(GOLDEN_DIR / "negative_cashflow.input.json")
    snapshot, _, _, risks = _run_pipeline(profile)
    assert snapshot["risk_flags"] == fc.project_risk_flags(risks)


def test_calculate_financial_snapshot_alone_returns_empty_risk_flags():
    """Before derive_risks() runs, calculate_financial_snapshot() must not
    independently guess at risk_flags - it returns empty, disclosing that
    risk_flags is not yet populated rather than a second, possibly
    disagreeing computation."""
    profile = _load(GOLDEN_DIR / "negative_cashflow.input.json")
    snapshot = fc.calculate_financial_snapshot(profile)
    assert snapshot["risk_flags"] == []


def test_project_risk_flags_is_a_pure_function_of_its_risks_argument():
    profile = _load(GOLDEN_DIR / "negative_cashflow.input.json")
    _, _, _, risks = _run_pipeline(profile)
    first = fc.project_risk_flags(risks)
    second = fc.project_risk_flags(risks)
    assert first == second
