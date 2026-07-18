"""Structured consistency checks (Architecture Plan.md, Consistency Validator).

These are the *authoritative* tier: fully deterministic checks over typed
`SpecialistResult`/`Roadmap` fields, not over generated prose. If one of
these fails, something is genuinely wrong - there is no "maybe" the way
there is with the prose checks in `utils/validation_prose.py`.

Kept in its own module, not merely its own functions, so the distinction
between "guarantee" and "heuristic" is visible in the file layout, not just
in a docstring someone can skim past.

Every check function has the same shape: `(entries, roadmap, snapshot,
findings, risks, trends) -> list[violation]`, where a violation is
`{"entry_key": str | None, "entry_index": int | None, "message": str}`.
`entry_key`/`entry_index` are `None` for a roadmap-level violation that
isn't attributable to any one specialist (e.g. an action's own amount
exceeding surplus - there is no specialist narrative to blame or replace).
"""

from __future__ import annotations

from typing import List, Optional

_AMOUNT_TOLERANCE = 1e-9


def _violation(entry: dict, message: str) -> dict:
    return {"entry_key": entry["key"], "entry_index": entry["index"], "message": f"{entry['key']}: {message}"}


def _roadmap_violation(message: str) -> dict:
    return {"entry_key": None, "entry_index": None, "message": message}


def expected_allocated_amount(entry: dict, roadmap: dict) -> Optional[float]:
    """The one authoritative source for "what should this specialist's
    allocated_amount be" - both check 3 and the fallback-remediation step
    in utils/validation.py call this, so there is exactly one place this
    mapping is defined."""
    allocation = roadmap["allocation"]
    key = entry["key"]
    if key == "debt":
        return allocation["debt_extra_payment"]
    if key == "savings":
        return allocation["savings_contribution"]
    if key == "goal":
        goal_name = entry["result"]["supporting_tables"]["goal"]["name"]
        return allocation["goal_contributions"].get(goal_name, 0.0)
    return None  # spending/budget do not allocate money


# Check 1: every recommends_action_ids entry exists in roadmap.actions.
def check_recommends_action_ids_exist(entries, roadmap, **_) -> List[dict]:
    valid_ids = {a["action_id"] for a in roadmap["actions"]}
    violations = []
    for entry in entries:
        for action_id in entry["result"].get("recommends_action_ids") or []:
            if action_id not in valid_ids:
                violations.append(_violation(entry, f"recommends_action_ids references unknown action_id {action_id!r}"))
    return violations


# Check 2: the order of recommends_action_ids is consistent with those
# actions' priority values.
def check_recommends_action_ids_order(entries, roadmap, **_) -> List[dict]:
    priority_by_id = {a["action_id"]: a["priority"] for a in roadmap["actions"]}
    violations = []
    for entry in entries:
        ids = entry["result"].get("recommends_action_ids") or []
        priorities = [priority_by_id[i] for i in ids if i in priority_by_id]
        if priorities != sorted(priorities):
            violations.append(_violation(entry, "recommends_action_ids is not listed in roadmap priority order"))
    return violations


# Check 3: each allocated_amount exactly equals the corresponding
# roadmap.allocation entry.
def check_allocated_amount_matches_roadmap(entries, roadmap, **_) -> List[dict]:
    violations = []
    for entry in entries:
        expected = expected_allocated_amount(entry, roadmap)
        actual = entry["result"].get("allocated_amount")
        if expected is None:
            if actual is not None:
                violations.append(_violation(entry, f"must not allocate money but reports allocated_amount={actual}"))
            continue
        if actual is None or abs(actual - expected) > _AMOUNT_TOLERANCE:
            violations.append(_violation(entry, f"allocated_amount {actual} does not match roadmap.allocation's {expected}"))
    return violations


# Check 4: if allocation[x] == 0, no specialist reports allocated_amount > 0
# for x and no recommends_action_ids entry maps to an action allocating x.
# Deliberately independent of check 3 (which already implies the amount
# half when it passes) - this also guards recommends_action_ids directly,
# so a corruption that only touches that field is still caught.
def check_zero_allocation_not_recommended(entries, roadmap, **_) -> List[dict]:
    action_by_id = {a["action_id"]: a for a in roadmap["actions"]}
    violations = []
    for entry in entries:
        expected = expected_allocated_amount(entry, roadmap)
        actual = entry["result"].get("allocated_amount")
        if expected == 0 and actual and actual > 0:
            violations.append(_violation(entry, f"reports a positive allocated_amount ({actual}) though the roadmap allocated $0"))
        for action_id in entry["result"].get("recommends_action_ids") or []:
            action = action_by_id.get(action_id)
            if action is not None and action.get("monthly_amount", 0) <= 0:
                violations.append(_violation(entry, f"recommends {action_id}, which the roadmap allocated $0"))
    return violations


# Check 5: every finding_refs/trend_refs (on specialist results) and
# finding_refs/risk_refs (on roadmap actions) resolves against this
# invocation's actual objects.
def check_refs_resolve(entries, roadmap, findings, risks, trends, **_) -> List[dict]:
    finding_ids = {f["finding_id"] for f in findings}
    trend_ids = {t["trend_id"] for t in trends}
    risk_ids = {r["risk_id"] for r in risks}

    violations = []
    for entry in entries:
        for ref in entry["result"].get("finding_refs") or []:
            if ref not in finding_ids:
                violations.append(_violation(entry, f"finding_refs references unknown finding_id {ref!r}"))
        for ref in entry["result"].get("trend_refs") or []:
            if ref not in trend_ids:
                violations.append(_violation(entry, f"trend_refs references unknown trend_id {ref!r}"))

    for action in roadmap["actions"]:
        for ref in action.get("finding_refs") or []:
            if ref not in finding_ids:
                violations.append(_roadmap_violation(f"action {action['action_id']} finding_refs references unknown finding_id {ref!r}"))
        for ref in action.get("risk_refs") or []:
            if ref not in risk_ids:
                violations.append(_roadmap_violation(f"action {action['action_id']} risk_refs references unknown risk_id {ref!r}"))
    return violations


# Check 6: no action's monthly_amount exceeds allocatable_surplus. A
# roadmap-level violation - there is no specialist narrative to blame if
# build_roadmap() itself produced an invalid action.
def check_action_amount_within_surplus(entries, roadmap, snapshot, **_) -> List[dict]:
    allocatable_surplus = snapshot["metrics"].get("allocatable_surplus")
    if allocatable_surplus is None:
        return []
    violations = []
    for action in roadmap["actions"]:
        if action.get("monthly_amount", 0) > allocatable_surplus + _AMOUNT_TOLERANCE:
            violations.append(_roadmap_violation(
                f"action {action['action_id']} monthly_amount {action['monthly_amount']} "
                f"exceeds allocatable_surplus {allocatable_surplus}"
            ))
    return violations


STRUCTURED_CHECKS = (
    check_recommends_action_ids_exist,
    check_recommends_action_ids_order,
    check_allocated_amount_matches_roadmap,
    check_zero_allocation_not_recommended,
    check_refs_resolve,
    check_action_amount_within_surplus,
)
