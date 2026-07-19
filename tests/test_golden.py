"""Phase 6 tests: golden fixture freeze (`fixtures/golden/*.expected.json`).

Per `Implementation Plan - MVP 1.md`'s Phase 6 task list, a frozen fixture
captures `snapshot.metrics`, `Trend[]`, `Finding[]` (narrowed to
id/severity/urgency/confidence/fact_or_inference), `Risk[]`,
`roadmap.allocation`, `roadmap.actions[].action_id` + `.priority`, and
`coach_summary.top_priorities` - never narrative/prose. The projection
below names exactly which fields are excluded from Finding and
RoadmapAction, so the exclusion is a visible, reviewable decision (per the
Phase 6 execution prompt) rather than a silently loose assertion. Trend and
Risk are captured whole: neither carries an LLM- or template-narrated prose
field (`Risk.impact` is a fixed, code-generated sentence produced by the
deterministic core, not agent output).

Floats are rounded to a fixed precision before comparison/serialization so
ordinary re-runs of an already-deterministic pipeline cannot produce diff
noise from float representation alone.
"""

import json
from pathlib import Path

import pytest

from agents import graph as g
from utils import finance_calc as fc
from utils import ingestion

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = REPO_ROOT / "fixtures" / "golden"

GOLDEN_NAMES = ("stable_high_surplus", "negative_cashflow", "income_drop_rising_dining")

_FLOAT_PRECISION = 6

_FINDING_FIELDS = ("finding_id", "severity", "urgency", "confidence", "fact_or_inference")
# excluded from Finding: type, title, metric_refs, trend_refs, impact,
# recommended_response - human-readable text, not a number/enum to freeze.
_ACTION_FIELDS = ("action_id", "priority")
# excluded from RoadmapAction: severity, urgency, timeframe, title,
# rationale, monthly_amount, metric_refs, finding_refs, risk_refs - the
# plan's task list asks this test to pin only an action's identity and its
# position in priority order, not its full shape.

_NARRATIVE_RESULT_KEYS = ("spending_result", "budget_result", "savings_result", "debt_result")


def _round_floats(obj):
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return round(obj, _FLOAT_PRECISION)
    if isinstance(obj, dict):
        return {key: _round_floats(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round_floats(value) for value in obj]
    return obj


def _project(entry: dict, fields: tuple) -> dict:
    return {field: entry.get(field) for field in fields}


def _run_pipeline(profile: dict):
    df = fc._transactions_to_frame(profile.get("transactions") or [])
    flags = ingestion.detect_data_quality_issues(df) if not df.empty else []
    snapshot = fc.calculate_financial_snapshot(profile, data_quality_flags=flags)
    trends = fc.compute_trends(profile, snapshot)
    findings = fc.derive_findings(snapshot, trends)
    risks = fc.derive_risks(snapshot, findings)
    snapshot["risk_flags"] = fc.project_risk_flags(risks)
    result = g.run_graph(profile, snapshot, findings, risks, trends)
    return snapshot, trends, findings, risks, result


def _build_captured(snapshot, trends, findings, risks, result) -> dict:
    roadmap = result["roadmap_result"]
    return _round_floats({
        "snapshot_metrics": snapshot["metrics"],
        "trends": trends,
        "findings": [_project(f, _FINDING_FIELDS) for f in findings],
        "risks": risks,
        "roadmap_allocation": roadmap["allocation"],
        "roadmap_actions": [_project(a, _ACTION_FIELDS) for a in roadmap["actions"]],
        "coach_top_priorities": result["coach_summary"]["top_priorities"],
    })


def capture_golden(profile: dict) -> dict:
    """The single place both the frozen `*.expected.json` files and this
    test's live pipeline output must agree on, so freezing and verifying
    can never silently drift apart from each other."""
    snapshot, trends, findings, risks, result = _run_pipeline(profile)
    return _build_captured(snapshot, trends, findings, risks, result)


def _load_profile(name: str) -> dict:
    with (GOLDEN_DIR / f"{name}.input.json").open() as f:
        return json.load(f)


def _load_expected(name: str) -> dict:
    with (GOLDEN_DIR / f"{name}.expected.json").open() as f:
        return json.load(f)


@pytest.mark.parametrize("name", GOLDEN_NAMES)
def test_golden_fixture_matches_frozen_output(name):
    actual = capture_golden(_load_profile(name))
    expected = _load_expected(name)
    assert actual == expected


@pytest.mark.parametrize("name", GOLDEN_NAMES)
def test_golden_fixture_ignores_narrative_reword(name):
    """A reworded specialist narrative must not fail the golden test - the
    captured structure never includes a narrative/prose field at all, so a
    wording change is invisible to this comparison by construction, not by
    a fragile string-matching exclusion list."""
    profile = _load_profile(name)
    snapshot, trends, findings, risks, result = _run_pipeline(profile)

    result["roadmap_result"]["narrative"] = "This sentence did not exist when the fixture was frozen."
    for key in _NARRATIVE_RESULT_KEYS:
        if result.get(key):
            result[key]["narrative"] = "Completely different wording than what was frozen."
    for goal_result in result.get("goal_result") or []:
        goal_result["narrative"] = "Completely different goal wording than what was frozen."

    actual = _build_captured(snapshot, trends, findings, risks, result)
    expected = _load_expected(name)
    assert actual == expected
