"""Canonical data contracts for the Finance Coach MVP 1 pipeline.

This module is a pure leaf: it imports nothing from `agents/` or the rest of
`utils/`, only the standard library and `typing`. Every other module may
import from here; this module must never import anything project-specific,
so that dependency direction stays one-way (Architecture Plan.md, Contract
rule 9 / dependency inversion).

No MVP 2 strategy-policy contract is defined here. MVP 1 is an independently
shippable product; the strategy-policy contracts belong to
`Architecture Plan - MVP 2.md` and must not appear in this codebase until
MVP 2 begins (see `tests/test_contracts.py`'s MVP2_CONTRACT_NAMES scan).
"""

from __future__ import annotations

from typing import Dict, List, Optional, TypedDict

SCHEMA_VERSION = "1.0"

Severity = str  # one of: "critical", "high", "medium", "low", "positive"
Urgency = str  # one of: "immediate", "this_month", "next_90_days", "long_term"
FactOrInference = str  # one of: "fact", "deterministic_inference" (MVP 1 never emits "hypothesis")

SEVERITIES = ("critical", "high", "medium", "low", "positive")
URGENCIES = ("immediate", "this_month", "next_90_days", "long_term")
FACT_OR_INFERENCE_VALUES = ("fact", "deterministic_inference")
GOAL_PRIORITIES = ("high", "medium", "low")
TRANSACTION_TYPES = ("income", "expense", "debt_payment", "transfer", "savings_transfer", "refund", "unknown")
TREND_DIRECTIONS = ("increasing", "decreasing", "flat")

_BUDGET_RATIO_TOLERANCE = 1e-6


# --------------------------------------------------------------------------
# Ingestion-level contracts
# --------------------------------------------------------------------------

class Transaction(TypedDict):
    date: str
    description: str
    amount: float
    category: str
    category_confidence: float
    needs_review: bool
    transaction_type: str


class Debt(TypedDict):
    name: str
    balance: float
    apr: float
    min_payment: float


class Goal(TypedDict):
    name: str
    amount: float
    months: int
    current: float
    priority: str


class Constraints(TypedDict):
    minimum_monthly_buffer: float
    protected_categories: List[str]


class PlanningAssumptions(TypedDict):
    currency: str
    needs_ratio: float
    wants_ratio: float
    savings_ratio: float
    savings_apy: float
    emergency_fund_months: int


class FinancialProfile(TypedDict):
    schema_version: str
    transactions: List[Transaction]
    monthly_income: Optional[float]
    current_savings: Optional[float]
    debts: List[Debt]
    goals: List[Goal]
    constraints: Constraints
    assumptions: PlanningAssumptions


class ReviewItem(TypedDict):
    transaction_index: int
    description: str
    amount: float
    suggested_category: str
    reason: str


# --------------------------------------------------------------------------
# Financial core / snapshot contracts
# --------------------------------------------------------------------------

class RiskFlag(TypedDict):
    """Backward-compatible projection of Risk[] — never an independent source."""

    code: str
    severity: str
    metric: str


class DataQualityFlag(TypedDict):
    code: str
    detail: str
    affects: List[str]


class SnapshotMetrics(TypedDict):
    average_monthly_expenses: Optional[float]
    monthly_surplus: Optional[float]  # alias of gross_surplus, kept for backward compatibility
    gross_surplus: Optional[float]
    allocatable_surplus: Optional[float]
    required_commitments: float
    savings_rate_percent: Optional[float]
    debt_to_income_percent: Optional[float]
    emergency_fund_months: Optional[float]
    total_debt: float
    period: Optional[str]
    is_partial_period: bool


class FinancialSnapshot(TypedDict):
    schema_version: str
    metrics: SnapshotMetrics
    health_score: int
    health_band: str
    risk_flags: List[RiskFlag]
    data_quality_flags: List[DataQualityFlag]
    debt_comparison: dict
    goal_results: list
    validation_issues: List[str]


# --------------------------------------------------------------------------
# Trend / Insight / Risk contracts
# --------------------------------------------------------------------------

class Trend(TypedDict):
    trend_id: str
    metric: str
    period: str
    start_value: float
    end_value: float
    absolute_change: float
    percent_change: Optional[float]
    direction: str
    classification: str


class Finding(TypedDict):
    finding_id: str
    type: str
    title: str
    severity: str
    urgency: str
    confidence: float
    fact_or_inference: str
    metric_refs: List[str]
    trend_refs: List[str]
    impact: str
    recommended_response: str


class Risk(TypedDict):
    risk_id: str
    category: str
    severity: str
    urgency: str
    likelihood: str
    impact: str
    metric_refs: List[str]
    finding_refs: List[str]
    mitigation_refs: List[str]


# --------------------------------------------------------------------------
# Roadmap / specialist / validation / coach contracts
# --------------------------------------------------------------------------

class SpecialistResult(TypedDict):
    schema_version: str
    agent: str
    narrative: str
    allocated_amount: Optional[float]
    why_allocated: Optional[str]
    expected_effect: str
    tradeoffs: str
    what_to_monitor: str
    finding_refs: List[str]
    trend_refs: List[str]
    recommends_action_ids: List[str]
    supporting_tables: dict
    live: bool


class RoadmapAction(TypedDict):
    action_id: str
    priority: int
    severity: str
    urgency: str
    timeframe: str
    title: str
    rationale: str
    monthly_amount: float
    metric_refs: List[str]
    finding_refs: List[str]
    risk_refs: List[str]


