from agents.base import BaseAgent
from utils import finance_calc as fc


class SpendingAnalyzerAgent(BaseAgent):
    name = "Spending Analyzer"
    system_prompt = (
        "You are a meticulous personal finance analyst. Given a user's categorized "
        "monthly spending data, identify the 2-3 most important patterns, flag any "
        "categories that are unusually high or trending up, and give specific, "
        "numbers-based observations. Be concise (under 180 words), no generic advice."
    )

    def _build_summary(self, transactions) -> tuple:
        by_cat = fc.spending_by_category(transactions)
        monthly = fc.monthly_cashflow(transactions)
        trends = fc.category_trends(transactions)

        summary = (
            f"Spending by category (all-time total):\n{by_cat.to_string(index=False)}\n\n"
            f"Monthly cash flow (income vs expenses):\n{monthly.to_string(index=False)}\n\n"
            f"Month-over-month category trends (% change, most recent two months):\n"
            f"{trends.to_string(index=False) if not trends.empty else 'insufficient history'}"
        )
        structured = {
            # Spending does not allocate money - allocated_amount/why_allocated stay None.
            "expected_effect": "Clearer visibility into where money is going each month.",
            "what_to_monitor": "Categories trending sharply up or down month over month.",
            "supporting_tables": {"by_category": by_cat, "monthly_cashflow": monthly, "trends": trends},
        }
        return summary, structured

    def _fallback_narrative(self, structured: dict) -> str:
        by_cat = structured["supporting_tables"]["by_category"]
        monthly = structured["supporting_tables"]["monthly_cashflow"]
        trends = structured["supporting_tables"]["trends"]

        lines = ["**Spending Analysis (offline rule-based mode)**"]
        if not by_cat.empty:
            top = by_cat.iloc[0]
            lines.append(f"- Your largest expense category is **{top['category']}** at ₹{top['amount']:,.0f}.")
        if not monthly.empty:
            last = monthly.iloc[-1]
            lines.append(
                f"- In {last['month']}, you earned ₹{last['income']:,.0f} and spent "
                f"₹{last['expenses']:,.0f} (net ₹{last['net']:,.0f})."
            )
        if not trends.empty:
            risers = trends[trends["pct_change"] > 15]
            for _, r in risers.iterrows():
                lines.append(f"- ⚠️ {r['category']} spending rose {r['pct_change']:.0f}% month-over-month.")
        return "\n".join(lines)
