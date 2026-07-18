"""Prose consistency checks (Architecture Plan.md, Consistency Validator).

These are the *heuristic* tier: best-effort regex checks over free-text
`narrative` strings. They will not catch a figure spelled "twelve hundred"
or paraphrased around - they are defense in depth, not a guarantee, and
must never be treated as one. Kept in its own module (not just its own
functions) so that distinction from `utils/validation_structured.py` is
visible in the file layout, not just asserted in a comment.

Same check-function shape as the structured tier: `(entries, roadmap,
snapshot, findings, risks, trends) -> list[violation]`.
"""

from __future__ import annotations

import re
from typing import List

import pandas as pd

_DOLLAR_PATTERN = re.compile(r"\$([\d,]+(?:\.\d+)?)")
_PERCENT_PATTERN = re.compile(r"(-?\d+(?:\.\d+)?)\s*%")
_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
_INCOME_EXPENSE_SURPLUS_KEYWORDS = ("income", "expense", "surplus")

# Narratives format money with `:,.0f` (whole dollars), so allow a small
# absolute tolerance to absorb that rounding rather than demanding an exact
# floating-point match against an unrounded allocation value.
_DOLLAR_TOLERANCE = 1.0
_PERCENT_TOLERANCE = 1.0


def _violation(entry: dict, message: str) -> dict:
    return {"entry_key": entry["key"], "entry_index": entry["index"], "message": f"{entry['key']}: {message}"}


def _extract_dollar_amounts(text: str) -> List[float]:
    return [float(m.replace(",", "")) for m in _DOLLAR_PATTERN.findall(text)]


def _extract_percentages(text: str) -> List[float]:
    return [float(m) for m in _PERCENT_PATTERN.findall(text)]


def _numeric_leaves(obj) -> List[float]:
    """Recursively extracts every numeric value from a nested structure of
    dicts, lists/tuples, and pandas DataFrames/Series. A specialist's own
    `supporting_tables` is its grounding data - whatever number it narrates
    should trace back to something in there, not just to the
    roadmap/snapshot-wide figures. Skips bool (a bool is technically an int
    subclass in Python, but "True"/"False" are never a dollar or percent
    figure)."""
    values: List[float] = []
    if isinstance(obj, bool):
        return values
    if isinstance(obj, (int, float)):
        values.append(float(obj))
    elif isinstance(obj, dict):
        for value in obj.values():
            values.extend(_numeric_leaves(value))
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            values.extend(_numeric_leaves(value))
    elif isinstance(obj, pd.DataFrame):
        for column in obj.select_dtypes(include="number").columns:
            values.extend(float(x) for x in obj[column].tolist())
    elif isinstance(obj, pd.Series):
        values.extend(float(x) for x in obj.tolist() if isinstance(x, (int, float)) and not isinstance(x, bool))
    return values


def _global_dollar_allowlist(roadmap: dict, snapshot: dict) -> List[float]:
    allocation = roadmap["allocation"]
    values = [allocation["buffer_reserved"], allocation["debt_extra_payment"], allocation["savings_contribution"]]
    values.extend(allocation["goal_contributions"].values())
    values.extend(action["monthly_amount"] for action in roadmap["actions"])
    metrics = snapshot["metrics"]
    for key in ("average_monthly_expenses", "gross_surplus", "allocatable_surplus", "total_debt", "required_commitments"):
        value = metrics.get(key)
        if value is not None:
            values.append(value)
    return values


def _global_percent_allowlist(snapshot: dict, trends: list) -> List[float]:
    values = []
    metrics = snapshot["metrics"]
    for key in ("debt_to_income_percent", "savings_rate_percent"):
        value = metrics.get(key)
        if value is not None:
            values.append(value)
    values.extend(t["percent_change"] for t in trends if t.get("percent_change") is not None)
    return values


def _entry_allowlist(entry: dict, global_allowlist: List[float]) -> List[float]:
    """A specialist's narrative may legitimately cite anything in its own
    supporting_tables (category totals, budget splits, avalanche/snowball
    interest, goal amounts, ...) in addition to the roadmap/snapshot-wide
    figures - narrowing this to the global list alone is exactly the
    "heuristic tightened until it false-positives on legitimate text"
    failure mode the Phase 4 execution prompt warns against."""
    return global_allowlist + _numeric_leaves(entry["result"].get("supporting_tables"))