class RoadmapAllocation(TypedDict):
    buffer_reserved: float
    debt_extra_payment: float
    goal_contributions: Dict[str, float]
    savings_contribution: float


class Roadmap(TypedDict):
    schema_version: str
    actions: List[RoadmapAction]
    allocation: RoadmapAllocation
    narrative: str
    assumptions_used: PlanningAssumptions


class ValidationResult(TypedDict):
    schema_version: str
    valid: bool
    violations: List[str]
    checked_agents: List[str]
    fallback_used: bool


class CoachSummary(TypedDict):
    schema_version: str
    overall_health: str
    what_changed: List[str]
    critical_risks: List[str]
    important_patterns: List[str]
    positive_changes: List[str]
    top_priorities: List[str]
    actions_this_week: List[str]
    actions_this_month: List[str]
    actions_next_90_days: List[str]
    actions_long_term: List[str]
    assumptions_and_limitations: str


class TrackerRow(TypedDict):
    month: str
    planned_savings: float
    extra_debt_payment: float
    goal_contributions: float


class ReportPackage(TypedDict):
    schema_version: str
    report_markdown: str
    tracker_rows: List[TrackerRow]
    filename_stem: str


# --------------------------------------------------------------------------
# Defaults
# --------------------------------------------------------------------------

def default_assumptions() -> PlanningAssumptions:
    """Baseline PlanningAssumptions used until a user customizes any ratio.

    The 50/30/20 split and 4% APY are a starting heuristic, not a claim about
    any specific user's situation. The UI must display these values whenever
    they are in effect rather than applying them silently.
    """
    return {
        "currency": "USD",
        "needs_ratio": 0.50,
        "wants_ratio": 0.30,
        "savings_ratio": 0.20,
        "savings_apy": 0.04,
        "emergency_fund_months": 3,
    }


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
#
# Validators return a list of human-readable issue strings; an empty list
# means valid. They never raise on malformed input and never coerce a
# missing (None) value to a default — a malformed FinancialProfile is a
# validation issue for the UI to display, not a programming error.

def validate_assumptions(assumptions: PlanningAssumptions) -> List[str]:
    issues: List[str] = []
    if assumptions is None:
        return ["assumptions is required"]

    for key in ("needs_ratio", "wants_ratio", "savings_ratio", "savings_apy"):
        value = assumptions.get(key)
        if value is None:
            issues.append(f"{key} is required")
        elif not (0.0 <= value <= 1.0):
            issues.append(f"{key} must be between 0 and 1, got {value}")

    needs = assumptions.get("needs_ratio")
    wants = assumptions.get("wants_ratio")
    savings = assumptions.get("savings_ratio")
    if None not in (needs, wants, savings):
        total = needs + wants + savings
        if abs(total - 1.0) > _BUDGET_RATIO_TOLERANCE:
            issues.append(f"needs_ratio + wants_ratio + savings_ratio must total 1.0, got {total}")

    emergency_fund_months = assumptions.get("emergency_fund_months")
    if emergency_fund_months is not None and emergency_fund_months < 0:
        issues.append(f"emergency_fund_months must be >= 0, got {emergency_fund_months}")

    return issues


def _validate_debt(debt: Debt, label: str) -> List[str]:
    issues: List[str] = []
    balance = debt.get("balance")
    min_payment = debt.get("min_payment")
    apr = debt.get("apr")
    if balance is not None and balance < 0:
        issues.append(f"{label}: balance must be >= 0, got {balance}")
    if min_payment is not None and min_payment < 0:
        issues.append(f"{label}: min_payment must be >= 0, got {min_payment}")
    if apr is not None and apr < 0:
        issues.append(f"{label}: apr must be >= 0, got {apr}")
    return issues


def _validate_goal(goal: Goal, label: str) -> List[str]:
    issues: List[str] = []
    amount = goal.get("amount")
    months = goal.get("months")
    current = goal.get("current")
    priority = goal.get("priority")
    if amount is not None and amount < 0:
        issues.append(f"{label}: amount must be >= 0, got {amount}")
    if months is not None and months < 0:
        issues.append(f"{label}: months must be >= 0, got {months}")
    if current is not None and current < 0:
        issues.append(f"{label}: current must be >= 0, got {current}")
    if priority is not None and priority not in GOAL_PRIORITIES:
        issues.append(f"{label}: priority must be one of {GOAL_PRIORITIES}, got {priority!r}")
    return issues


def validate_profile(profile: FinancialProfile) -> List[str]:
    issues: List[str] = []
    if profile is None:
        return ["profile is required"]

    monthly_income = profile.get("monthly_income")
    if monthly_income is not None and monthly_income < 0:
        issues.append(f"monthly_income must be >= 0, got {monthly_income}")

    current_savings = profile.get("current_savings")
    if current_savings is not None and current_savings < 0:
        issues.append(f"current_savings must be >= 0, got {current_savings}")

    for i, debt in enumerate(profile.get("debts") or []):
        issues.extend(_validate_debt(debt, debt.get("name") or f"debts[{i}]"))

    for i, goal in enumerate(profile.get("goals") or []):
        issues.extend(_validate_goal(goal, goal.get("name") or f"goals[{i}]"))

    constraints = profile.get("constraints") or {}
    buffer_value = constraints.get("minimum_monthly_buffer")
    if buffer_value is not None and buffer_value < 0:
        issues.append(f"constraints.minimum_monthly_buffer must be >= 0, got {buffer_value}")

    assumptions = profile.get("assumptions")
    if assumptions is not None:
        issues.extend(validate_assumptions(assumptions))

    return issues
