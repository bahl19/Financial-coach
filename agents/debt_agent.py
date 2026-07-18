from agents.base import BaseAgent
from utils import finance_calc as fc


class DebtAnalyzerAgent(BaseAgent):
    name = "Debt Analyzer"
    system_prompt = (
        "You are a debt-payoff strategist. Given two simulated payoff plans "
        "(avalanche vs snowball) with months-to-debt-free and total interest paid, "
        "recommend which strategy fits this user and explain the tradeoff in plain "
        "language. Reference the actual numbers. Under 180 words."
    )

    def run(self, context: dict) -> dict:
        debts = context.get("debts") or []
        extra = context.get("extra_debt_payment", 0)

        if not debts:
            return {
                "agent": self.name,
                "narrative": "No debts on file -- you're debt-free! \U0001f389",
                "avalanche": None,
                "snowball": None,
                "live": False,
            }

        avalanche = fc.simulate_payoff(debts, extra, strategy="avalanche")
        snowball = fc.simulate_payoff(debts, extra, strategy="snowball")

        summary = (
            f"Avalanche plan (highest APR first): payoff in {avalanche['months_to_payoff']} months, "
            f"total interest ${avalanche['total_interest']:,.0f}, order: {avalanche['payoff_order']}\n"
            f"Snowball plan (smallest balance first): payoff in {snowball['months_to_payoff']} months, "
            f"total interest ${snowball['total_interest']:,.0f}, order: {snowball['payoff_order']}\n"
            f"Extra monthly payment available beyond minimums: ${extra:,.0f}"
        )
        narrative, live = self._ask(summary)
        if narrative is None:
            savings = snowball["total_interest"] - avalanche["total_interest"]
            narrative = (
                "**Debt Payoff Analysis (offline rule-based mode)**\n"
                f"- Avalanche (highest APR first): debt-free in {avalanche['months_to_payoff']} months, "
                f"${avalanche['total_interest']:,.0f} in interest.\n"
                f"- Snowball (smallest balance first): debt-free in {snowball['months_to_payoff']} months, "
                f"${snowball['total_interest']:,.0f} in interest.\n"
                + (
                    f"- Avalanche saves you ${savings:,.0f} in interest -- recommended if you can stay "
                    "motivated without quick wins.\n"
                    if savings > 0
                    else "- Both strategies cost about the same in interest here.\n"
                )
                + "- Snowball may suit you better if you want fast psychological wins from closing small accounts first."
            )

        return {"agent": self.name, "narrative": narrative, "avalanche": avalanche, "snowball": snowball, "live": live}
