"""Reports & Tracker (Architecture Plan.md, Component 4 - Reporting).

A pure formatter over values Phases 1-5 already produced. The strongest
design signal for this module: if a number is needed here that is not
already present in `profile`/`snapshot`/`trends`/`findings`/`risks`/
`roadmap`/`coach_summary`, that is an upstream bug to report, not something
to compute here. A single arithmetic operation in this file is how "the
report says something different from the app" begins.

Content assembly (`assemble_report_content` - choosing what to include, in
what order) is kept separate from markdown formatting
(`format_report_markdown`), so assembly is unit-testable on plain dicts/
lists without ever comparing rendered strings.
"""

from __future__ import annotations

from typing import List

from utils.contracts import (
    CoachSummary, Finding, FinancialProfile, FinancialSnapshot, Risk, Roadmap, ReportPackage, TrackerRow, Trend,
)
from utils.currency import format_money

# Architecture Plan.md's own words for this limitation, reused verbatim so
# the two documents cannot drift apart over separate edits.
EDUCATIONAL_ADVICE_LIMITATION = (
    "This application provides educational financial planning, not investment, "
    "tax, legal, or regulated financial advice. It must never invent account "
    "values, rates, or user constraints."
)

# The Coach Summary's fixed section order (Phase 5, utils/coach.py's
# _ID_LIST_SECTIONS plus its remaining fields), reused as data here too:
# (CoachSummary field name, section heading). Iterating this rather than
# writing out the sections as a sequence of prose/if-statements is what
# keeps "fixed order" an enforced fact instead of a convention someone can
# silently reorder in one of the two places it is written.
_COACH_SECTIONS = (
    ("overall_health", "Overall Health"),
    ("what_changed", "What Changed"),
    ("critical_risks", "Critical Risks"),
    ("important_patterns", "Important Patterns"),
    ("positive_changes", "Positive Changes"),
    ("top_priorities", "Top Priorities"),
    ("actions_this_week", "Actions This Week"),
    ("actions_this_month", "Actions This Month"),
    ("actions_next_90_days", "Actions Next 90 Days"),
    ("actions_long_term", "Actions Long Term"),
    ("assumptions_and_limitations", "Assumptions & Limitations"),
)

_DEFAULT_TRACKER_MONTHS = 12


# --------------------------------------------------------------------------
# Assembly: choosing what a report contains and in what order. No
# arithmetic beyond reading a value or copying a list/dict verbatim.
# --------------------------------------------------------------------------

def _assemble_profile_inputs(profile: FinancialProfile) -> dict:
    return {
        "monthly_income": profile.get("monthly_income"),
        "current_savings": profile.get("current_savings"),
        "debts": profile.get("debts") or [],
        "goals": profile.get("goals") or [],
        "constraints": profile.get("constraints") or {},
    }


def _assemble_health(snapshot: FinancialSnapshot) -> dict:
    return {
        "score": snapshot["health_score"],
        "band": snapshot["health_band"],
        "metrics": dict(snapshot["metrics"]),
    }


def _assemble_findings(findings: List[Finding]) -> List[dict]:
    return [
        {
            "finding_id": f["finding_id"], "title": f["title"], "severity": f["severity"],
            "urgency": f["urgency"], "trend_refs": f.get("trend_refs") or [],
        }
        for f in findings
    ]


def _assemble_risks(risks: List[Risk]) -> List[dict]:
    return [
        {
            "risk_id": r["risk_id"], "category": r["category"], "severity": r["severity"],
            "urgency": r["urgency"], "finding_refs": r.get("finding_refs") or [],
        }
        for r in risks
    ]


def _assemble_actions(roadmap: Roadmap) -> List[dict]:
    return [
        {
            "action_id": a["action_id"], "priority": a["priority"], "title": a["title"],
            "timeframe": a["timeframe"], "monthly_amount": a["monthly_amount"],
            "finding_refs": a.get("finding_refs") or [], "risk_refs": a.get("risk_refs") or [],
        }
        for a in roadmap["actions"]
    ]


def _assemble_coach_sections(coach_summary: CoachSummary) -> List[tuple]:
    return [(heading, coach_summary[field]) for field, heading in _COACH_SECTIONS]