# Check 7: every $ amount in a narrative appears in an allowlist derived
# from roadmap.allocation + snapshot.metrics + that specialist's own
# supporting_tables (its grounding data).
def check_narrative_dollar_amounts_are_allowlisted(entries, roadmap, snapshot, **_) -> List[dict]:
    global_allowlist = _global_dollar_allowlist(roadmap, snapshot)
    violations = []
    for entry in entries:
        allowlist = _entry_allowlist(entry, global_allowlist)
        narrative = entry["result"].get("narrative") or ""
        for amount in _extract_dollar_amounts(narrative):
            # Compare against the magnitude: dollar amounts in narratives
            # are always shown unsigned (e.g. "over by $645"), while some
            # grounding data (a variance/delta) is naturally signed.
            if not any(abs(amount - abs(allowed)) <= _DOLLAR_TOLERANCE for allowed in allowlist):
                violations.append(_violation(entry, f"narrative quotes ${amount:,.0f}, matching no known allocation, metric, or supporting figure"))
    return violations


# Check 8: every % in a narrative resolves to a Trend.percent_change, a
# snapshot metric, or a percentage already present in that specialist's own
# supporting_tables (e.g. spending's own category_trends pct_change).
def check_narrative_percentages_resolve(entries, snapshot, trends, **_) -> List[dict]:
    global_allowlist = _global_percent_allowlist(snapshot, trends)
    violations = []
    for entry in entries:
        allowlist = _entry_allowlist(entry, global_allowlist)
        narrative = entry["result"].get("narrative") or ""
        for pct in _extract_percentages(narrative):
            if not any(abs(pct - allowed) <= _PERCENT_TOLERANCE or abs(pct - abs(allowed)) <= _PERCENT_TOLERANCE for allowed in allowlist):
                violations.append(_violation(entry, f"narrative quotes {pct}%, matching no known trend, metric, or supporting figure"))
    return violations


# Check 9: no narrative quotes an income/expense/surplus value absent from
# snapshot.metrics. Narrower than check 7: sentence-scoped and keyword-
# gated, so it only fires on sentences actually discussing income/expenses/
# surplus, against a tighter allowlist than check 7's full roadmap-wide one.
def check_narrative_income_expense_surplus_values(entries, snapshot, **_) -> List[dict]:
    metrics = snapshot["metrics"]
    global_allowlist = [
        metrics[key] for key in ("gross_surplus", "average_monthly_expenses", "allocatable_surplus")
        if metrics.get(key) is not None
    ]
    violations = []
    for entry in entries:
        # As with checks 7/8: a sentence mentioning "expenses" (e.g. an
        # emergency-fund target derived from average_monthly_expenses, or a
        # category total) may legitimately cite a figure grounded in that
        # specialist's own supporting_tables, not the three snapshot keys
        # alone - narrowing this further is exactly the over-tight-heuristic
        # failure mode the Phase 4 execution prompt warns against.
        allowlist = _entry_allowlist(entry, global_allowlist)
        narrative = entry["result"].get("narrative") or ""
        for sentence in _SENTENCE_SPLIT_PATTERN.split(narrative):
            lowered = sentence.lower()
            if not any(keyword in lowered for keyword in _INCOME_EXPENSE_SURPLUS_KEYWORDS):
                continue
            for amount in _extract_dollar_amounts(sentence):
                if not any(abs(amount - abs(allowed)) <= _DOLLAR_TOLERANCE for allowed in allowlist):
                    violations.append(_violation(
                        entry, f"sentence mentioning income/expense/surplus quotes ${amount:,.0f}, absent from snapshot.metrics or supporting figures"
                    ))
    return violations


PROSE_CHECKS = (
    check_narrative_dollar_amounts_are_allowlisted,
    check_narrative_percentages_resolve,
    check_narrative_income_expense_surplus_values,
)
