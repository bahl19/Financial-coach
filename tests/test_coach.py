"""Phase 5 tests: utils/coach.py (synthesize_coach_summary).

Each test maps to a Phase 5 exit-gate item in `Implementation Plan - MVP 1.md`.
"""

import json
from pathlib import Path

import pytest

from agents import graph as g
from utils import coach
from utils import finance_calc as fc
from utils import ingestion

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"
GOLDEN_DIR = FIXTURES_DIR / "golden"

ALL_PROFILE_FIXTURES = sorted(GOLDEN_DIR.glob("*.input.json")) + [
    FIXTURES_DIR / "valid_profile.json",
    FIXTURES_DIR / "empty_debts_goals_profile.json",
    FIXTURES_DIR / "high_interest_debt_with_surplus.json",
    FIXTURES_DIR / "mixed_urgency_actions.json",
]


def _load(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def _full_pipeline(profile: dict):
    df = fc._transactions_to_frame(profile.get("transactions") or [])
    flags = ingestion.detect_data_quality_issues(df) if not df.empty else []
    snapshot = fc.calculate_financial_snapshot(profile, data_quality_flags=flags)
    trends = fc.compute_trends(profile, snapshot)
    findings = fc.derive_findings(snapshot, trends)
    risks = fc.derive_risks(snapshot, findings)
    snapshot["risk_flags"] = fc.project_risk_flags(risks)
    result = g.run_graph(profile, snapshot, findings, risks, trends)
    roadmap = result["roadmap_result"]
    specialist_results = {
        key: result[key] for key in
        ("spending_result", "budget_result", "savings_result", "debt_result", "goal_result")
    }
    return snapshot, trends, findings, risks, roadmap, specialist_results


def _synthesize(path: Path):
    profile = _load(path)
    snapshot, trends, findings, risks, roadmap, specialist_results = _full_pipeline(profile)
    summary = coach.synthesize_coach_summary(snapshot, trends, findings, risks, roadmap, specialist_results)
    return summary, snapshot, trends, findings, risks, roadmap


# --------------------------------------------------------------------------
# Gate: "top_priorities never exceeds 3 entries and every entry resolves to
# a real action_id"
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", ALL_PROFILE_FIXTURES, ids=lambda p: p.name)
def test_top_priorities_capped_at_three_and_all_resolve(path):
    summary, snapshot, trends, findings, risks, roadmap = _synthesize(path)
    action_ids = {a["action_id"] for a in roadmap["actions"]}

    assert len(summary["top_priorities"]) <= 3
    for action_id in summary["top_priorities"]:
        assert action_id in action_ids


def test_top_priorities_are_the_highest_priority_actions_specifically():
    summary, snapshot, trends, findings, risks, roadmap = _synthesize(FIXTURES_DIR / "mixed_urgency_actions.json")
    expected = [a["action_id"] for a in roadmap["actions"][:3]]
    assert summary["top_priorities"] == expected


def test_top_priorities_actually_truncates_when_more_than_three_actions_exist():
    """None of the committed fixtures naturally produce more than 3 actions
    (verified by inspection - the waterfall tops out at buffer + debt +
    1 goal + savings for all of them), so the <= 3 cap in the other tests
    is never exercised as a real truncation. Adding extra goals here is the
    minimal way to prove the cap actually cuts something off, not just
    happens to never be hit."""
    from utils import roadmap as rm

    profile = _load(FIXTURES_DIR / "mixed_urgency_actions.json")
    profile["goals"] = [
        {"name": "Trip", "amount": 2000.0, "months": 4, "current": 200.0, "priority": "high"},
        {"name": "Laptop", "amount": 1500.0, "months": 6, "current": 0.0, "priority": "high"},
        {"name": "Bike", "amount": 800.0, "months": 8, "current": 0.0, "priority": "medium"},
    ]
    snapshot, trends, findings, risks, roadmap, specialist_results = _full_pipeline(profile)
    assert len(roadmap["actions"]) > 3, "fixture must produce more than 3 actions for this test to mean anything"

    summary = coach.synthesize_coach_summary(snapshot, trends, findings, risks, roadmap, specialist_results)
    assert len(summary["top_priorities"]) == 3
    assert summary["top_priorities"] == [a["action_id"] for a in roadmap["actions"][:3]]
    # The 4th+ action must genuinely be excluded, not just coincidentally absent.
    excluded_action_id = roadmap["actions"][3]["action_id"]
    assert excluded_action_id not in summary["top_priorities"]


# --------------------------------------------------------------------------
# Gate: "Every other list's entries resolve to a real
# Trend/Finding/Risk/action_id"
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", ALL_PROFILE_FIXTURES, ids=lambda p: p.name)
def test_every_id_list_resolves_against_real_objects(path):
    summary, snapshot, trends, findings, risks, roadmap = _synthesize(path)

    trend_ids = {t["trend_id"] for t in trends}
    finding_ids = {f["finding_id"] for f in findings}
    risk_ids = {r["risk_id"] for r in risks}
    action_ids = {a["action_id"] for a in roadmap["actions"]}

    for trend_id in summary["what_changed"]:
        assert trend_id in trend_ids

    for risk_id in summary["critical_risks"]:
        assert risk_id in risk_ids

    for finding_id in summary["important_patterns"] + summary["positive_changes"]:
        assert finding_id in finding_ids

    for bucket in ("actions_this_week", "actions_this_month", "actions_next_90_days", "actions_long_term"):
        for action_id in summary[bucket]:
            assert action_id in action_ids


def test_no_id_list_contains_a_freestanding_string_that_is_not_an_id():
    """A crude but meaningful check: every entry in every ID list must be a
    short, ID-shaped token (matches the FINDING_/TREND_/RISK_/ACTION_ prefix
    convention), never a sentence or a bare number - a violation here would
    mean this layer started narrating instead of selecting."""
    summary, *_ = _synthesize(GOLDEN_DIR / "income_drop_rising_dining.input.json")
    id_fields = (
        "what_changed", "critical_risks", "important_patterns", "positive_changes",
        "top_priorities", "actions_this_week", "actions_this_month", "actions_next_90_days", "actions_long_term",
    )
    for field in id_fields:
        for value in summary[field]:
            assert isinstance(value, str)
            assert value.startswith(("TREND_", "FINDING_", "RISK_", "ACTION_"))
            assert " " not in value  # a sentence would contain spaces; an ID never does


# --------------------------------------------------------------------------
# Gate: "Actions are bucketed by their urgency value, verified against a
# fixture with mixed urgencies"
# --------------------------------------------------------------------------

def test_actions_are_bucketed_by_urgency_on_a_mixed_urgency_fixture():
    summary, snapshot, trends, findings, risks, roadmap = _synthesize(FIXTURES_DIR / "mixed_urgency_actions.json")
    urgency_by_action_id = {a["action_id"]: a["urgency"] for a in roadmap["actions"]}

    # Sanity-check the fixture premise: it must actually produce more than
    # one distinct urgency, or this test proves nothing.
    assert len(set(urgency_by_action_id.values())) >= 3, "fixture must exercise at least 3 distinct urgencies"

    bucket_to_urgency = {
        "actions_this_week": "immediate",
        "actions_this_month": "this_month",
        "actions_next_90_days": "next_90_days",
        "actions_long_term": "long_term",
    }
    for bucket, expected_urgency in bucket_to_urgency.items():
        for action_id in summary[bucket]:
            assert urgency_by_action_id[action_id] == expected_urgency


def test_immediate_urgency_action_lands_in_this_week_bucket():
    """The resolve-inputs path is the only place urgency="immediate"
    actually occurs - covers the this_week bucket the mixed-urgency fixture
    above cannot (nothing else ever produces "immediate")."""
    profile = _load(FIXTURES_DIR / "valid_profile.json")
    profile["monthly_income"] = None  # forces build_roadmap's unresolved-inputs path
    from utils import roadmap as rm
    snapshot = fc.calculate_financial_snapshot(profile)
    roadmap = rm.build_roadmap(profile, snapshot, [], [])
    assert roadmap["actions"][0]["urgency"] == "immediate"

    summary = coach.synthesize_coach_summary(snapshot, [], [], [], roadmap, {})
    assert roadmap["actions"][0]["action_id"] in summary["actions_this_week"]


# --------------------------------------------------------------------------
# Gate: "data_quality_flags present in a fixture appear in the Assumptions
# and Data Limitations section"
# --------------------------------------------------------------------------

def test_data_quality_flags_appear_in_assumptions_and_limitations():
    profile = _load(FIXTURES_DIR / "data_quality_duplicate_and_missing_month.json")
    snapshot, trends, findings, risks, roadmap, specialist_results = _full_pipeline(profile)
    assert snapshot["data_quality_flags"]  # sanity-check the fixture actually has flags

    summary = coach.synthesize_coach_summary(snapshot, trends, findings, risks, roadmap, specialist_results)
    for flag in snapshot["data_quality_flags"]:
        assert flag["detail"] in summary["assumptions_and_limitations"]


def test_no_data_quality_flags_still_produces_a_valid_limitations_string():
    summary, snapshot, *_ = _synthesize(GOLDEN_DIR / "stable_high_surplus.input.json")
    assert isinstance(summary["assumptions_and_limitations"], str)
    assert summary["assumptions_and_limitations"]  # never empty


# --------------------------------------------------------------------------
# Gate: "The section order is fixed and matches the spec above in a
# rendered example"
# --------------------------------------------------------------------------

_EXPECTED_SECTION_ORDER = (
    "overall_health", "what_changed", "critical_risks", "important_patterns", "positive_changes",
    "top_priorities", "actions_this_week", "actions_this_month", "actions_next_90_days", "actions_long_term",
    "assumptions_and_limitations",
)


def test_coach_summary_keys_match_the_fixed_section_order():
    summary, *_ = _synthesize(GOLDEN_DIR / "stable_high_surplus.input.json")
    keys = tuple(k for k in summary.keys() if k != "schema_version")
    assert keys == _EXPECTED_SECTION_ORDER


def test_rendering_the_summary_in_fixed_order_produces_a_stable_document():
    """A minimal "rendered example" per the gate item: joining the sections
    in CoachSummary's own key order (schema_version aside) must reproduce
    exactly the spec's section sequence, so a future renderer can iterate
    summary.items() directly rather than hardcoding field names."""
    summary, *_ = _synthesize(GOLDEN_DIR / "negative_cashflow.input.json")
    rendered_order = [k for k in summary if k != "schema_version"]
    assert rendered_order == list(_EXPECTED_SECTION_ORDER)


# --------------------------------------------------------------------------
# Standing constraint: no invented risk/finding/number; overall_health is a
# deterministic function of snapshot + risks, not free text
# --------------------------------------------------------------------------

def test_overall_health_reflects_critical_risk_count_deterministically():
    summary, snapshot, trends, findings, risks, roadmap = _synthesize(GOLDEN_DIR / "negative_cashflow.input.json")
    critical_count = sum(1 for r in risks if r["severity"] == "critical")
    if critical_count > 0:
        assert "critical" in summary["overall_health"].lower()
    assert snapshot["health_band"] in summary["overall_health"]


def test_synthesize_coach_summary_is_deterministic_for_the_same_input():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    snapshot, trends, findings, risks, roadmap, specialist_results = _full_pipeline(profile)
    a = coach.synthesize_coach_summary(snapshot, trends, findings, risks, roadmap, specialist_results)
    b = coach.synthesize_coach_summary(snapshot, trends, findings, risks, roadmap, specialist_results)
    assert a == b
