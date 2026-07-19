from agents.base import BaseAgent
from utils import finance_calc as fc


class SavingsStrategyAgent(BaseAgent):
    name = "Savings Strategist"
    system_prompt = (
        "You are a savings and investing coach. Given the user's existing savings, emergency fund "
        "target, and the monthly contribution the plan has already allocated - whether to a savings "
        "account or, when the numbers favor it, to their existing investments - explain how that "
        "contribution builds toward the target. Use the actual numbers. Under 180 words."
    )

    def _build_summary(
        self, monthly_cashflow, current_savings, savings_contribution, savings_apy=0.0,
        investment_contribution=0.0, current_investments=0.0, investment_cagr=None,
        action_id=None, finding_refs=None, trend_refs=None,
    ) -> tuple:
        # avg_expenses is read from spending_result's already-computed monthly
        # cashflow, not recomputed from raw transactions (Implementation Plan,
        # Phase 3). savings_contribution/investment_contribution are copied
        # from roadmap.allocation, never computed as a share of surplus here -
        # build_roadmap() is the only place that decision is made, and the
        # two are mutually exclusive by construction (utils/roadmap.py Step 6).
        avg_expenses = float(monthly_cashflow["expenses"].mean()) if not monthly_cashflow.empty else 0.0
        target = fc.emergency_fund_target(avg_expenses)
        # savings_apy defaults to 0.0 (never None) precisely so this call
        # always uses the user's confirmed rate, not savings_projection()'s
        # own 4% default - that default silently overriding a confirmed
        # rate was a real bug, fixed alongside this feature.
        savings_projected = fc.savings_projection(current_savings, savings_contribution, months=24, apr=savings_apy)

        investment_projected = None
        if investment_contribution > 0:
            investment_projected = fc.savings_projection(
                current_investments, investment_contribution, months=24, apr=investment_cagr or 0.0,
            )

        summary = (
            f"Current savings: ₹{current_savings:,.0f}. "
            f"Recommended emergency fund target (3-6 months expenses): ₹{target[0]:,.0f}-₹{target[1]:,.0f}. "
            f"Monthly savings contribution allocated by the roadmap: ₹{savings_contribution:,.0f} "
            f"(at {savings_apy * 100:.1f}% APY). "
            f"Projected savings balance in 24 months: ₹{savings_projected[-1]['balance']:,.0f}."
        )
        if investment_projected is not None:
            summary += (
                f" Monthly investment contribution: ₹{investment_contribution:,.0f} "
                f"(at {(investment_cagr or 0.0) * 100:.1f}% CAGR, versus the {savings_apy * 100:.1f}% savings APY). "
                f"Projected investment balance in 24 months: ₹{investment_projected[-1]['balance']:,.0f}."
            )

        structured = {
            "allocated_amount": savings_contribution + investment_contribution,
            "why_allocated": action_id,
            "expected_effect": (
                f"Projected savings balance in 24 months: ₹{savings_projected[-1]['balance']:,.0f}."
                + (f" Projected investment balance: ₹{investment_projected[-1]['balance']:,.0f}." if investment_projected else "")
            ),
            "tradeoffs": "Money contributed here is not available for debt payoff or discretionary spending.",
            "what_to_monitor": "Whether the emergency fund target is reached before redirecting savings elsewhere.",
            "finding_refs": finding_refs or [],
            "trend_refs": trend_refs or [],
            "recommends_action_ids": [action_id] if action_id else [],
            "supporting_tables": {
                "emergency_fund_target": target,
                "projection": savings_projected,
                "savings_apy": savings_apy,
                "investment_contribution": investment_contribution,
                "investment_projection": investment_projected,
                "investment_cagr": investment_cagr,
            },
        }
        return summary, structured

    def _fallback_narrative(self, structured: dict) -> str:
        target = structured["supporting_tables"]["emergency_fund_target"]
        projection = structured["supporting_tables"]["projection"]
        savings_apy = structured["supporting_tables"].get("savings_apy") or 0.0
        investment_contribution = structured["supporting_tables"].get("investment_contribution") or 0.0
        investment_projection = structured["supporting_tables"].get("investment_projection")
        investment_cagr = structured["supporting_tables"].get("investment_cagr") or 0.0
        contribution = structured["allocated_amount"] or 0.0
        savings_contribution = contribution - investment_contribution

        lines = [
            "**Savings Strategy (offline rule-based mode)**",
            f"- Target emergency fund: ₹{target[0]:,.0f}-₹{target[1]:,.0f} (3-6 months of expenses).",
            f"- Monthly savings contribution allocated by the roadmap: ₹{savings_contribution:,.0f} (at {savings_apy * 100:.1f}% APY).",
            f"- At this rate, projected savings in 24 months: ₹{projection[-1]['balance']:,.0f}.",
        ]
        if investment_projection is not None:
            lines.append(
                f"- Monthly investment contribution allocated by the roadmap: ₹{investment_contribution:,.0f} "
                f"(at {investment_cagr * 100:.1f}% CAGR)."
            )
            lines.append(f"- At this rate, projected investment balance in 24 months: ₹{investment_projection[-1]['balance']:,.0f}.")
        return "\n".join(lines)