def assemble_report_content(
    profile: FinancialProfile, snapshot: FinancialSnapshot, trends: List[Trend], findings: List[Finding],
    risks: List[Risk], roadmap: Roadmap, coach_summary: CoachSummary,
) -> dict:
    """The one place deciding what a report contains and in what order.
    Every value is read from its upstream input, never derived - trends are
    copied whole (they carry no prose), findings/risks/actions are narrowed
    to the fields a report shows plus whatever refs they carry (so those
    refs can be checked against this same content for resolution)."""
    return {
        "profile_inputs": _assemble_profile_inputs(profile),
        "health": _assemble_health(snapshot),
        "trends": list(trends),
        "findings": _assemble_findings(findings),
        "risks": _assemble_risks(risks),
        "roadmap_allocation": dict(roadmap["allocation"]),
        "roadmap_actions": _assemble_actions(roadmap),
        "coach_sections": _assemble_coach_sections(coach_summary),
        "assumptions": roadmap.get("assumptions_used") or {},
        "data_quality_flags": list(snapshot.get("data_quality_flags") or []),
        "educational_advice_limitation": EDUCATIONAL_ADVICE_LIMITATION,
    }


# --------------------------------------------------------------------------
# Formatting: assembled content -> markdown. String templating only - no
# value here is computed, only read from what assembly already selected.
# --------------------------------------------------------------------------

def _format_debts(debts: list, currency=None) -> str:
    if not debts:
        return "_No debts on file._"
    return "\n".join(f"- **{d['name']}**: {format_money(d['balance'], currency, 2)} at {d['apr']}% APR" for d in debts)


def _format_goals(goals: list, currency=None) -> str:
    if not goals:
        return "_No goals on file._"
    return "\n".join(
        f"- **{g['name']}**: {format_money(g['amount'], currency, 2)} in {g['months']} months "
        f"({format_money(g.get('current', 0), currency, 2)} saved so far)"
        for g in goals
    )


# Display rounding policy, decided once and applied everywhere in this
# module: every plain (non-currency) number shown in the report is rounded
# to 2 decimal places for readability. This changes only the string shown,
# never the value in `content` - assembly above still carries the exact,
# unrounded figure from snapshot/trends.
_DISPLAY_DECIMALS = 2


def _format_number_for_display(value) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{_DISPLAY_DECIMALS}f}"
    return str(value)


_HEALTH_METRIC_LABELS = (
    ("average_monthly_expenses", "Average monthly expenses"),
    ("gross_surplus", "Gross surplus"),
    ("allocatable_surplus", "Allocatable surplus"),
    ("savings_rate_percent", "Savings rate (%)"),
    ("debt_to_income_percent", "Debt-to-income (%)"),
    ("emergency_fund_months", "Emergency fund (months)"),
    ("total_debt", "Total debt"),
    ("net_worth", "Net worth"),
)


def _format_health(health: dict) -> str:
    lines = [f"**Health score:** {health['score']}/100 ({health['band']})", ""]
    for key, label in _HEALTH_METRIC_LABELS:
        value = health["metrics"].get(key)
        lines.append(f"- {label}: {_format_number_for_display(value)}")
    return "\n".join(lines)


def _format_trends(trends: list) -> str:
    if not trends:
        return "_No trends available._"
    return "\n".join(
        f"- `{t['trend_id']}` ({t['metric']}): {_format_number_for_display(t['start_value'])} -> "
        f"{_format_number_for_display(t['end_value'])} [{t['classification']}, {t['direction']}]"
        for t in trends
    )


def _format_findings(findings: list) -> str:
    if not findings:
        return "_No findings._"
    return "\n".join(f"- `{f['finding_id']}` [{f['severity']}/{f['urgency']}]: {f['title']}" for f in findings)


def _format_risks(risks: list) -> str:
    if not risks:
        return "_No risks identified._"
    return "\n".join(f"- `{r['risk_id']}` [{r['severity']}/{r['urgency']}] ({r['category']})" for r in risks)


