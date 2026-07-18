from agents.base import BaseAgent
from utils import finance_calc as fc


class SavingsStrategyAgent(BaseAgent):
    name = "Savings Strategist"
    system_prompt = (
        "You are a savings coach. Given the user's income, expenses, existing "
        "savings, and emergency fund target, propose a concrete monthly savings "
        "plan (e.g., how to split contributions across an emergency fund, "
        "high-yield savings, and retirement). Use the actual numbers. Under 180 words."
    )

    def run(self, context: dict) -> dict:
        income = context.get("monthly_income", 0)
        monthly = fc.monthly_cashflow(context["transactions"])
        avg_expenses = monthly["expenses"].mean() if not monthly.empty else 0
        current_savings = context.get("current_savings", 0)

        target = fc.emergency_fund_target(avg_expenses)
        surplus = max(income - avg_expenses, 0)
        contribution = surplus * 0.5
        projection = fc.savings_projection(current_savings, contribution, months=24)

        summary = (
            f"Monthly income: ${income:,.0f}, avg monthly expenses: ${avg_expenses:,.0f}, "
            f"monthly surplus: ${surplus:,.0f}, current savings: ${current_savings:,.0f}, "
            f"recommended emergency fund target (3-6 months expenses): ${target[0]:,.0f}-${target[1]:,.0f}. "
            f"Projected balance in 24 months if 50% of surplus (${contribution:,.0f}/mo) is saved at 4% APY: "
            f"${projection[-1]['balance']:,.0f}"
        )
        narrative, live = self._ask(summary)
        if narrative is None:
            narrative = (
                "**Savings Strategy (offline rule-based mode)**\n"
                f"- Target emergency fund: ${target[0]:,.0f}-${target[1]:,.0f} (3-6 months of expenses).\n"
                f"- You currently have ${current_savings:,.0f} saved.\n"
                f"- Monthly surplus available: ${surplus:,.0f}. Suggest auto-transferring 50% "
                f"(${contribution:,.0f}) to a high-yield savings account and directing the rest toward "
                "debt payoff or investing.\n"
                f"- At this rate, projected savings in 24 months: ${projection[-1]['balance']:,.0f}."
            )

        return {
            "agent": self.name,
            "narrative": narrative,
            "emergency_fund_target": target,
            "surplus": surplus,
            "projection": projection,
            "live": live,
        }
