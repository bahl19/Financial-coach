"""Chat-routing keyword map (Architecture Plan.md, Component 4/7).

Everything this module used to own - `_enrich_context()`'s
`monthly_surplus`/`extra_debt_payment` computation and the `run_full_report()`/
`route_chat()` dict-comprehension fan-out - is retired, not refactored around.
`build_roadmap()` (`utils/roadmap.py`) is now the only place a dollar
allocation is decided, and `agents/graph.py` is the only orchestration path;
keeping the old fan-out alive alongside it would mean two code paths, one of
which still contained the double-allocation bug this plan exists to fix.

`ROUTES`/`match_routes()` are preserved as specified (Implementation Plan -
MVP 1.md, Phase 3); `build_chat_reply()` (Phase 8) is what actually wires
chat routing on top of `agents/graph.py` - the keyword map itself never
changed, only what it dispatches to. The `OrchestratorAgent` backward-
compatible import shim that used to live here (raising `NotImplementedError`
on call, just to keep `app.py` importable before Phase 8 rewired it) is
deleted now that Phase 8 is done and nothing calls it.
"""

ROUTES = {
    "debt": ["debt", "loan", "payoff", "credit card", "apr", "interest"],
    "savings": ["saving", "emergency fund", "invest"],
    "budget": ["budget", "50/30/20", "afford", "overspend"],
    "goals": ["goal", "vacation", "save up", "target"],
    "spending": ["spend", "spending", "category", "trend", "expense"],
}


def match_routes(query: str) -> list:
    """Returns the ROUTES keys whose keywords appear in `query`, or the
    default fallback subset if none match. Pure lookup - no agent calls,
    no context enrichment, no surplus computation."""
    q = query.lower()
    matched = [key for key, keywords in ROUTES.items() if any(kw in q for kw in keywords)]
    return matched or ["spending", "budget"]


_ROUTE_TO_RESULT_KEY = {
    "spending": "spending_result", "budget": "budget_result", "savings": "savings_result",
    "debt": "debt_result", "goals": "goal_result",
}


def build_chat_reply(query: str, graph_result: dict) -> str:
    """Phase 8's chat entry point, wired on top of `agents/graph.py` per
    this module's own docstring. Composes a reply purely from the *same*
    `graph_result` the Overview/specialist tabs already render - matched to
    the query via `match_routes()` - never a second graph invocation or a
    freestanding LLM call. `goal_result` is the one specialist that returns
    a list (one entry per goal), so its narratives are joined individually."""
    matched_routes = match_routes(query)
    narratives = []
    for route in matched_routes:
        result = graph_result.get(_ROUTE_TO_RESULT_KEY[route])
        if result is None:
            continue
        if isinstance(result, list):
            narratives.extend(item["narrative"] for item in result)
        else:
            narratives.append(result["narrative"])
    if not narratives:
        return (
            "I don't have enough information yet to answer that - try asking about "
            "spending, budget, debt, savings, or goals."
        )
    return "\n\n---\n\n".join(narratives)
