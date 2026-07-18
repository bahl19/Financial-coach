"""LangGraph orchestration (Architecture Plan.md, Multi-Agent Orchestration).

Stage 1 (Trend/Insight/Risk Engine) already ran before this graph is
invoked - it consumes `FinancialSnapshot`, `Trend[]`, `Finding[]`, `Risk[]`
as inputs, it does not compute them.

Stage 2 (parallel from START): `spending` and `build_roadmap` - neither
depends on the other. `build_roadmap` is the one and only place a dollar
allocation is decided.

Stage 3 (after Stage 2): `budget`/`savings` depend on `spending`;
`savings`/`debt`/`goal` depend on `build_roadmap`'s allocation. LangGraph's
fan-in (multiple edges into the same node) is what makes `savings` wait for
both predecessors natively - no manual synchronization needed.

Stage 4 (after all of Stage 3): `validate` (utils.validation, Phase 4) runs
the consistency checks and may substitute a specialist's narrative with a
deterministic fallback.

Stage 5 (final): `coach` (utils.coach, Phase 5) selects and ranks from
everything above into one `CoachSummary` - it computes nothing new.

No checkpointer, no interrupts, no state surviving past one `invoke()` call
(Architecture Plan.md: "no persistent workflow checkpoints").

Every node below is a thin adapter over a pure function it does not own the
logic of - `roadmap_node` calls `utils.roadmap.build_roadmap()`, the
specialist nodes call the specialist agents. This is what keeps
`run_pipeline_direct()` a genuine, equivalent fallback rather than a second
implementation: it calls the exact same node functions, just chained
directly instead of through LangGraph.
"""

from __future__ import annotations

from typing import List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.budget_agent import BudgetAdvisorAgent
from agents.debt_agent import DebtAnalyzerAgent
from agents.goal_agent import GoalPlannerAgent
from agents.savings_agent import SavingsStrategyAgent
from agents.spending_agent import SpendingAnalyzerAgent
from utils import coach as coach_module
from utils import finance_calc as fc
from utils import roadmap as rm
from utils import validation as val
from utils.contracts import FinancialProfile, FinancialSnapshot


class GraphState(TypedDict, total=False):
    profile: FinancialProfile
    snapshot: FinancialSnapshot
    findings: list
    risks: list
    trends: list  # needed by validation_node's checks 5 and 8, not by Stage 2/3 nodes
    spending_result: dict
    roadmap_result: dict
    budget_result: dict
    savings_result: dict
    debt_result: dict
    goal_result: list
    validation_result: dict
    coach_summary: dict


def _find_action_by_id(roadmap: dict, action_id: Optional[str]) -> Optional[dict]:
    if action_id is None:
        return None
    return next((a for a in roadmap["actions"] if a["action_id"] == action_id), None)


def _find_action_for_goal(roadmap: dict, goal_name: str) -> Optional[dict]:
    return next((a for a in roadmap["actions"] if a.get("title") == f"Fund goal: {goal_name}"), None)


# --------------------------------------------------------------------------
# Node functions - each is a thin adapter: extract narrow inputs from state,
# call one pure function/agent, return the partial state update.
# --------------------------------------------------------------------------

def spending_node(state: GraphState) -> dict:
    transactions_df = fc._transactions_to_frame(state["profile"].get("transactions") or [])
    return {"spending_result": SpendingAnalyzerAgent().run(transactions=transactions_df)}


def roadmap_node(state: GraphState) -> dict:
    roadmap = rm.build_roadmap(state["profile"], state["snapshot"], state["findings"], state["risks"])
    return {"roadmap_result": roadmap}


def budget_node(state: GraphState) -> dict:
    tables = state["spending_result"]["supporting_tables"]
    result = BudgetAdvisorAgent().run(
        by_category=tables["by_category"],
        monthly_cashflow=tables["monthly_cashflow"],
        monthly_income=state["profile"].get("monthly_income") or 0.0,
    )
    return {"budget_result": result}


def savings_node(state: GraphState) -> dict:
    roadmap = state["roadmap_result"]
    monthly_cashflow = state["spending_result"]["supporting_tables"]["monthly_cashflow"]
    action = _find_action_by_id(roadmap, rm.ACTION_GROW_SAVINGS) or _find_action_by_id(roadmap, rm.ACTION_STARTER_BUFFER)
    result = SavingsStrategyAgent().run(
        monthly_cashflow=monthly_cashflow,
        current_savings=state["profile"].get("current_savings") or 0.0,
        savings_contribution=roadmap["allocation"]["savings_contribution"],
        action_id=action["action_id"] if action else None,
        finding_refs=action["finding_refs"] if action else [],
    )
    return {"savings_result": result}


def debt_node(state: GraphState) -> dict:
    roadmap = state["roadmap_result"]
    action = _find_action_by_id(roadmap, rm.ACTION_ACCELERATE_DEBT)
    result = DebtAnalyzerAgent().run(
        debts=state["profile"].get("debts") or [],
        extra_debt_payment=roadmap["allocation"]["debt_extra_payment"],
        action_id=action["action_id"] if action else None,
        finding_refs=action["finding_refs"] if action else [],
    )
    return {"debt_result": result}


