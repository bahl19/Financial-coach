"""Consistency validator (Architecture Plan.md, Consistency Validator).

Composes the two check tiers (`utils/validation_structured.py`,
`utils/validation_prose.py`) into one public entry point. `validate_consistency()`
is pure - it inspects `specialist_results` and returns a verdict, it never
mutates anything. Remediation (replacing a failing narrative with a
deterministic fallback) is a genuinely separate function,
`apply_consistency_fallback()`, so a check can never accidentally paper over
what it just found.

This module imports the specialist agent classes to reuse each one's own
`_fallback_narrative()` - already a first-class, LLM-independent output from
Phase 3 - rather than writing a second fallback-narrative generator that
could drift from the first. That makes this a Component-4-internal, utils/
-to-agents/ import, the reverse of the usual direction; it is deliberate; see
this module's use of `_AGENT_INSTANCES` below.
"""

from __future__ import annotations

from typing import Dict, List

from agents.budget_agent import BudgetAdvisorAgent
from agents.debt_agent import DebtAnalyzerAgent
from agents.goal_agent import GoalPlannerAgent
from agents.savings_agent import SavingsStrategyAgent
from agents.spending_agent import SpendingAnalyzerAgent
from utils.contracts import ValidationResult
from utils.validation_prose import PROSE_CHECKS
from utils.validation_structured import STRUCTURED_CHECKS, expected_allocated_amount

_AGENT_INSTANCES = {
    "spending": SpendingAnalyzerAgent(),
    "debt": DebtAnalyzerAgent(),
    "savings": SavingsStrategyAgent(),
    "budget": BudgetAdvisorAgent(),
    "goal": GoalPlannerAgent(),
}

_ALL_CHECKS = STRUCTURED_CHECKS + PROSE_CHECKS


def _flatten_specialist_results(specialist_results: dict) -> List[dict]:
    """Returns [{"key": str, "index": int | None, "result": SpecialistResult}].
    `index` is only set for goal_result, which is a list (one entry per
    goal) rather than a single SpecialistResult like the other four."""
    entries = []
    for key, value in specialist_results.items():
        name = key[: -len("_result")] if key.endswith("_result") else key
        if isinstance(value, list):
            for index, item in enumerate(value):
                entries.append({"key": name, "index": index, "result": item})
        else:
            entries.append({"key": name, "index": None, "result": value})
    return entries


def _run_all_checks(roadmap, specialist_results, snapshot, findings, risks, trends) -> List[dict]:
    entries = _flatten_specialist_results(specialist_results)
    violations = []
    for check in _ALL_CHECKS:
        violations.extend(check(
            entries=entries, roadmap=roadmap, snapshot=snapshot, findings=findings, risks=risks, trends=trends,
        ))
    return violations


def validate_consistency(
    roadmap: dict, specialist_results: dict, snapshot: dict, findings: list, risks: list, trends: list,
) -> ValidationResult:
    """Pure: returns a verdict, never mutates `specialist_results` or
    `roadmap`. Call `apply_consistency_fallback()` separately to remediate
    a failing result."""
    violations = _run_all_checks(roadmap, specialist_results, snapshot, findings, risks, trends)
    return {
        "schema_version": "1.0",
        "valid": not violations,
        "violations": [v["message"] for v in violations],
        "checked_agents": list(_AGENT_INSTANCES.keys()),
        "fallback_used": False,  # remediation is a separate step; this function never applies one
    }


def _failing_entry_keys(roadmap, specialist_results, snapshot, findings, risks, trends) -> set:
    """Which (key, index) pairs had at least one violation attributed to
    them - used only by apply_consistency_fallback(), never by
    validate_consistency() itself."""
    violations = _run_all_checks(roadmap, specialist_results, snapshot, findings, risks, trends)
    return {(v["entry_key"], v["entry_index"]) for v in violations if v["entry_key"] is not None}


def _rebuilt_fallback_narrative(key: str, original_result: dict, roadmap: dict) -> str:
    """Reuses the agent's own _fallback_narrative(), fed the *corrected*
    allocated_amount sourced authoritatively from roadmap.allocation - the
    rest of the structured fields (supporting_tables etc.) are assumed
    structurally sound; only the numeric claim is untrusted."""
    agent = _AGENT_INSTANCES[key]
    corrected_structured = dict(original_result)
    corrected_structured["allocated_amount"] = expected_allocated_amount(
        {"key": key, "result": original_result}, roadmap
    )
    return agent._fallback_narrative(corrected_structured)


def apply_consistency_fallback(
    roadmap: dict, specialist_results: dict, snapshot: dict, findings: list, risks: list, trends: list,
) -> "tuple[dict, ValidationResult]":
    """Detects (via validate_consistency's own logic) and then remediates:
    returns (corrected_specialist_results, ValidationResult). Every
    specialist whose result had any violation attributed to it gets its
    narrative replaced with the deterministic fallback and its allocated_amount
    corrected; specialists with no violations are returned untouched.

    A roadmap-level violation (entry_key is None - e.g. an action's own
    amount exceeding surplus) has no specialist narrative to replace; it is
    still reported in `violations`, but fallback_used only reflects whether
    a specialist result was actually swapped."""
    failing = _failing_entry_keys(roadmap, specialist_results, snapshot, findings, risks, trends)

    corrected: Dict[str, object] = {}
    fallback_used = False
    for graph_key, value in specialist_results.items():
        short_key = graph_key[: -len("_result")] if graph_key.endswith("_result") else graph_key
        if isinstance(value, list):
            new_list = []
            for index, item in enumerate(value):
                if (short_key, index) in failing:
                    fixed = dict(item)
                    fixed["allocated_amount"] = expected_allocated_amount({"key": short_key, "result": item}, roadmap)
                    fixed["narrative"] = _rebuilt_fallback_narrative(short_key, item, roadmap)
                    new_list.append(fixed)
                    fallback_used = True
                else:
                    new_list.append(item)
            corrected[graph_key] = new_list
        else:
            if (short_key, None) in failing:
                fixed = dict(value)
                fixed["allocated_amount"] = expected_allocated_amount({"key": short_key, "result": value}, roadmap)
                fixed["narrative"] = _rebuilt_fallback_narrative(short_key, value, roadmap)
                corrected[graph_key] = fixed
                fallback_used = True
            else:
                corrected[graph_key] = value

    result = validate_consistency(roadmap, specialist_results, snapshot, findings, risks, trends)
    result["fallback_used"] = fallback_used
    return corrected, result
