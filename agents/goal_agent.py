from agents.base import BaseAgent
from utils import finance_calc as fc


class GoalPlannerAgent(BaseAgent):
    name = "Goal Planner"
    system_prompt = (
        "You are a goals-based financial planner. Given a savings goal, target timeline, "
        "and the user's available monthly surplus, tell them whether it's achievable, "
        "the required monthly contribution, and one concrete lever to close any gap. "
        "Under 150 words."
    )

    def run(self, context: dict) -> dict:
        goals = context.get("goals") or []
        surplus = context.get("monthly_surplus", 0)
        results = []

        for g in goals:
            res = fc.goal_feasibility(g["amount"], g["months"], surplus, g.get("current", 0))
            summary = (
                f"Goal: {g['name']}, target ${g['amount']:,.0f} in {g['months']} months, "
                f"already saved ${g.get('current', 0):,.0f}, available monthly surplus ${surplus:,.0f}. "
                f"Required monthly contribution: ${res['required_monthly']:,.0f}. Feasible: {res['feasible']}."
            )
            narrative, live = self._ask(summary, max_tokens=300)
            if narrative is None:
                if res["feasible"]:
                    narrative = (
                        f"✅ On track: saving ${res['required_monthly']:,.0f}/month hits "
                        f"**{g['name']}** in {g['months']} months."
                    )
                else:
                    narrative = (
                        f"⚠️ Needs ${res['required_monthly']:,.0f}/month but only ${surplus:,.0f} "
                        f"available -- shortfall of ${res['shortfall']:,.0f}/month. Consider extending the "
                        "timeline or cutting spending elsewhere."
                    )
            results.append({**g, **res, "narrative": narrative, "live": live})

        return {"agent": self.name, "goals": results}
