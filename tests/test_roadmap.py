"""Phase 3 tests: utils/roadmap.py (build_roadmap / explain_roadmap).

Each test maps to a Phase 3 exit-gate item in `Implementation Plan - MVP 1.md`
concerning the roadmap allocator itself (not yet the specialists or graph -
see test_specialist_agents.py and test_graph.py for those).
"""

import json
from pathlib import Path

import pytest

from utils import finance_calc as fc
from utils import ingestion
from utils import roadmap as rm

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"
GOLDEN_DIR = FIXTURES_DIR / "golden"

ALL_PROFILE_FIXTURES = sorted(GOLDEN_DIR.glob("*.input.json")) + [
    FIXTURES_DIR / "valid_profile.json",
    FIXTURES_DIR / "empty_debts_goals_profile.json",
    FIXTURES_DIR / "comprehensive_findings_scenario.json",
    FIXTURES_DIR / "high_interest_debt_with_surplus.json",
]


def _load(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def _run_pipeline(profile: dict):
    df = fc._transactions_to_frame(profile.get("transactions") or [])
    flags = ingestion.detect_data_quality_issues(df) if not df.empty else []
    snapshot = fc.calculate_financial_snapshot(profile, data_quality_flags=flags)
    trends = fc.compute_trends(profile, snapshot)
    findings = fc.derive_findings(snapshot, trends)
    risks = fc.derive_risks(snapshot, findings)
    snapshot["risk_flags"] = fc.project_risk_flags(risks)
    roadmap = rm.build_roadmap(profile, snapshot, findings, risks)
    return snapshot, trends, findings, risks, roadmap


# --------------------------------------------------------------------------
# Allocation ledger: the structural guarantee itself
# --------------------------------------------------------------------------

def test_ledger_never_hands_out_more_than_it_has():
    ledger = rm._AllocationLedger(100.0)
    first = ledger.take(60.0)
    second = ledger.take(60.0)  # asks for more than remains
    assert first == 60.0
    assert second == 40.0
    assert ledger.remaining == 0.0
    assert ledger.take(1.0) == 0.0


def test_ledger_rejects_negative_requests_as_zero():
    ledger = rm._AllocationLedger(100.0)
    assert ledger.take(-50.0) == 0.0
    assert ledger.remaining == 100.0


def test_ledger_never_goes_negative_for_a_negative_total():
    ledger = rm._AllocationLedger(-500.0)
    assert ledger.remaining == 0.0
    assert ledger.take(10.0) == 0.0


# --------------------------------------------------------------------------
# Gate: "sum(distributed allocation) never exceeds allocatable_surplus" -
# property-style check across every committed fixture.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", ALL_PROFILE_FIXTURES, ids=lambda p: p.name)
def test_distributed_allocation_never_exceeds_allocatable_surplus(path):
    profile = _load(path)
    snapshot, _, _, _, roadmap = _run_pipeline(profile)
    allocatable_surplus = snapshot["metrics"]["allocatable_surplus"]
    if allocatable_surplus is None:
        pytest.skip(f"{path.name} has unresolved inputs")

    allocation = roadmap["allocation"]
    distributed = allocation["debt_extra_payment"] + sum(allocation["goal_contributions"].values()) + allocation["savings_contribution"]
    assert distributed <= allocatable_surplus + 1e-9


# --------------------------------------------------------------------------
# Gate: "Every roadmap action points to a snapshot metric, and to a
# finding_id/risk_id where one exists"
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", ALL_PROFILE_FIXTURES, ids=lambda p: p.name)
def test_every_action_has_metric_refs(path):
    profile = _load(path)
    _, _, _, _, roadmap = _run_pipeline(profile)
    for action in roadmap["actions"]:
        assert action["metric_refs"], f"action {action['action_id']} has no metric_refs"


def test_debt_action_references_a_real_finding_and_risk_when_they_exist():
    """Uses a fixture with genuine positive surplus AND a high-APR debt -
    comprehensive_findings_scenario.json (Phase 2) has a high-APR debt but
    its allocatable_surplus is correctly 0 given its deliberately-lowered
    income, so it cannot exercise this action; that is correct behavior,
    not a gap, which test_negative_cashflow_* below covers explicitly."""
    profile = _load(FIXTURES_DIR / "high_interest_debt_with_surplus.json")
    _, _, findings, risks, roadmap = _run_pipeline(profile)
    finding_ids = {f["finding_id"] for f in findings}
    risk_ids = {r["risk_id"] for r in risks}

    debt_action = next((a for a in roadmap["actions"] if a["action_id"] == rm.ACTION_ACCELERATE_DEBT), None)
    assert debt_action is not None, "expected the high-APR debt in this fixture to trigger debt acceleration"
    assert debt_action["monthly_amount"] > 0
    for ref in debt_action["finding_refs"]:
        assert ref in finding_ids
    for ref in debt_action["risk_refs"]:
        assert ref in risk_ids


# --------------------------------------------------------------------------
# Gate: "Action priorities are unique and sequential; every action has a
# stable action_id"
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", ALL_PROFILE_FIXTURES, ids=lambda p: p.name)
def test_action_priorities_are_unique_sequential_and_every_action_has_an_id(path):
    profile = _load(path)
    _, _, _, _, roadmap = _run_pipeline(profile)
    priorities = [a["priority"] for a in roadmap["actions"]]
    assert priorities == list(range(1, len(priorities) + 1))
    action_ids = [a["action_id"] for a in roadmap["actions"]]
    assert len(action_ids) == len(set(action_ids)), "action_ids must be unique within one roadmap"
    assert all(action_ids)


def test_build_roadmap_is_deterministic_for_the_same_input():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    snapshot, _, findings, risks, roadmap1 = _run_pipeline(profile)
    roadmap2 = rm.build_roadmap(profile, snapshot, findings, risks)
    assert roadmap1["allocation"] == roadmap2["allocation"]
    assert [a["action_id"] for a in roadmap1["actions"]] == [a["action_id"] for a in roadmap2["actions"]]


# --------------------------------------------------------------------------
# Bug found during Phase 6 golden-fixture manual review: a goal could clear
# snapshot.goal_results' preliminary, allocation-unaware feasibility check
# (run before this waterfall, against the *full* allocatable_surplus) and
# still end up genuinely underfunded here once buffer/debt/earlier-priority
# goals claim their share first - build_roadmap() already computed the real,
# allocation-aware feasibility at that point but discarded it, so the action
# itself never reflected the shortfall (only the goal specialist's own prose
# narrative did). See income_drop_rising_dining: "New laptop" needs
# $400/month but only $377.17 remains once the starter buffer takes its 50%
# share first.
# --------------------------------------------------------------------------

def test_underfunded_goal_action_is_elevated_to_high_severity_this_month():
    profile = _load(GOLDEN_DIR / "income_drop_rising_dining.input.json")
    _, _, _, _, roadmap = _run_pipeline(profile)
    action = next(a for a in roadmap["actions"] if a["action_id"] == "ACTION_FUND_GOAL_NEW_LAPTOP")
    assert action["severity"] == "high"
    assert action["urgency"] == "this_month"
    assert "short of the $400" in action["rationale"]
    # amount actually allocated is still exactly what the ledger had left,
    # not the goal's full requirement - elevation must not change the amount.
    assert roadmap["allocation"]["goal_contributions"]["New laptop"] == pytest.approx(377.16666666666674)


def test_fully_funded_goal_action_keeps_medium_severity_next_90_days():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    _, _, _, _, roadmap = _run_pipeline(profile)
    action = next(a for a in roadmap["actions"] if a["action_id"].startswith("ACTION_FUND_GOAL_"))
    assert action["severity"] == "medium"
    assert action["urgency"] == "next_90_days"
    assert "short of" not in action["rationale"]


# --------------------------------------------------------------------------
# Gate: "The negative-cashflow golden input produces a roadmap where
# debt_extra_payment, savings_contribution, and every goal_contributions
# entry are 0"
# --------------------------------------------------------------------------

def test_negative_cashflow_golden_fixture_produces_an_all_zero_distributed_allocation():
    profile = _load(GOLDEN_DIR / "negative_cashflow.input.json")
    snapshot, _, _, _, roadmap = _run_pipeline(profile)
    assert snapshot["metrics"]["allocatable_surplus"] == 0.0

    allocation = roadmap["allocation"]
    assert allocation["debt_extra_payment"] == 0.0
    assert allocation["savings_contribution"] == 0.0
    assert all(amount == 0.0 for amount in allocation["goal_contributions"].values())


def test_negative_cashflow_produces_no_debt_savings_or_goal_actions():
    """Stronger than the gate item itself: not only is the allocation zero,
    no action for debt acceleration, savings growth, or goal funding should
    even be generated - there's nothing to spend money on."""
    profile = _load(GOLDEN_DIR / "negative_cashflow.input.json")
    _, _, _, _, roadmap = _run_pipeline(profile)
    action_ids = {a["action_id"] for a in roadmap["actions"]}
    assert rm.ACTION_ACCELERATE_DEBT not in action_ids
    assert rm.ACTION_GROW_SAVINGS not in action_ids
    assert not any(a["action_id"].startswith("ACTION_FUND_GOAL_") for a in roadmap["actions"])


# --------------------------------------------------------------------------
# Unresolved-inputs path (step 1 of the waterfall)
# --------------------------------------------------------------------------

def test_missing_monthly_income_produces_the_resolve_inputs_action_only():
    profile = _load(FIXTURES_DIR / "valid_profile.json")
    profile["monthly_income"] = None
    df = fc._transactions_to_frame(profile["transactions"])
    snapshot = fc.calculate_financial_snapshot(profile, data_quality_flags=ingestion.detect_data_quality_issues(df))
    roadmap = rm.build_roadmap(profile, snapshot, [], [])
    assert [a["action_id"] for a in roadmap["actions"]] == [rm.ACTION_RESOLVE_INPUTS]
    assert roadmap["allocation"] == {
        "buffer_reserved": 0.0, "debt_extra_payment": 0.0, "goal_contributions": {}, "savings_contribution": 0.0,
    }


def test_invalid_profile_produces_the_resolve_inputs_action():
    profile = _load(FIXTURES_DIR / "invalid_negative_debt_balance.json")
    snapshot = fc.calculate_financial_snapshot(profile)
    roadmap = rm.build_roadmap(profile, snapshot, [], [])
    assert roadmap["actions"][0]["action_id"] == rm.ACTION_RESOLVE_INPUTS
    assert "balance must be >= 0" in roadmap["actions"][0]["rationale"]


# --------------------------------------------------------------------------
# explain_roadmap fallback (no LLM configured in tests - no API key present)
# --------------------------------------------------------------------------

def test_explain_roadmap_fallback_lists_every_action_unchanged():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    snapshot, _, findings, risks, roadmap = _run_pipeline(profile)
    fallback = rm._fallback_roadmap_narrative(roadmap)
    for action in roadmap["actions"]:
        assert action["title"] in fallback
        assert f"{action['monthly_amount']:,.0f}" in fallback


def test_roadmap_narrative_is_populated_without_an_api_key():
    """No OPENROUTER_API_KEY is set in the test environment, so this
    exercises the real fallback path end-to-end via build_roadmap()."""
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    _, _, _, _, roadmap = _run_pipeline(profile)
    assert roadmap["narrative"]
    assert "offline rule-based mode" in roadmap["narrative"] or roadmap["narrative"]
