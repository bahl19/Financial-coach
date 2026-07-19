"""Phase 7 tests: utils/reporting.py (build_report / build_tracker).

Each test maps to a Phase 7 exit-gate item in `Implementation Plan - MVP 1.md`.
Assembly is tested on the plain dict `assemble_report_content()` returns,
never by comparing rendered markdown strings - per the Phase 7 execution
prompt's "separate content assembly from formatting... mixing them forces
every test to assert on formatted text, which is brittle."
"""

import json
from pathlib import Path

import pytest

from utils import finance_calc as fc
from utils import ingestion
from utils import reporting as rp
from utils.coach import synthesize_coach_summary
from utils.roadmap import build_roadmap

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
    roadmap = build_roadmap(profile, snapshot, findings, risks)
    coach_summary = synthesize_coach_summary(snapshot, trends, findings, risks, roadmap, {})
    return snapshot, trends, findings, risks, roadmap, coach_summary


# --------------------------------------------------------------------------
# Gate: "Exported values match the source snapshot and roadmap exactly (no
# independently recalculated numbers)"
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", ALL_PROFILE_FIXTURES, ids=lambda p: p.stem)
def test_assembled_content_matches_source_values_exactly(path):
    profile = _load(path)
    snapshot, trends, findings, risks, roadmap, coach_summary = _run_pipeline(profile)
    content = rp.assemble_report_content(profile, snapshot, trends, findings, risks, roadmap, coach_summary)

    assert content["health"]["score"] == snapshot["health_score"]
    assert content["health"]["band"] == snapshot["health_band"]
    assert content["health"]["metrics"] == snapshot["metrics"]
    assert content["trends"] == trends
    assert content["roadmap_allocation"] == roadmap["allocation"]
    assert [a["action_id"] for a in content["roadmap_actions"]] == [a["action_id"] for a in roadmap["actions"]]
    assert [a["priority"] for a in content["roadmap_actions"]] == [a["priority"] for a in roadmap["actions"]]
    for assembled, original in zip(content["findings"], findings):
        assert assembled["finding_id"] == original["finding_id"]
        assert assembled["severity"] == original["severity"]
        assert assembled["urgency"] == original["urgency"]
    for assembled, original in zip(content["risks"], risks):
        assert assembled["risk_id"] == original["risk_id"]
        assert assembled["severity"] == original["severity"]
        assert assembled["urgency"] == original["urgency"]


def test_build_report_tracker_rows_are_produced_by_build_tracker():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    snapshot, trends, findings, risks, roadmap, coach_summary = _run_pipeline(profile)
    report = rp.build_report(profile, snapshot, trends, findings, risks, roadmap, coach_summary)
    assert report["tracker_rows"] == rp.build_tracker(roadmap)


# --------------------------------------------------------------------------
# Gate: "A report with no debts or goals still renders"
# --------------------------------------------------------------------------

def test_report_with_no_debts_or_goals_still_renders():
    profile = _load(FIXTURES_DIR / "empty_debts_goals_profile.json")
    snapshot, trends, findings, risks, roadmap, coach_summary = _run_pipeline(profile)
    report = rp.build_report(profile, snapshot, trends, findings, risks, roadmap, coach_summary)
    assert report["report_markdown"]
    assert "No debts on file" in report["report_markdown"]
    assert "No goals on file" in report["report_markdown"]


# --------------------------------------------------------------------------
# Gate: "Tracker totals do not exceed the roadmap's distributed allocation
# (excluding buffer_reserved)"
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", ALL_PROFILE_FIXTURES, ids=lambda p: p.stem)
def test_tracker_row_totals_never_exceed_distributed_allocation(path):
    profile = _load(path)
    _, _, _, _, roadmap, _ = _run_pipeline(profile)
    allocation = roadmap["allocation"]
    distributed_total = (
        allocation["debt_extra_payment"] + allocation["savings_contribution"] + sum(allocation["goal_contributions"].values())
    )
    for row in rp.build_tracker(roadmap):
        row_total = row["planned_savings"] + row["extra_debt_payment"] + row["goal_contributions"]
        assert row_total <= distributed_total + 1e-9
        assert "buffer_reserved" not in row


def test_tracker_defaults_to_twelve_months():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    _, _, _, _, roadmap, _ = _run_pipeline(profile)
    rows = rp.build_tracker(roadmap)
    assert len(rows) == 12
    assert [row["month"] for row in rows] == [f"Month {i}" for i in range(1, 13)]


def test_tracker_honors_a_custom_month_count():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    _, _, _, _, roadmap, _ = _run_pipeline(profile)
    rows = rp.build_tracker(roadmap, months=3)
    assert len(rows) == 3


