"""Roadmap planner (Architecture Plan.md, Component 4).

`build_roadmap()` is the single deterministic waterfall allocator - the
*only* place a dollar allocation decision is made anywhere in this codebase.
Every specialist agent narrates a figure this module already produced; none
of them may compute their own share of surplus. This is the fix for the
double-allocation bug that motivated this entire delivery plan (see the
"Highlighted fix" callout in Implementation Plan - MVP 1.md, Phase 3).

No LLM call decides an allocation. `explain_roadmap()` may use an LLM for
narrative tone only, and its fallback must reproduce the action list
unchanged - a missing API key must never change what the roadmap says will
happen with the user's money.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from utils.contracts import Finding, FinancialProfile, FinancialSnapshot, Risk, Roadmap
from utils.currency import format_money
from utils.finance_calc import goal_feasibility
from utils.llm import complete

# --------------------------------------------------------------------------
# Allocation ledger
# --------------------------------------------------------------------------
#
# Each waterfall step calls .take() for its desired share; the ledger
# refuses to hand out more than remains. This makes "sum(distributed
# allocation) <= allocatable_surplus" structurally impossible to violate,
# rather than a property checked after the fact.

class _AllocationLedger:
    def __init__(self, total: float):
        self._remaining = max(0.0, total)

    @property
    def remaining(self) -> float:
        return self._remaining

    def take(self, amount: float) -> float:
        """Takes up to `amount` from what is left. Returns what was
        actually taken - never more than `remaining`, never negative."""
        amount = max(0.0, amount)
        taken = min(amount, self._remaining)
        self._remaining -= taken
        return taken


# --------------------------------------------------------------------------
# Named constants - every ratio and threshold below is a documented
# decision, never a bare literal at the call site.
# --------------------------------------------------------------------------

_STARTER_BUFFER_SHARE_OF_SURPLUS = 0.5
_DEBT_ACCEL_SHARE_OF_SURPLUS = 0.5
_HIGH_APR_THRESHOLD_PERCENT = 20.0  # a debt at or above this rate is "high-interest" for step 4

# Step 6 (remainder routing): the remaining ledger balance goes to investment
# contribution instead of plain savings only when the user's reported
# investment_cagr beats their savings_apy by at least this many percentage
# points - a deliberate margin, not a bare ">" comparison, so a trivial or
# noisy rate difference doesn't flip the recommendation. Absent investment
# data (current_investments or investment_cagr is None) always keeps
# today's behavior: 100% of the remainder goes to savings.
_CAGR_ADVANTAGE_THRESHOLD_PERCENT = 1.0

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

ACTION_RESOLVE_INPUTS = "ACTION_RESOLVE_INPUTS"
ACTION_STARTER_BUFFER = "ACTION_STARTER_BUFFER"
ACTION_ACCELERATE_DEBT = "ACTION_ACCELERATE_DEBT"
ACTION_GROW_SAVINGS = "ACTION_GROW_SAVINGS"
ACTION_GROW_INVESTMENT = "ACTION_GROW_INVESTMENT"


def _slug(name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in name.upper()).strip("_")


def _finding_ids_of_type(findings: List[Finding], *types: str) -> List[str]:
    return [f["finding_id"] for f in findings if f["type"] in types]


def _risk_ids_of_category(risks: List[Risk], *categories: str) -> List[str]:
    return [r["risk_id"] for r in risks if r["category"] in categories]


def _action(
    action_id: str, priority: int, severity: str, urgency: str, timeframe: str, title: str,
    rationale: str, monthly_amount: float, metric_refs: list, finding_refs: list, risk_refs: list,
) -> dict:
    return {
        "action_id": action_id, "priority": priority, "severity": severity, "urgency": urgency,
        "timeframe": timeframe, "title": title, "rationale": rationale, "monthly_amount": monthly_amount,
        "metric_refs": metric_refs, "finding_refs": finding_refs, "risk_refs": risk_refs,
    }


def _unresolved_inputs_roadmap(
    profile: FinancialProfile, validation_issues: List[str], allocatable_surplus: Optional[float]
) -> Roadmap:
    """Step 1: resolve invalid or missing financial inputs before offering
    any monetary allocation. No LLM call - there is nothing to narrate
    beyond the issues themselves."""
    reason = "; ".join(validation_issues) if validation_issues else "Confirmed monthly income is required."
    action = _action(
        ACTION_RESOLVE_INPUTS, 1, "critical", "immediate", "Before anything else",
        "Resolve missing or invalid financial inputs", reason, 0.0, [], [], [],
    )
    return {
        "schema_version": "1.0",
        "actions": [action],
        "allocation": {
            "buffer_reserved": 0.0, "debt_extra_payment": 0.0, "goal_contributions": {},
            "savings_contribution": 0.0, "investment_contribution": 0.0,
        },
        "narrative": f"No monetary allocation is possible yet: {reason}",
        "assumptions_used": profile.get("assumptions"),
    }


def build_roadmap(
    profile: FinancialProfile, snapshot: FinancialSnapshot, findings: List[Finding], risks: List[Risk]
) -> Roadmap:
    metrics = snapshot["metrics"]
    validation_issues = snapshot.get("validation_issues") or []
    allocatable_surplus = metrics.get("allocatable_surplus")
    currency = (profile.get("assumptions") or {}).get("currency")

    if validation_issues or allocatable_surplus is None:
        return _unresolved_inputs_roadmap(profile, validation_issues, allocatable_surplus)

    ledger = _AllocationLedger(allocatable_surplus)
    actions: List[dict] = []

    # Step 2: the configured buffer and debt minimums are already excluded
    # from allocatable_surplus by construction (Surplus and Allocation
    # Semantics) - nothing to allocate here, only to record for transparency.
    buffer_reserved = float((profile.get("constraints") or {}).get("minimum_monthly_buffer") or 0.0)

    # Step 3: starter emergency buffer when coverage is below target.
    starter_buffer_amount = 0.0
    emergency_months = metrics.get("emergency_fund_months")
    target_months = (profile.get("assumptions") or {}).get("emergency_fund_months")
    if emergency_months is not None and target_months and emergency_months < target_months:
        starter_buffer_amount = ledger.take(_STARTER_BUFFER_SHARE_OF_SURPLUS * allocatable_surplus)
        if starter_buffer_amount > 0:
            emergency_severity = "critical" if emergency_months <= 0 else "high"
            actions.append(_action(
                ACTION_STARTER_BUFFER, 0, emergency_severity, "this_month", "This month",
                "Build a starter emergency buffer", "Emergency coverage is below the chosen target.",
                starter_buffer_amount, ["emergency_fund_months"],
                _finding_ids_of_type(findings, "emergency_fund_risk"),
                _risk_ids_of_category(risks, "savings"),
            ))

    # Step 4: direct remaining debt allocation toward avalanche when
    # high-interest debt exists.
    debts = profile.get("debts") or []
    debt_extra_payment = 0.0
    has_high_interest_debt = any((debt.get("apr") or 0.0) >= _HIGH_APR_THRESHOLD_PERCENT for debt in debts)
    if debts and has_high_interest_debt:
        debt_extra_payment = ledger.take(_DEBT_ACCEL_SHARE_OF_SURPLUS * allocatable_surplus)
        if debt_extra_payment > 0:
            actions.append(_action(
                ACTION_ACCELERATE_DEBT, 0, "high", "this_month", "This month",
                "Accelerate high-interest debt payoff",
                "Paying only minimums on high-APR debt accrues avoidable interest.",
                debt_extra_payment, ["total_debt"],
                _finding_ids_of_type(findings, "debt_risk"),
                _risk_ids_of_category(risks, "debt"),
            ))

    # Step 5: fund feasible high-priority goals from remaining surplus, in
    # priority order, greedily until the ledger is exhausted.
    goal_contributions: Dict[str, float] = {}
    sorted_goals = sorted(
        profile.get("goals") or [], key=lambda goal: _PRIORITY_ORDER.get(goal.get("priority"), len(_PRIORITY_ORDER))
    )
    for goal in sorted_goals:
        if ledger.remaining <= 0:
            break
        feasibility = goal_feasibility(
            goal.get("amount", 0.0), goal.get("months", 0), ledger.remaining, goal.get("current", 0.0)
        )
        amount = ledger.take(feasibility["required_monthly"])
        if amount <= 0:
            continue
        goal_contributions[goal["name"]] = amount
        # feasibility["feasible"] was computed against ledger.remaining - the
        # surplus genuinely still available at this point in the waterfall -
        # so it is the authoritative answer to "does this goal's contribution
        # cover its required_monthly?", unlike snapshot.goal_results (a
        # preliminary, allocation-unaware check against the *full*
        # allocatable_surplus, run before this waterfall and before any
        # higher-priority step or earlier goal has claimed its share). A goal
        # can pass that preliminary check yet still be underfunded here.
        # Elevate the action itself when that happens so the shortfall is
        # visible in the roadmap/coach summary, not only inside this one
        # goal's own specialist narrative.
        underfunded = not feasibility["feasible"]
        actions.append(_action(
            f"ACTION_FUND_GOAL_{_slug(goal['name'])}", 0,
            "high" if underfunded else "medium",
            "this_month" if underfunded else "next_90_days",
            "This month" if underfunded else "Next 90 days",
            f"Fund goal: {goal['name']}",
            (
                f"Contributing {format_money(amount, currency)}/month toward {goal['name']}, short of the "
                f"{format_money(feasibility['required_monthly'], currency)}/month required to stay on track."
            ) if underfunded else f"Contributing toward {goal['name']} at the required monthly pace.",
            amount, ["allocatable_surplus"], [], _risk_ids_of_category(risks, "goals"),
        ))

    # Step 6: remainder to savings, or to investment contribution instead
    # when the user's reported investment_cagr clears savings_apy by
    # _CAGR_ADVANTAGE_THRESHOLD_PERCENT. The starter emergency buffer above
    # is never a candidate for this - an emergency fund needs to be liquid
    # and stable, not routed toward a return that can also fall; only
    # genuinely discretionary remainder surplus is eligible.
    assumptions = profile.get("assumptions") or {}
    savings_apy = assumptions.get("savings_apy") or 0.0
    investment_cagr = assumptions.get("investment_cagr")
    current_investments = profile.get("current_investments")
    prefers_investment = (
        current_investments is not None and investment_cagr is not None
        and (investment_cagr - savings_apy) * 100 >= _CAGR_ADVANTAGE_THRESHOLD_PERCENT
    )

    remainder = ledger.take(ledger.remaining)
    remainder_to_savings = 0.0 if prefers_investment else remainder
    remainder_to_investment = remainder if prefers_investment else 0.0

    if remainder_to_investment > 0:
        actions.append(_action(
            ACTION_GROW_INVESTMENT, 0, "positive", "long_term", "Ongoing",
            "Grow investments",
            f"Remaining surplus routed to investment contribution - your reported "
            f"{investment_cagr * 100:.1f}% CAGR beats your {savings_apy * 100:.1f}% savings APY.",
            remainder_to_investment, ["gross_surplus"], [], [],
        ))
    elif remainder_to_savings > 0:
        actions.append(_action(
            ACTION_GROW_SAVINGS, 0, "positive", "long_term", "Ongoing",
            "Grow savings", "Remaining surplus after higher-priority steps.",
            remainder_to_savings, ["gross_surplus"], [], [],
        ))
    savings_contribution = starter_buffer_amount + remainder_to_savings
    investment_contribution = remainder_to_investment

    for index, action in enumerate(actions, start=1):
        action["priority"] = index

    roadmap: Roadmap = {
        "schema_version": "1.0",
        "actions": actions,
        "allocation": {
            "buffer_reserved": buffer_reserved,
            "debt_extra_payment": debt_extra_payment,
            "goal_contributions": goal_contributions,
            "savings_contribution": savings_contribution,
            "investment_contribution": investment_contribution,
        },
        "narrative": "",
        "assumptions_used": profile.get("assumptions"),
    }
    roadmap["narrative"] = explain_roadmap(roadmap, snapshot)
    return roadmap


# --------------------------------------------------------------------------
# explain_roadmap: LLM narrative with a deterministic, action-list-based
# fallback. Never changes the allocation - only prose describing it.
# --------------------------------------------------------------------------

_ROADMAP_SYSTEM_PROMPT = (
    "You are a financial coach summarizing a already-decided, deterministic action plan. "
    "Explain the plan below in plain language, in priority order. Do not invent a dollar "
    "amount, priority, or action that is not listed. Under 200 words."
)


def _fallback_roadmap_narrative(roadmap: Roadmap) -> str:
    if not roadmap["actions"]:
        return "No monetary allocation is possible until required inputs are resolved."
    currency = (roadmap.get("assumptions_used") or {}).get("currency")
    lines = ["**Your Prioritized Roadmap (offline rule-based mode)**"]
    for action in roadmap["actions"]:
        lines.append(
            f"{action['priority']}. **{action['title']}** ({action['timeframe']}): "
            f"{format_money(action['monthly_amount'], currency)}/mo — {action['rationale']}"
        )
    return "\n".join(lines)


def explain_roadmap(roadmap: Roadmap, snapshot: FinancialSnapshot) -> str:
    if not roadmap["actions"]:
        return _fallback_roadmap_narrative(roadmap)

    currency = (roadmap.get("assumptions_used") or {}).get("currency")
    summary_lines = [
        f"{a['priority']}. {a['title']} - {format_money(a['monthly_amount'], currency)}/mo ({a['timeframe']}): {a['rationale']}"
        for a in roadmap["actions"]
    ]
    summary = "Action plan:\n" + "\n".join(summary_lines)
    narrative = complete(_ROADMAP_SYSTEM_PROMPT, summary, max_tokens=400)
    if narrative is None:
        return _fallback_roadmap_narrative(roadmap)
    return narrative
