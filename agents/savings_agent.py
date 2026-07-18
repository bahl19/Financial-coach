from agents.base import BaseAgent
from utils import finance_calc as fc


class SavingsStrategyAgent(BaseAgent):
    name = "Savings Strategist"
    system_prompt = (
        "You are a savings coach. Given the user's existing savings, emergency fund "
        "target, and the monthly contribution the plan has already allocated, explain "
        "how that contribution builds toward the target (e.g., an emergency fund, "
        "high-yield savings, or retirement). Use the actual numbers. Under 180 words."
    )

    def _build_summary(
        self, monthly_cashflow, current_savings, savings_contribution,
        action_id=None, finding_refs=None, trend_refs=None,
    ) -> tuple:
        # avg_expenses is read from spending_result's already-computed monthly
        # cashflow, not recomputed from raw transactions (Implementation Plan,
        # Phase 3). savings_contribution is copied from roadmap.allocation,
        # never computed as a percentage of surplus here.
        avg_expenses = float(monthly_cashflow["expenses"].mean()) if not monthly_cashflow.empty else 0.0
        target = fc.emergency_fund_target(avg_expenses)
        projection = fc.savings_projection(current_savings, savings_contribution, months=24)

        summary = (
            f"Current savings: ${current_savings:,.0f}. "
            f"Recommended emergency fund target (3-6 months expenses): ${target[0]:,.0f}-${target[1]:,.0f}. "
            f"Monthly contribution allocated by the roadmap: ${savings_contribution:,.0f}. "
            f"Projected balance in 24 months at this contribution: ${projection[-1]['balance']:,.0f}"
        )
        structured = {
            "allocated_amount": savings_contribution,
            "why_allocated": action_id,
            "expected_effect": f"Projected balance in 24 months: ${projection[-1]['balance']:,.0f}.",
            "tradeoffs": "Money contributed here is not available for debt payoff or discretionary spending.",
            "what_to_monitor": "Whether the emergency fund target is reached before redirecting savings elsewhere.",
            "finding_refs": finding_refs or [],
            "trend_refs": trend_refs or [],
            "recommends_action_ids": [action_id] if action_id else [],
            "supporting_tables": {"emergency_fund_target": target, "projection": projection},
        }
        return summary, structured

    def _fallback_narrative(self, structured: dict) -> str:
        target = structured["supporting_tables"]["emergency_fund_target"]
        projection = structured["supporting_tables"]["projection"]
        contribution = structured["allocated_amount"] or 0.0
        return (
            "**Savings Strategy (offline rule-based mode)**\n"
            f"- Target emergency fund: ${target[0]:,.0f}-${target[1]:,.0f} (3-6 months of expenses).\n"
            f"- Monthly contribution allocated by the roadmap: ${contribution:,.0f}.\n"
            f"- At this rate, projected savings in 24 months: ${projection[-1]['balance']:,.0f}."
        )
