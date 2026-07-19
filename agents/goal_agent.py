from agents.base import BaseAgent
from utils import finance_calc as fc


class GoalPlannerAgent(BaseAgent):
    """The one specialist that returns a *list* of SpecialistResult, one per
    goal, rather than a single result - goals are inherently a collection,
    and Phase 4's consistency validator needs each goal's contribution
    traceable individually, not folded into one combined narrative."""

    name = "Goal Planner"
    system_prompt = (
        "You are a goals-based financial planner. Given a savings goal, target timeline, "
        "and the monthly contribution the plan has already allocated to it, tell the user "
        "whether it's on track, the required monthly contribution, and one concrete lever "
        "to close any gap. Under 150 words."
    )

    def run(self, goals, goal_contributions, action_ids_by_goal=None, finding_refs_by_goal=None) -> list:
        action_ids_by_goal = action_ids_by_goal or {}
        finding_refs_by_goal = finding_refs_by_goal or {}
        results = []
        for goal in goals or []:
            name = goal["name"]
            # The allocated contribution comes from roadmap.allocation.goal_contributions,
            # never recomputed from the raw monthly_surplus (that was the bug this
            # phase exists to fix) - a goal missing from the dict simply got ₹0.
            contribution = goal_contributions.get(name, 0.0)
            results.append(super().run(
                goal=goal,
                contribution=contribution,
                action_id=action_ids_by_goal.get(name),
                finding_refs=finding_refs_by_goal.get(name),
            ))
        return results

    def _build_summary(self, goal, contribution, action_id=None, finding_refs=None) -> tuple:
        result = fc.goal_feasibility(goal["amount"], goal["months"], contribution, goal.get("current", 0.0))
        summary = (
            f"Goal: {goal['name']}, target ₹{goal['amount']:,.0f} in {goal['months']} months, "
            f"already saved ₹{goal.get('current', 0.0):,.0f}, allocated monthly contribution: "
            f"₹{contribution:,.0f}. Required monthly contribution: ₹{result['required_monthly']:,.0f}. "
            f"Feasible at this contribution: {result['feasible']}."
        )
        structured = {
            "allocated_amount": contribution,
            "why_allocated": action_id,
            "expected_effect": (
                f"On track for {goal['name']}." if result["feasible"]
                else f"Shortfall of ₹{result['shortfall']:,.0f}/month for {goal['name']}."
            ),
            "what_to_monitor": "Whether the required monthly contribution changes if the target or timeline changes.",
            "finding_refs": finding_refs or [],
            "recommends_action_ids": [action_id] if action_id else [],
            "supporting_tables": {"goal": goal, "feasibility": result},
        }
        return summary, structured

    def _fallback_narrative(self, structured: dict) -> str:
        goal = structured["supporting_tables"]["goal"]
        result = structured["supporting_tables"]["feasibility"]
        contribution = structured["allocated_amount"] or 0.0
        if result["feasible"]:
            return (
                f"✅ On track: the roadmap allocates ₹{contribution:,.0f}/month, meeting the "
                f"₹{result['required_monthly']:,.0f}/month needed for **{goal['name']}** in {goal['months']} months."
            )
        return (
            f"⚠️ **{goal['name']}** needs ₹{result['required_monthly']:,.0f}/month but the roadmap "
            f"allocates only ₹{contribution:,.0f} -- shortfall of ₹{result['shortfall']:,.0f}/month. "
            "Consider extending the timeline or cutting spending elsewhere."
        )
