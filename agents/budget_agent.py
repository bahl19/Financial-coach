from agents.base import BaseAgent
from utils import finance_calc as fc


class BudgetAdvisorAgent(BaseAgent):
    name = "Budget Advisor"
    system_prompt = (
        "You are a pragmatic budget coach using the 50/30/20 framework (needs/wants/savings). "
        "Compare the user's actual spending split to the recommended split and give 3 specific, "
        "actionable changes they could make this month. Reference real rupee amounts. Under 180 words."
    )

    def _build_summary(self, by_category, monthly_cashflow, monthly_income) -> tuple:
        # Budget does not allocate surplus, so it takes no roadmap_result
        # dependency. It reuses spending_result's by_category/monthly_cashflow
        # instead of recomputing them from raw transactions.
        num_months = max(len(monthly_cashflow), 1)
        recommended = fc.recommended_budget(monthly_income)
        actual = fc.actual_budget_split_from_categories(by_category, num_months)

        summary = (
            f"Monthly income: ₹{monthly_income:,.0f}\n"
            f"Recommended 50/30/20 split: {recommended}\n"
            f"Actual split (average per month): {actual}"
        )
        # Computed once and stored, not recomputed inline while formatting
        # the narrative - a derived figure ("over/under by ₹X") must be
        # traceable in supporting_tables like everything else, not exist
        # only inside a string-formatting call (Standing Context: pure
        # functions, one truth per figure).
        variance = fc.budget_variance(actual, recommended)

        structured = {
            "expected_effect": "Spending brought closer to the 50/30/20 guideline.",
            "what_to_monitor": "Whether the largest over-budget bucket trends back down next month.",
            "supporting_tables": {
                "recommended": recommended, "actual": actual, "monthly_income": monthly_income, "variance": variance,
            },
        }
        return summary, structured

    def _fallback_narrative(self, structured: dict) -> str:
        recommended = structured["supporting_tables"]["recommended"]
        actual = structured["supporting_tables"]["actual"]
        variance = structured["supporting_tables"]["variance"]
        income = structured["supporting_tables"]["monthly_income"]

        diffs = []
        for bucket in recommended:
            delta = variance.get(bucket, 0.0)
            if income and abs(delta) > 0.05 * income:
                direction = "over" if delta > 0 else "under"
                diffs.append(
                    f"- {bucket}: you're at ₹{actual.get(bucket, 0.0):,.0f} vs recommended "
                    f"₹{recommended[bucket]:,.0f} ({direction} by ₹{abs(delta):,.0f})."
                )
        body = "\n".join(diffs) if diffs else "Your spending is roughly in line with the 50/30/20 guideline."
        return "**Budget Advice (offline rule-based mode)**\n" + body
