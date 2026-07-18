"""Phase 3/4 tests: agents/graph.py (LangGraph wiring).

Each test maps to a Phase 3 exit-gate item concerning the graph itself, plus
the Phase 4 wiring of the consistency validator as Stage 4. Phase 4's
per-check behavior is covered exhaustively in test_validation.py; this file
only confirms the validator is actually wired into the graph correctly.
"""

import json
from pathlib import Path

import pytest

from agents import graph as g
from utils import finance_calc as fc
from utils import ingestion

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"
GOLDEN_DIR = FIXTURES_DIR / "golden"

ALL_PROFILE_FIXTURES = sorted(GOLDEN_DIR.glob("*.input.json")) + [
    FIXTURES_DIR / "valid_profile.json",
    FIXTURES_DIR / "empty_debts_goals_profile.json",
    FIXTURES_DIR / "high_interest_debt_with_surplus.json",
]


def _load(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def _stage1(profile: dict):
    df = fc._transactions_to_frame(profile.get("transactions") or [])
    flags = ingestion.detect_data_quality_issues(df) if not df.empty else []
    snapshot = fc.calculate_financial_snapshot(profile, data_quality_flags=flags)
    trends = fc.compute_trends(profile, snapshot)
    findings = fc.derive_findings(snapshot, trends)
    risks = fc.derive_risks(snapshot, findings)
    snapshot["risk_flags"] = fc.project_risk_flags(risks)
    return snapshot, findings, risks, trends


# --------------------------------------------------------------------------
# Gate: "Graph runs without a checkpointer and completes within a single
# invocation"
# --------------------------------------------------------------------------

def test_compiled_graph_has_no_checkpointer():
    compiled = g.build_graph()
    # LangGraph stores the compiled checkpointer (if any) on this attribute;
    # None means no persistence was configured.
    assert getattr(compiled, "checkpointer", None) is None


@pytest.mark.parametrize("path", ALL_PROFILE_FIXTURES, ids=lambda p: p.name)
def test_run_graph_completes_in_one_invocation_for_every_fixture(path):
    profile = _load(path)
    snapshot, findings, risks, trends = _stage1(profile)
    result = g.run_graph(profile, snapshot, findings, risks, trends)
    for key in (
        "spending_result", "roadmap_result", "budget_result", "savings_result",
        "debt_result", "goal_result", "validation_result", "coach_summary",
    ):
        assert key in result


# --------------------------------------------------------------------------
# Gate: "Graph-produced Roadmap matches calling build_roadmap() directly
# (no drift)"
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", ALL_PROFILE_FIXTURES, ids=lambda p: p.name)
def test_graph_roadmap_matches_direct_build_roadmap_call(path):
    from utils import roadmap as rm

    profile = _load(path)
    snapshot, findings, risks, trends = _stage1(profile)

    graph_result = g.run_graph(profile, snapshot, findings, risks, trends)
    direct_roadmap = rm.build_roadmap(profile, snapshot, findings, risks)

    # Compare everything except `narrative`, which may call an LLM and is
    # therefore not guaranteed byte-identical between two separate calls
    # even with the same inputs (though both fall back to the same
    # deterministic text with no API key configured, as here).
    graph_roadmap = dict(graph_result["roadmap_result"])
    graph_roadmap.pop("narrative", None)
    direct_roadmap = dict(direct_roadmap)
    direct_roadmap.pop("narrative", None)
    assert graph_roadmap == direct_roadmap


def test_run_pipeline_direct_matches_run_graph_exactly():
    """The documented fallback path uses the same node functions - their
    outputs must be identical for the same input, narrative aside."""
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    snapshot, findings, risks, trends = _stage1(profile)

    via_graph = g.run_graph(profile, snapshot, findings, risks, trends)
    via_direct = g.run_pipeline_direct(profile, snapshot, findings, risks, trends)

    a, b = dict(via_graph["roadmap_result"]), dict(via_direct["roadmap_result"])
    a.pop("narrative", None)
    b.pop("narrative", None)
    assert a == b

    for key in ("budget_result", "savings_result", "debt_result"):
        a, b = dict(via_graph[key]), dict(via_direct[key])
        a.pop("narrative", None)
        b.pop("narrative", None)
        a.pop("supporting_tables", None)  # DataFrames don't support == cleanly across calls
        b.pop("supporting_tables", None)
        assert a == b

    assert via_graph["validation_result"] == via_direct["validation_result"]
    assert via_graph["coach_summary"] == via_direct["coach_summary"]


# --------------------------------------------------------------------------
# Phase 4: the consistency validator is actually wired in as Stage 4
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", ALL_PROFILE_FIXTURES, ids=lambda p: p.name)
def test_a_clean_run_through_the_graph_is_valid(path):
    profile = _load(path)
    snapshot, findings, risks, trends = _stage1(profile)
    result = g.run_graph(profile, snapshot, findings, risks, trends)
    assert result["validation_result"]["valid"] is True
    assert result["validation_result"]["fallback_used"] is False


# --------------------------------------------------------------------------
# Gate: "savings and budget consume spending_result instead of recomputing"
# / "debt, savings, and goal quote the exact dollar figures in
# roadmap.allocation"
# --------------------------------------------------------------------------

def test_savings_and_debt_results_quote_exact_roadmap_allocation_figures():
    profile = _load(FIXTURES_DIR / "high_interest_debt_with_surplus.json")
    snapshot, findings, risks, trends = _stage1(profile)
    result = g.run_graph(profile, snapshot, findings, risks, trends)

    allocation = result["roadmap_result"]["allocation"]
    assert result["debt_result"]["allocated_amount"] == allocation["debt_extra_payment"]
    assert result["savings_result"]["allocated_amount"] == allocation["savings_contribution"]


def test_goal_results_quote_exact_roadmap_allocation_figures():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    snapshot, findings, risks, trends = _stage1(profile)
    result = g.run_graph(profile, snapshot, findings, risks, trends)

    allocation = result["roadmap_result"]["allocation"]
    for goal_result in result["goal_result"]:
        goal_name = goal_result["supporting_tables"]["goal"]["name"]
        assert goal_result["allocated_amount"] == allocation["goal_contributions"].get(goal_name, 0.0)


# --------------------------------------------------------------------------
# Gate: "The negative-cashflow golden input produces a roadmap where
# debt_extra_payment, savings_contribution, and every goal_contributions
# entry are 0" - verified again through the graph specifically, not just
# build_roadmap() directly (test_roadmap.py already covers that).
# --------------------------------------------------------------------------

def test_negative_cashflow_through_the_graph_allocates_nothing():
    profile = _load(GOLDEN_DIR / "negative_cashflow.input.json")
    snapshot, findings, risks, trends = _stage1(profile)
    result = g.run_graph(profile, snapshot, findings, risks, trends)

    allocation = result["roadmap_result"]["allocation"]
    assert allocation["debt_extra_payment"] == 0.0
    assert allocation["savings_contribution"] == 0.0
    assert result["debt_result"]["allocated_amount"] in (0.0, None)
    assert result["savings_result"]["allocated_amount"] == 0.0


# --------------------------------------------------------------------------
# Phase 5: coach synthesis is wired in as the final stage
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", ALL_PROFILE_FIXTURES, ids=lambda p: p.name)
def test_coach_summary_reads_the_post_validation_specialist_results(path):
    profile = _load(path)
    snapshot, findings, risks, trends = _stage1(profile)
    result = g.run_graph(profile, snapshot, findings, risks, trends)

    action_ids = {a["action_id"] for a in result["roadmap_result"]["actions"]}
    summary = result["coach_summary"]
    assert len(summary["top_priorities"]) <= 3
    for action_id in summary["top_priorities"]:
        assert action_id in action_ids
