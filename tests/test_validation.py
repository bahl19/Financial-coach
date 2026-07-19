"""Phase 4 tests: utils/validation.py (+ validation_structured / validation_prose).

Per the Phase 4 execution prompt: "Write each test by deliberately
constructing the violation the check exists to catch. A validator that has
only ever seen valid input is untested." Every test below does exactly
that - takes a genuinely clean pipeline run, corrupts one specific thing,
and asserts the corresponding check (and only that class of check) fires.
"""

import copy
import json
from pathlib import Path

from agents import graph as g
from utils import finance_calc as fc
from utils import ingestion
from utils import validation as v

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"
GOLDEN_DIR = FIXTURES_DIR / "golden"


def _load(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def _clean_pipeline(profile: dict):
    df = fc._transactions_to_frame(profile.get("transactions") or [])
    flags = ingestion.detect_data_quality_issues(df) if not df.empty else []
    snapshot = fc.calculate_financial_snapshot(profile, data_quality_flags=flags)
    trends = fc.compute_trends(profile, snapshot)
    findings = fc.derive_findings(snapshot, trends)
    risks = fc.derive_risks(snapshot, findings)
    snapshot["risk_flags"] = fc.project_risk_flags(risks)
    result = g.run_graph(profile, snapshot, findings, risks, trends)
    roadmap = result["roadmap_result"]
    # Explicit allowlist, not "everything except roadmap_result" - LangGraph's
    # invoke() returns the *full* merged state (profile/snapshot/findings/
    # risks/trends/validation_result included), and a blocklist would
    # silently let those leak into "specialist_results" as bogus entries
    # (harmless only because every check degrades safely via dict.get(),
    # which would have hidden a real bug in the checks themselves).
    specialist_results = {
        key: result[key] for key in
        ("spending_result", "budget_result", "savings_result", "debt_result", "goal_result")
    }
    return roadmap, specialist_results, snapshot, findings, risks, trends


CLEAN_PROFILE = _load(FIXTURES_DIR / "high_interest_debt_with_surplus.json")


def _clean() -> tuple:
    return _clean_pipeline(copy.deepcopy(CLEAN_PROFILE))


# --------------------------------------------------------------------------
# Gate: "A clean run reports valid: True, fallback_used: False"
# --------------------------------------------------------------------------

def test_clean_run_is_valid_with_no_fallback():
    roadmap, specialist_results, snapshot, findings, risks, trends = _clean()
    result = v.validate_consistency(roadmap, specialist_results, snapshot, findings, risks, trends)
    assert result["valid"] is True
    assert result["violations"] == []
    assert result["fallback_used"] is False


# --------------------------------------------------------------------------
# Check 1: recommends_action_ids references unknown action_id
# --------------------------------------------------------------------------

def test_check1_catches_an_unknown_recommended_action_id():
    roadmap, specialist_results, snapshot, findings, risks, trends = _clean()
    specialist_results["debt_result"] = dict(specialist_results["debt_result"])
    specialist_results["debt_result"]["recommends_action_ids"] = ["ACTION_DOES_NOT_EXIST"]

    result = v.validate_consistency(roadmap, specialist_results, snapshot, findings, risks, trends)
    assert result["valid"] is False
    assert any("unknown action_id" in msg for msg in result["violations"])


# --------------------------------------------------------------------------
# Check 2: recommends_action_ids not in priority order
# --------------------------------------------------------------------------

def test_check2_catches_out_of_priority_order_recommendations():
    roadmap, specialist_results, snapshot, findings, risks, trends = _clean()
    action_ids = [a["action_id"] for a in roadmap["actions"]]
    if len(action_ids) < 2:
        # Ensure there are at least two actions to reorder, regardless of
        # which fixture produced this roadmap.
        roadmap = copy.deepcopy(roadmap)
        roadmap["actions"].append({
            "action_id": "ACTION_EXTRA_TEST_ONLY", "priority": 99, "severity": "low", "urgency": "long_term",
            "timeframe": "Ongoing", "title": "Test", "rationale": "test", "monthly_amount": 1.0,
            "metric_refs": ["gross_surplus"], "finding_refs": [], "risk_refs": [],
        })
        action_ids.append("ACTION_EXTRA_TEST_ONLY")

    specialist_results["debt_result"] = dict(specialist_results["debt_result"])
    specialist_results["debt_result"]["recommends_action_ids"] = list(reversed(action_ids))

    result = v.validate_consistency(roadmap, specialist_results, snapshot, findings, risks, trends)
    assert result["valid"] is False
    assert any("priority order" in msg for msg in result["violations"])


# --------------------------------------------------------------------------
# Check 3 / gate: "A corrupted SpecialistResult (allocated_amount not
# matching roadmap.allocation) is replaced by the deterministic fallback,
# with fallback_used = True"
# --------------------------------------------------------------------------

def test_check3_catches_a_mismatched_allocated_amount():
    roadmap, specialist_results, snapshot, findings, risks, trends = _clean()
    real_amount = specialist_results["debt_result"]["allocated_amount"]
    specialist_results["debt_result"] = dict(specialist_results["debt_result"])
    specialist_results["debt_result"]["allocated_amount"] = (real_amount or 0.0) + 500.0

    result = v.validate_consistency(roadmap, specialist_results, snapshot, findings, risks, trends)
    assert result["valid"] is False
    assert any("does not match roadmap.allocation" in msg for msg in result["violations"])


def test_corrupted_allocated_amount_is_replaced_by_deterministic_fallback():
    roadmap, specialist_results, snapshot, findings, risks, trends = _clean()
    real_amount = specialist_results["debt_result"]["allocated_amount"]
    specialist_results["debt_result"] = dict(specialist_results["debt_result"])
    specialist_results["debt_result"]["allocated_amount"] = (real_amount or 0.0) + 500.0
    specialist_results["debt_result"]["narrative"] = "This is a corrupted narrative claiming the wrong amount."

    corrected, result = v.apply_consistency_fallback(roadmap, specialist_results, snapshot, findings, risks, trends)

    assert result["fallback_used"] is True
    assert corrected["debt_result"]["allocated_amount"] == real_amount
    assert corrected["debt_result"]["narrative"] != "This is a corrupted narrative claiming the wrong amount."
    assert corrected["debt_result"]["narrative"]  # a real, non-empty fallback narrative was produced
    # Untouched specialists pass through exactly as given.
    assert corrected["spending_result"] == specialist_results["spending_result"]


def test_budget_agent_reporting_a_nonzero_allocated_amount_is_caught():
    """Budget never allocates money - check 3's expected=None branch."""
    roadmap, specialist_results, snapshot, findings, risks, trends = _clean()
    specialist_results["budget_result"] = dict(specialist_results["budget_result"])
    specialist_results["budget_result"]["allocated_amount"] = 42.0

    result = v.validate_consistency(roadmap, specialist_results, snapshot, findings, risks, trends)
    assert result["valid"] is False
    assert any("must not allocate money" in msg for msg in result["violations"])


# --------------------------------------------------------------------------
# Check 4: zero-allocation not recommended
# --------------------------------------------------------------------------

def test_check4_catches_a_positive_amount_reported_against_a_zero_allocation():
    profile = _load(GOLDEN_DIR / "negative_cashflow.input.json")
    roadmap, specialist_results, snapshot, findings, risks, trends = _clean_pipeline(profile)
    assert roadmap["allocation"]["debt_extra_payment"] == 0.0  # sanity-check the premise

    specialist_results["debt_result"] = dict(specialist_results["debt_result"])
    specialist_results["debt_result"]["allocated_amount"] = 250.0  # fabricated, roadmap gave ₹0

    result = v.validate_consistency(roadmap, specialist_results, snapshot, findings, risks, trends)
    assert result["valid"] is False
    assert any("though the roadmap allocated ₹0" in msg for msg in result["violations"])


def test_check4_catches_recommending_a_zero_dollar_action():
    roadmap, specialist_results, snapshot, findings, risks, trends = _clean()
    roadmap = copy.deepcopy(roadmap)
    roadmap["actions"].append({
        "action_id": "ACTION_ZERO_DOLLAR_TEST", "priority": 99, "severity": "low", "urgency": "long_term",
        "timeframe": "Ongoing", "title": "Zero dollar test action", "rationale": "test", "monthly_amount": 0.0,
        "metric_refs": ["gross_surplus"], "finding_refs": [], "risk_refs": [],
    })
    specialist_results["spending_result"] = dict(specialist_results["spending_result"])
    specialist_results["spending_result"]["recommends_action_ids"] = ["ACTION_ZERO_DOLLAR_TEST"]

    result = v.validate_consistency(roadmap, specialist_results, snapshot, findings, risks, trends)
    assert result["valid"] is False
    assert any("allocated ₹0" in msg for msg in result["violations"])


# --------------------------------------------------------------------------
# Gate: "The negative-cashflow golden input passes check 4 (nothing
# recommends a positive allocation)" - the un-corrupted, honest case.
# --------------------------------------------------------------------------

def test_negative_cashflow_golden_input_passes_check4_uncorrupted():
    profile = _load(GOLDEN_DIR / "negative_cashflow.input.json")
    roadmap, specialist_results, snapshot, findings, risks, trends = _clean_pipeline(profile)
    violations = fc  # noqa - just to keep import used if unused elsewhere
    from utils.validation_structured import check_zero_allocation_not_recommended
    entries = v._flatten_specialist_results(specialist_results)
    assert check_zero_allocation_not_recommended(entries=entries, roadmap=roadmap) == []


# --------------------------------------------------------------------------
# Check 5: unresolved finding_refs / trend_refs / action risk_refs
# --------------------------------------------------------------------------

def test_check5_catches_an_unresolved_finding_ref_on_a_specialist():
    roadmap, specialist_results, snapshot, findings, risks, trends = _clean()
    specialist_results["debt_result"] = dict(specialist_results["debt_result"])
    specialist_results["debt_result"]["finding_refs"] = ["FINDING_DOES_NOT_EXIST"]

    result = v.validate_consistency(roadmap, specialist_results, snapshot, findings, risks, trends)
    assert result["valid"] is False
    assert any("unknown finding_id" in msg for msg in result["violations"])


def test_check5_catches_an_unresolved_trend_ref_on_a_specialist():
    roadmap, specialist_results, snapshot, findings, risks, trends = _clean()
    specialist_results["debt_result"] = dict(specialist_results["debt_result"])
    specialist_results["debt_result"]["trend_refs"] = ["TREND_DOES_NOT_EXIST"]

    result = v.validate_consistency(roadmap, specialist_results, snapshot, findings, risks, trends)
    assert result["valid"] is False
    assert any("unknown trend_id" in msg for msg in result["violations"])


def test_check5_catches_an_unresolved_risk_ref_on_a_roadmap_action():
    roadmap, specialist_results, snapshot, findings, risks, trends = _clean()
    roadmap = copy.deepcopy(roadmap)
    roadmap["actions"][0]["risk_refs"] = ["RISK_DOES_NOT_EXIST"]

    result = v.validate_consistency(roadmap, specialist_results, snapshot, findings, risks, trends)
    assert result["valid"] is False
    assert any("unknown risk_id" in msg for msg in result["violations"])
    # This is a roadmap-level violation - no specialist narrative caused it.
    assert not any(vi["entry_key"] for vi in v._run_all_checks(roadmap, specialist_results, snapshot, findings, risks, trends) if "unknown risk_id" in vi["message"])


# --------------------------------------------------------------------------
# Check 6: action monthly_amount exceeds allocatable_surplus
# --------------------------------------------------------------------------

def test_check6_catches_an_action_exceeding_allocatable_surplus():
    roadmap, specialist_results, snapshot, findings, risks, trends = _clean()
    surplus = snapshot["metrics"]["allocatable_surplus"]
    roadmap = copy.deepcopy(roadmap)
    roadmap["actions"][0]["monthly_amount"] = surplus + 10_000.0

    result = v.validate_consistency(roadmap, specialist_results, snapshot, findings, risks, trends)
    assert result["valid"] is False
    assert any("exceeds allocatable_surplus" in msg for msg in result["violations"])

    corrected, remediated = v.apply_consistency_fallback(roadmap, specialist_results, snapshot, findings, risks, trends)
    # No specialist result caused this, so nothing should be replaced.
    assert remediated["fallback_used"] is False
    assert corrected == specialist_results


# --------------------------------------------------------------------------
# Check 7: narrative dollar amount not in the allowlist
# --------------------------------------------------------------------------

def test_check7_catches_a_fabricated_dollar_amount_in_prose():
    roadmap, specialist_results, snapshot, findings, risks, trends = _clean()
    specialist_results["debt_result"] = dict(specialist_results["debt_result"])
    specialist_results["debt_result"]["narrative"] = "You should pay an extra ₹987,654 toward your debt this month."

    result = v.validate_consistency(roadmap, specialist_results, snapshot, findings, risks, trends)
    assert result["valid"] is False
    assert any("matching no known allocation, metric, or supporting figure" in msg for msg in result["violations"])


def test_check7_does_not_false_positive_on_a_legitimate_narrative():
    roadmap, specialist_results, snapshot, findings, risks, trends = _clean()
    from utils.validation_prose import check_narrative_dollar_amounts_are_allowlisted
    entries = v._flatten_specialist_results(specialist_results)
    violations = check_narrative_dollar_amounts_are_allowlisted(
        entries=entries, roadmap=roadmap, snapshot=snapshot, findings=findings, risks=risks, trends=trends,
    )
    assert violations == []


# --------------------------------------------------------------------------
# Check 8: narrative percentage not in the allowlist
# --------------------------------------------------------------------------

def test_check8_catches_a_fabricated_percentage_in_prose():
    roadmap, specialist_results, snapshot, findings, risks, trends = _clean()
    specialist_results["spending_result"] = dict(specialist_results["spending_result"])
    specialist_results["spending_result"]["narrative"] = "Your dining spend rose an incredible 973% this month."

    result = v.validate_consistency(roadmap, specialist_results, snapshot, findings, risks, trends)
    assert result["valid"] is False
    assert any("matching no known trend, metric, or supporting figure" in msg for msg in result["violations"])


# --------------------------------------------------------------------------
# Check 9: income/expense/surplus-labeled dollar figure absent from metrics
# --------------------------------------------------------------------------

def test_check9_catches_a_fabricated_income_figure_in_prose():
    roadmap, specialist_results, snapshot, findings, risks, trends = _clean()
    specialist_results["savings_result"] = dict(specialist_results["savings_result"])
    specialist_results["savings_result"]["narrative"] = "Given your income of ₹123,456, you should save more."

    result = v.validate_consistency(roadmap, specialist_results, snapshot, findings, risks, trends)
    assert result["valid"] is False
    assert any("income/expense/surplus" in msg for msg in result["violations"])
