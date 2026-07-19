from agents.base import BaseAgent
from utils import finance_calc as fc
from utils.currency import format_money


class DebtAnalyzerAgent(BaseAgent):
    name = "Debt Analyzer"
    system_prompt = (
        "You are a debt-payoff strategist. Given two simulated payoff plans "
        "(avalanche vs snowball) with months-to-debt-free and total interest paid, "
        "recommend which strategy fits this user and explain the tradeoff in plain "
        "language. Reference the actual numbers. Under 180 words."
    )

    def _build_summary(
        self, debts, extra_debt_payment, action_id=None, finding_refs=None, trend_refs=None, currency=None,
    ) -> tuple:
        if not debts:
            structured = {
                # roadmap.allocation["debt_extra_payment"] is always a concrete
                # float (0.0 with no debts), never None - allocated_amount must
                # match it exactly here too. None is reserved for agents that
                # never allocate money at all (spending, budget); debt does
                # allocate, just 0 in this case, and consistency checks (Phase 4)
                # treat "None" and "0.0" as different claims.
                "allocated_amount": extra_debt_payment,
                "why_allocated": action_id,
                "supporting_tables": {"avalanche": None, "snowball": None, "currency": currency},
                "finding_refs": finding_refs or [],
                "trend_refs": trend_refs or [],
            }
            return None, structured  # nothing to ask an LLM about - skip straight to fallback

        avalanche = fc.simulate_payoff(debts, extra_debt_payment, strategy="avalanche")
        snowball = fc.simulate_payoff(debts, extra_debt_payment, strategy="snowball")
        interest_saved = max(snowball["total_interest"] - avalanche["total_interest"], 0.0)

        summary = (
            f"Avalanche plan (highest APR first): payoff in {avalanche['months_to_payoff']} months, "
            f"total interest {format_money(avalanche['total_interest'], currency)}, order: {avalanche['payoff_order']}\n"
            f"Snowball plan (smallest balance first): payoff in {snowball['months_to_payoff']} months, "
            f"total interest {format_money(snowball['total_interest'], currency)}, order: {snowball['payoff_order']}\n"
            f"Extra monthly payment allocated by the roadmap: {format_money(extra_debt_payment, currency)}"
        )
        structured = {
            # Copied directly from the roadmap's allocation - never computed here.
            "allocated_amount": extra_debt_payment,
            "why_allocated": action_id,
            "expected_effect": f"Avalanche saves {format_money(interest_saved, currency)} in interest versus snowball.",
            "tradeoffs": "Snowball may offer faster small-balance wins for motivation, at a higher total interest cost.",
            "what_to_monitor": "Confirm the extra payment is applied to principal, not just the next due date.",
            "finding_refs": finding_refs or [],
            "trend_refs": trend_refs or [],
            "recommends_action_ids": [action_id] if action_id else [],
            "supporting_tables": {"avalanche": avalanche, "snowball": snowball, "currency": currency},
        }
        return summary, structured

    def _fallback_narrative(self, structured: dict) -> str:
        avalanche = structured["supporting_tables"]["avalanche"]
        snowball = structured["supporting_tables"]["snowball"]
        if avalanche is None:
            return "No debts on file -- you're debt-free! \U0001f389"

        currency = structured["supporting_tables"].get("currency")
        allocated = structured["allocated_amount"] or 0.0
        savings = snowball["total_interest"] - avalanche["total_interest"]
        return (
            "**Debt Payoff Analysis (offline rule-based mode)**\n"
            f"- Extra monthly payment allocated by the roadmap: {format_money(allocated, currency)}.\n"
            f"- Avalanche (highest APR first): debt-free in {avalanche['months_to_payoff']} months, "
            f"{format_money(avalanche['total_interest'], currency)} in interest.\n"
            f"- Snowball (smallest balance first): debt-free in {snowball['months_to_payoff']} months, "
            f"{format_money(snowball['total_interest'], currency)} in interest.\n"
            + (
                f"- Avalanche saves you {format_money(savings, currency)} in interest -- recommended if you can stay "
                "motivated without quick wins.\n"
                if savings > 0
                else "- Both strategies cost about the same in interest here.\n"
            )
            + "- Snowball may suit you better if you want fast psychological wins from closing small accounts first."
        )
