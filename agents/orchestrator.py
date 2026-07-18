from agents.spending_agent import SpendingAnalyzerAgent
from agents.debt_agent import DebtAnalyzerAgent
from agents.savings_agent import SavingsStrategyAgent
from agents.budget_agent import BudgetAdvisorAgent
from agents.goal_agent import GoalPlannerAgent
from utils import finance_calc as fc


class OrchestratorAgent:
    """Coordinates the specialist financial agents and routes user chat queries
    to whichever of them is relevant."""

    ROUTES = {
        "debt": ["debt", "loan", "payoff", "credit card", "apr", "interest"],
        "savings": ["saving", "emergency fund", "invest"],
        "budget": ["budget", "50/30/20", "afford", "overspend"],
        "goals": ["goal", "vacation", "save up", "target"],
        "spending": ["spend", "spending", "category", "trend", "expense"],
    }

    def __init__(self):
        self.agents = {
            "spending": SpendingAnalyzerAgent(),
            "debt": DebtAnalyzerAgent(),
            "savings": SavingsStrategyAgent(),
            "budget": BudgetAdvisorAgent(),
            "goals": GoalPlannerAgent(),
        }

    def _enrich_context(self, context: dict) -> dict:
        monthly = fc.monthly_cashflow(context["transactions"])
        avg_expenses = monthly["expenses"].mean() if not monthly.empty else 0
        context["monthly_surplus"] = max(context.get("monthly_income", 0) - avg_expenses, 0)
        context.setdefault("extra_debt_payment", context["monthly_surplus"] * 0.3)
        return context

    def run_full_report(self, context: dict) -> dict:
        context = self._enrich_context(context)
        return {key: agent.run(context) for key, agent in self.agents.items()}

    def route_chat(self, query: str, context: dict) -> str:
        context = self._enrich_context(context)
        q = query.lower()
        matched = [key for key, keywords in self.ROUTES.items() if any(kw in q for kw in keywords)]
        if not matched:
            matched = ["spending", "budget"]

        responses = []
        for key in matched:
            agent = self.agents[key]
            if key == "goals" and not context.get("goals"):
                continue
            result = agent.run(context)
            if key == "goals":
                for g in result["goals"]:
                    responses.append(f"**{agent.name} -- {g['name']}:** {g['narrative']}")
            elif result.get("narrative"):
                responses.append(f"**{agent.name}:** {result['narrative']}")

        if not responses:
            return "I don't have enough data yet -- try loading your transactions and debts first."
        return "\n\n".join(responses)