# --------------------------------------------------------------------------
# Gate: "Report renders the Coach Summary's fixed section order"
# --------------------------------------------------------------------------

def test_coach_sections_appear_in_the_fixed_order():
    profile = _load(GOLDEN_DIR / "negative_cashflow.input.json")
    snapshot, trends, findings, risks, roadmap, coach_summary = _run_pipeline(profile)
    content = rp.assemble_report_content(profile, snapshot, trends, findings, risks, roadmap, coach_summary)
    assert [field for field, _heading in rp._COACH_SECTIONS] == [
        "overall_health", "what_changed", "critical_risks", "important_patterns", "positive_changes",
        "top_priorities", "actions_this_week", "actions_this_month", "actions_next_90_days", "actions_long_term",
        "assumptions_and_limitations",
    ]
    headings_in_content = [heading for heading, _value in content["coach_sections"]]
    headings_in_markdown = rp.format_report_markdown(content)
    last_index = -1
    for heading in headings_in_content:
        index = headings_in_markdown.find(f"**{heading}:**")
        assert index > last_index, f"{heading!r} did not appear in order in the rendered report"
        last_index = index


# --------------------------------------------------------------------------
# Gate: "Every cited finding_id/risk_id/trend_id/action_id resolves"
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", ALL_PROFILE_FIXTURES, ids=lambda p: p.stem)
def test_every_cited_ref_resolves_within_the_assembled_report(path):
    profile = _load(path)
    snapshot, trends, findings, risks, roadmap, coach_summary = _run_pipeline(profile)
    content = rp.assemble_report_content(profile, snapshot, trends, findings, risks, roadmap, coach_summary)

    finding_ids = {f["finding_id"] for f in content["findings"]}
    risk_ids = {r["risk_id"] for r in content["risks"]}
    trend_ids = {t["trend_id"] for t in content["trends"]}
    action_ids = {a["action_id"] for a in content["roadmap_actions"]}

    for finding in content["findings"]:
        for ref in finding["trend_refs"]:
            assert ref in trend_ids, f"finding {finding['finding_id']} cites unknown trend_id {ref!r}"
    for risk in content["risks"]:
        for ref in risk["finding_refs"]:
            assert ref in finding_ids, f"risk {risk['risk_id']} cites unknown finding_id {ref!r}"
    for action in content["roadmap_actions"]:
        for ref in action["finding_refs"]:
            assert ref in finding_ids, f"action {action['action_id']} cites unknown finding_id {ref!r}"
        for ref in action["risk_refs"]:
            assert ref in risk_ids, f"action {action['action_id']} cites unknown risk_id {ref!r}"

    # top_priorities/action buckets in the Coach Summary must also resolve
    # against this report's own action list.
    for _heading, value in content["coach_sections"]:
        if not isinstance(value, list):
            continue
        for item in value:
            assert item in action_ids or item in finding_ids or item in risk_ids or item in trend_ids, (
                f"coach summary cites unknown id {item!r}"
            )


# --------------------------------------------------------------------------
# Gate: "buffer_reserved is visually and semantically distinct from
# distributed amounts"
# --------------------------------------------------------------------------

def test_buffer_reserved_is_labeled_distinctly_and_excluded_from_tracker():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    snapshot, trends, findings, risks, roadmap, coach_summary = _run_pipeline(profile)
    content = rp.assemble_report_content(profile, snapshot, trends, findings, risks, roadmap, coach_summary)
    markdown = rp.format_report_markdown(content)

    assert "Buffer reserved (planning constraint, not a distributed transfer)" in markdown
    assert "Distributed monthly allocation:" in markdown
    # the buffer line must appear before, not inside, the distributed list
    buffer_index = markdown.index("Buffer reserved")
    distributed_index = markdown.index("Distributed monthly allocation:")
    assert buffer_index < distributed_index
    for row in rp.build_tracker(roadmap):
        assert "buffer_reserved" not in row


# --------------------------------------------------------------------------
# Gate: "PR merged to main, tagged phase7-done" is a caveat, not testable here.
# --------------------------------------------------------------------------

def test_educational_advice_limitation_is_present_verbatim_from_architecture_plan():
    profile = _load(GOLDEN_DIR / "stable_high_surplus.input.json")
    snapshot, trends, findings, risks, roadmap, coach_summary = _run_pipeline(profile)
    content = rp.assemble_report_content(profile, snapshot, trends, findings, risks, roadmap, coach_summary)
    assert content["educational_advice_limitation"] == rp.EDUCATIONAL_ADVICE_LIMITATION
    assert "not investment, tax, legal, or regulated financial advice" in content["educational_advice_limitation"]
    assert content["educational_advice_limitation"] in rp.format_report_markdown(content)