def _format_roadmap(allocation: dict, actions: list, currency=None) -> str:
    # buffer_reserved is a planning constraint, not a monthly transfer - it
    # gets its own labeled line, set apart from the distributed-amount list,
    # rather than being folded into that list or any total below it.
    lines = [
        f"**Buffer reserved (planning constraint, not a distributed transfer):** {format_money(allocation['buffer_reserved'], currency, 2)}",
        "",
        "**Distributed monthly allocation:**",
        f"- Extra debt payment: {format_money(allocation['debt_extra_payment'], currency, 2)}",
        f"- Savings contribution: {format_money(allocation['savings_contribution'], currency, 2)}",
        f"- Investment contribution: {format_money(allocation['investment_contribution'], currency, 2)}",
    ]
    for goal_name, amount in allocation["goal_contributions"].items():
        lines.append(f"- Goal contribution ({goal_name}): {format_money(amount, currency, 2)}")
    lines.append("")
    lines.append("**Actions, in priority order:**")
    for action in sorted(actions, key=lambda a: a["priority"]):
        lines.append(
            f"{action['priority']}. **{action['title']}** ({action['timeframe']}): "
            f"{format_money(action['monthly_amount'], currency, 2)}/mo"
        )
    return "\n".join(lines)


def _format_coach_sections(sections: list) -> str:
    lines = []
    for heading, value in sections:
        lines.append(f"**{heading}:**")
        if isinstance(value, list):
            lines.append(", ".join(value) if value else "_none_")
        else:
            lines.append(str(value))
        lines.append("")
    return "\n".join(lines).rstrip()


def _format_assumptions(assumptions: dict) -> str:
    if not assumptions:
        return "_Defaults in effect; no customized assumptions on file._"
    return "\n".join(f"- {key}: {value}" for key, value in assumptions.items())


def _format_data_quality(flags: list) -> str:
    if not flags:
        return "_None noted._"
    return "\n".join(f"- {flag['detail']}" for flag in flags)


def format_report_markdown(content: dict) -> str:
    profile_inputs = content["profile_inputs"]
    currency = content["assumptions"].get("currency")
    sections = [
        "# Financial Coach Report",
        "",
        "## Profile Inputs",
        f"- Monthly income: {profile_inputs['monthly_income']}",
        f"- Current savings: {profile_inputs['current_savings']}",
        "",
        "### Debts",
        _format_debts(profile_inputs["debts"], currency),
        "",
        "### Goals",
        _format_goals(profile_inputs["goals"], currency),
        "",
        "## Health Metrics",
        _format_health(content["health"]),
        "",
        "## Trends",
        _format_trends(content["trends"]),
        "",
        "## Findings",
        _format_findings(content["findings"]),
        "",
        "## Risks",
        _format_risks(content["risks"]),
        "",
        "## Roadmap",
        _format_roadmap(content["roadmap_allocation"], content["roadmap_actions"], currency),
        "",
        "## Coach Summary",
        _format_coach_sections(content["coach_sections"]),
        "",
        "## Assumptions",
        _format_assumptions(content["assumptions"]),
        "",
        "## Data Quality Limitations",
        _format_data_quality(content["data_quality_flags"]),
        "",
        "## Important",
        content["educational_advice_limitation"],
    ]
    return "\n".join(sections)


# --------------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------------

def build_report(
    profile: FinancialProfile, snapshot: FinancialSnapshot, trends: List[Trend], findings: List[Finding],
    risks: List[Risk], roadmap: Roadmap, coach_summary: CoachSummary,
) -> ReportPackage:
    content = assemble_report_content(profile, snapshot, trends, findings, risks, roadmap, coach_summary)
    return {
        "schema_version": "1.0",
        "report_markdown": format_report_markdown(content),
        "tracker_rows": build_tracker(roadmap),
        "filename_stem": "financial_coach_report",
    }


def build_tracker(roadmap: Roadmap, months: int = _DEFAULT_TRACKER_MONTHS) -> List[TrackerRow]:
    """One row per month, repeating the roadmap's already-decided monthly
    allocation unchanged. MVP 1 has no per-goal timeline (TrackerRow.
    goal_contributions is one aggregate figure, not a per-goal breakdown,
    and nothing here tracks a goal reaching its target and dropping off) -
    this is a flat schedule of the same distributed amounts repeated for
    the requested number of months, not a projection that changes over
    time. Summing the per-goal contributions into one number is the only
    aggregation this module performs; it introduces no new figure that
    wasn't already in `roadmap.allocation`."""
    allocation = roadmap["allocation"]
    total_goal_contributions = sum(allocation["goal_contributions"].values())
    return [
        {
            "month": f"Month {i}",
            "planned_savings": allocation["savings_contribution"],
            "planned_investment": allocation["investment_contribution"],
            "extra_debt_payment": allocation["debt_extra_payment"],
            "goal_contributions": total_goal_contributions,
        }
        for i in range(1, months + 1)
    ]
