"""Assumptions and scenarios (Architecture Plan.md, Component 5).

Owns adjusted inputs only, not financial math - it builds a modified
`FinancialProfile` and leaves calling `utils.finance_calc` to obtain results
to the caller. Depends on Component 1 (contracts) only; it reuses
`contracts.validate_assumptions()` for validation rather than duplicating
range/sum checks here (Component 1 already owns that logic - one truth).
"""

from __future__ import annotations

import copy
from typing import List

from utils.contracts import FinancialProfile, FinancialSnapshot, validate_assumptions


def apply_assumptions(profile: FinancialProfile, updates: dict) -> FinancialProfile:
    """Returns a new FinancialProfile with `updates` merged into its
    assumptions. Never mutates `profile` - a deep copy is returned so a
    preview can be discarded without side effects on the base profile the
    rest of the app is using."""
    adjusted = copy.deepcopy(profile)
    adjusted["assumptions"] = {**(adjusted.get("assumptions") or {}), **updates}
    return adjusted


def validate_assumption_updates(profile: FinancialProfile, updates: dict) -> List[str]:
    """Validates the *resulting* merged assumptions, not just the changed
    keys in isolation - a change to one ratio can break the needs/wants/
    savings sum-to-1.0 invariant even if the changed value itself is in
    range. Does not mutate `profile`."""
    adjusted = apply_assumptions(profile, updates)
    return validate_assumptions(adjusted["assumptions"])


def apply_expense_reduction(profile: FinancialProfile, categories_to_reduce: set, reduction_fraction: float) -> FinancialProfile:
    """Returns a new FinancialProfile with every expense transaction in
    `categories_to_reduce` scaled down by `reduction_fraction` (e.g. 0.1 for
    a 10% cut) - never mutates `profile`. Which categories count as
    "discretionary" is the caller's decision to make and pass in - this
    module depends on Component 1 (contracts) only, per its own docstring,
    so it does not import utils.finance_calc.NEEDS_CATS/SAVINGS_CATS itself."""
    adjusted = copy.deepcopy(profile)
    for transaction in adjusted.get("transactions") or []:
        if transaction.get("category") in categories_to_reduce and transaction.get("amount", 0) < 0:
            transaction["amount"] = transaction["amount"] * (1 - reduction_fraction)
    return adjusted


_COMPARISON_METRIC_KEYS = (
    "gross_surplus", "allocatable_surplus", "savings_rate_percent",
    "debt_to_income_percent", "emergency_fund_months", "health_score",
)


def compare_scenarios(base: FinancialSnapshot, adjusted: FinancialSnapshot) -> dict:
    """Per-metric delta between two snapshots, so the UI can show what an
    assumption change would do without altering the base snapshot itself."""
    base_metrics = {**base["metrics"], "health_score": base["health_score"]}
    adjusted_metrics = {**adjusted["metrics"], "health_score": adjusted["health_score"]}

    comparison = {}
    for key in _COMPARISON_METRIC_KEYS:
        base_value = base_metrics.get(key)
        adjusted_value = adjusted_metrics.get(key)
        delta = adjusted_value - base_value if base_value is not None and adjusted_value is not None else None
        comparison[key] = {"base": base_value, "adjusted": adjusted_value, "delta": delta}
    return comparison
