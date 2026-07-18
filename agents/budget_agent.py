from agents.base import BaseAgent
from utils import finance_calc as fc


class BudgetAdvisorAgent(BaseAgent):
    name = "Budget Advisor"
    system_prompt = (
        "You are a pragmatic budget coach using the 50/30/20 framework (needs/wants/savings). "
        "Compare the user's actual spending split to the recommended split and give 3 specific, "
        "actionable changes they could make this month. Reference real dollar amounts. Under 180 words."
    )

    def run(self, context: dict) -> dict:
        df = context["transactions"]
        income = context.get("monthly_income", 0)
        recommended = fc.recommended_budget(income)
        actual = fc.actual_budget_split(df)

        summary = (
            f"Monthly income: ${income:,.0f}\n"
            f"Recommended 50/30/20 split: {recommended}\n"
            f"Actual split (all transaction history): {actual}"
        )
        narrative, live = self._ask(summary)
        if narrative is None:
            diffs = []
            for k in recommended:
                delta = actual.get(k, 0) - recommended[k]
                if income and abs(delta) > 0.05 * income:
                    direction = "over" if delta > 0 else "under"
                    diffs.append(
                        f"- {k}: you're at ${actual.get(k, 0):,.0f} vs recommended ${recommended[k]:,.0f} "
                        f"({direction} by ${abs(delta):,.0f})."
                    )
            body = "\n".join(diffs) if diffs else "Your spending is roughly in line with the 50/30/20 guideline."
            narrative = "**Budget Advice (offline rule-based mode)**\n" + body

        return {"agent": self.name, "narrative": narrative, "recommended": recommended, "actual": actual, "live": live}
