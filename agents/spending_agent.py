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

    def run(self, context: dict) -> dict:
        df = context["transactions"]
        by_cat = fc.spending_by_category(df)
        monthly = fc.monthly_cashflow(df)
        trends = fc.category_trends(df)

        data_summary = (
            f"Spending by category (all-time total):\n{by_cat.to_string(index=False)}\n\n"
            f"Monthly cash flow (income vs expenses):\n{monthly.to_string(index=False)}\n\n"
            f"Month-over-month category trends (% change, most recent two months):\n"
            f"{trends.to_string(index=False) if not trends.empty else 'insufficient history'}"
        )
        narrative, live = self._ask(data_summary)
        if narrative is None:
            narrative = self._fallback(by_cat, monthly, trends)

        return {
            "agent": self.name,
            "narrative": narrative,
            "by_category": by_cat,
            "monthly_cashflow": monthly,
            "trends": trends,
            "live": live,
        }

    def _fallback(self, by_cat, monthly, trends) -> str:
        lines = ["**Spending Analysis (offline rule-based mode)**"]
        if not by_cat.empty:
            top = by_cat.iloc[0]
            lines.append(f"- Your largest expense category is **{top['category']}** at ${top['amount']:,.0f}.")
        if not monthly.empty:
            last = monthly.iloc[-1]
            lines.append(
                f"- In {last['month']}, you earned ${last['income']:,.0f} and spent "
                f"${last['expenses']:,.0f} (net ${last['net']:,.0f})."
            )
        if not trends.empty:
            risers = trends[trends["pct_change"] > 15]
            for _, r in risers.iterrows():
                lines.append(f"- ⚠️ {r['category']} spending rose {r['pct_change']:.0f}% month-over-month.")
        return "\n".join(lines)