def goal_node(state: GraphState) -> dict:
    roadmap = state["roadmap_result"]
    goals = state["profile"].get("goals") or []
    action_ids_by_goal, finding_refs_by_goal = {}, {}
    for goal in goals:
        action = _find_action_for_goal(roadmap, goal["name"])
        if action:
            action_ids_by_goal[goal["name"]] = action["action_id"]
            finding_refs_by_goal[goal["name"]] = action["finding_refs"]
    result = GoalPlannerAgent().run(
        goals=goals,
        goal_contributions=roadmap["allocation"]["goal_contributions"],
        action_ids_by_goal=action_ids_by_goal,
        finding_refs_by_goal=finding_refs_by_goal,
    )
    return {"goal_result": result}


def validation_node(state: GraphState) -> dict:
    """Stage 4 (Architecture Plan.md, Consistency Validator): runs after
    all of Stage 3 completes. Detection and remediation are two separate
    calls (utils.validation keeps them separate on principle) composed here
    at the one place that actually needs both - the corrected specialist
    results replace the originals in graph state; untouched ones pass
    through unchanged."""
    specialist_results = {
        "spending_result": state["spending_result"],
        "budget_result": state["budget_result"],
        "savings_result": state["savings_result"],
        "debt_result": state["debt_result"],
        "goal_result": state["goal_result"],
    }
    corrected, validation_result = val.apply_consistency_fallback(
        state["roadmap_result"], specialist_results, state["snapshot"],
        state["findings"], state["risks"], state["trends"],
    )
    update = dict(corrected)
    update["validation_result"] = validation_result
    return update


def coach_node(state: GraphState) -> dict:
    """Stage 5 (Architecture Plan.md, Coach Synthesis): the final stage.
    Reads the validated specialist results (post-Stage-4 correction, if
    any) - selects and ranks, computes nothing new."""
    specialist_results = {
        "spending_result": state["spending_result"],
        "budget_result": state["budget_result"],
        "savings_result": state["savings_result"],
        "debt_result": state["debt_result"],
        "goal_result": state["goal_result"],
    }
    summary = coach_module.synthesize_coach_summary(
        state["snapshot"], state["trends"], state["findings"], state["risks"],
        state["roadmap_result"], specialist_results,
    )
    return {"coach_summary": summary}


# --------------------------------------------------------------------------
# Graph assembly
# --------------------------------------------------------------------------

def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("spending", spending_node)
    graph.add_node("build_roadmap", roadmap_node)
    graph.add_node("budget", budget_node)
    graph.add_node("savings", savings_node)
    graph.add_node("debt", debt_node)
    graph.add_node("goal", goal_node)
    graph.add_node("validate", validation_node)
    graph.add_node("coach", coach_node)

    # Stage 2: parallel from START, no dependency between them.
    graph.add_edge(START, "spending")
    graph.add_edge(START, "build_roadmap")

    # Stage 3: budget/savings need spending_result; savings/debt/goal need
    # roadmap_result. LangGraph fans savings in from both predecessors.
    graph.add_edge("spending", "budget")
    graph.add_edge("spending", "savings")
    graph.add_edge("build_roadmap", "savings")
    graph.add_edge("build_roadmap", "debt")
    graph.add_edge("build_roadmap", "goal")

    # Stage 4: validation fans in from all four Stage 3 nodes - it must not
    # run until every specialist result exists.
    graph.add_edge("budget", "validate")
    graph.add_edge("savings", "validate")
    graph.add_edge("debt", "validate")
    graph.add_edge("goal", "validate")

    # Stage 5: coach synthesis is the final stage.
    graph.add_edge("validate", "coach")
    graph.add_edge("coach", END)

    return graph.compile()  # no checkpointer argument - no persistence, ever


def run_graph(
    profile: FinancialProfile, snapshot: FinancialSnapshot, findings: List, risks: List, trends: List,
) -> GraphState:
    """Compiles and invokes the graph fresh for this call - no state
    survives past this single invocation."""
    graph = build_graph()
    initial_state: GraphState = {
        "profile": profile, "snapshot": snapshot, "findings": findings, "risks": risks, "trends": trends,
    }
    return graph.invoke(initial_state)


def run_pipeline_direct(
    profile: FinancialProfile, snapshot: FinancialSnapshot, findings: List, risks: List, trends: List,
) -> GraphState:
    """The documented fallback path if the graph isn't stable (Implementation
    Plan - MVP 1.md, Phase 3): the exact same node functions, called
    directly and sequentially with no LangGraph involved. Also used as the
    reference implementation the graph's output is checked against for
    drift."""
    state: GraphState = {
        "profile": profile, "snapshot": snapshot, "findings": findings, "risks": risks, "trends": trends,
    }
    state.update(spending_node(state))
    state.update(roadmap_node(state))
    state.update(budget_node(state))
    state.update(savings_node(state))
    state.update(debt_node(state))
    state.update(goal_node(state))
    state.update(validation_node(state))
    state.update(coach_node(state))
    return state
