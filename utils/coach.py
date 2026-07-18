"""Coach Synthesis (Architecture Plan.md, Coach Synthesis).

This is selection and ranking over what Phases 2-4 already produced, not
generation. Every element `synthesize_coach_summary()` emits is an ID that
already resolves against `trends`/`findings`/`risks`/`roadmap.actions` -
nothing here invents a number, a risk, or a finding. It does not implement
trade-off suppression beyond urgency-based bucketing (Important-tier, not
this phase's job).

The section order is represented as data (`_ID_LIST_SECTIONS` below), not a
sequence of string concatenations - each section is independently testable,
reorderable, and driven by one small pure function a reader can point to
when asking "why is this here?".

NOTE on urgency-to-bucket naming: `Urgency` (utils/contracts.py) has exactly
four values - immediate, this_month, next_90_days, long_term - and
`CoachSummary` has exactly four action buckets - this_week, this_month,
next_90_days, long_term. The shapes line up 4-to-4, and `immediate ->
actions_this_week` is the only mapping that doesn't invent a fifth value or
leave a bucket permanently empty, so that is what this module does. It is
a naming choice (an "immediate" action is presented to the user under
"this week"), not new data - flagged here rather than assumed silently.
"""

from __future__ import annotations

from typing import List

from utils.contracts import CoachSummary, Finding, FinancialSnapshot, Risk, Roadmap, Trend

_MAX_TOP_PRIORITIES = 3

_URGENCY_TO_BUCKET = {
    "immediate": "actions_this_week",
    "this_month": "actions_this_month",
    "next_90_days": "actions_next_90_days",
    "long_term": "actions_long_term",
}

_NON_STABLE_CLASSIFICATIONS = ("sharp_increase", "sharp_decrease", "moderate_increase", "moderate_decrease")


def _overall_health(snapshot: FinancialSnapshot, risks: List[Risk]) -> str:
    critical_count = sum(1 for risk in risks if risk["severity"] == "critical")
    band = snapshot["health_band"]
    if critical_count == 0:
        return f"{band}."
    plural = "risk" if critical_count == 1 else "risks"
    word = {1: "one"}.get(critical_count, str(critical_count))
    return f"{band}, with {word} critical near-term {plural}."


def _what_changed(trends: List[Trend]) -> List[str]:
    return [t["trend_id"] for t in trends if t["classification"] in _NON_STABLE_CLASSIFICATIONS]


def _critical_risks(risks: List[Risk]) -> List[str]:
    return [r["risk_id"] for r in risks if r["severity"] == "critical"]


def _important_patterns(findings: List[Finding]) -> List[str]:
    return [
        f["finding_id"] for f in findings
        if f["severity"] in ("critical", "high", "medium") and f["type"] != "data_quality"
    ]


def _positive_changes(findings: List[Finding]) -> List[str]:
    return [f["finding_id"] for f in findings if f["severity"] == "positive"]


# Section order as data (Phase 5 execution prompt): each entry is
# (CoachSummary field name, pure function computing that field's ID list).
_ID_LIST_SECTIONS = (
    ("what_changed", lambda snapshot, trends, findings, risks: _what_changed(trends)),
    ("critical_risks", lambda snapshot, trends, findings, risks: _critical_risks(risks)),
    ("important_patterns", lambda snapshot, trends, findings, risks: _important_patterns(findings)),
    ("positive_changes", lambda snapshot, trends, findings, risks: _positive_changes(findings)),
)


def _top_priorities(roadmap: Roadmap) -> List[str]:
    # roadmap.actions is already priority-ordered (1 = most important) by
    # build_roadmap() - taking the first N is the whole ranking rule.
    return [a["action_id"] for a in roadmap["actions"][:_MAX_TOP_PRIORITIES]]


def _action_buckets(roadmap: Roadmap) -> dict:
    buckets = {bucket: [] for bucket in _URGENCY_TO_BUCKET.values()}
    for action in roadmap["actions"]:
        bucket = _URGENCY_TO_BUCKET.get(action["urgency"])
        if bucket is not None:
            buckets[bucket].append(action["action_id"])
    return buckets


def _assumptions_and_limitations(roadmap: Roadmap, snapshot: FinancialSnapshot) -> str:
    assumptions = roadmap.get("assumptions_used") or {}
    lines = []
    if assumptions:
        lines.append(
            f"Assumptions in effect: {assumptions.get('needs_ratio', 0) * 100:.0f}/"
            f"{assumptions.get('wants_ratio', 0) * 100:.0f}/{assumptions.get('savings_ratio', 0) * 100:.0f} "
            f"needs/wants/savings split, {assumptions.get('savings_apy', 0) * 100:.1f}% savings APY, "
            f"{assumptions.get('emergency_fund_months', 0)}-month emergency fund target."
        )
    data_quality_flags = snapshot.get("data_quality_flags") or []
    if data_quality_flags:
        lines.append("Data limitations: " + "; ".join(flag["detail"] for flag in data_quality_flags) + ".")
    if not lines:
        return "No assumption or data-quality limitations to disclose."
    return " ".join(lines)


def synthesize_coach_summary(
    snapshot: FinancialSnapshot, trends: List[Trend], findings: List[Finding], risks: List[Risk],
    roadmap: Roadmap, specialist_results: dict,
) -> CoachSummary:
    """`specialist_results` is accepted to match the signature specified in
    Architecture Plan.md, Component 4, but is not currently consumed - every
    section below is fully derivable from snapshot/trends/findings/risks/
    roadmap, and inventing a use for an unneeded parameter would itself
    violate this phase's "no freestanding new claims" rule."""
    id_lists = {
        field: fn(snapshot, trends, findings, risks) for field, fn in _ID_LIST_SECTIONS
    }
    buckets = _action_buckets(roadmap)

    return {
        "schema_version": "1.0",
        "overall_health": _overall_health(snapshot, risks),
        "what_changed": id_lists["what_changed"],
        "critical_risks": id_lists["critical_risks"],
        "important_patterns": id_lists["important_patterns"],
        "positive_changes": id_lists["positive_changes"],
        "top_priorities": _top_priorities(roadmap),
        "actions_this_week": buckets["actions_this_week"],
        "actions_this_month": buckets["actions_this_month"],
        "actions_next_90_days": buckets["actions_next_90_days"],
        "actions_long_term": buckets["actions_long_term"],
        "assumptions_and_limitations": _assumptions_and_limitations(roadmap, snapshot),
    }
