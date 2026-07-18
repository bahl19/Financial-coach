"""Chat-routing keyword map (Architecture Plan.md, Component 4/7).

Everything this module used to own - `_enrich_context()`'s
`monthly_surplus`/`extra_debt_payment` computation and the `run_full_report()`/
`route_chat()` dict-comprehension fan-out - is retired, not refactored around.
`build_roadmap()` (`utils/roadmap.py`) is now the only place a dollar
allocation is decided, and `agents/graph.py` is the only orchestration path;
keeping the old fan-out alive alongside it would mean two code paths, one of
which still contained the double-allocation bug this plan exists to fix.

`ROUTES` is preserved as specified (Implementation Plan - MVP 1.md, Phase 3)
for Phase 8 to wire chat routing on top of `agents/graph.py` - the keyword
map itself doesn't change, only what it dispatches to.
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


class OrchestratorAgent:
    """Backward-compatible shim so `app.py` (not rewired until Phase 8)
    still *imports* successfully - the previous `_enrich_context()`,
    `run_full_report()`, and `route_chat()` implementations are deleted,
    not kept working, because they depended on interfaces the Phase 3
    specialist refactor removed (whole-context dict in, no allocated-amount
    guarantee). Calling either method raises clearly, at call time only, so
    the rest of the app (upload, manual entry, review) still loads instead
    of crashing at import - see Implementation Plan - MVP 1.md, Phase 8."""

    ROUTES = ROUTES

    def run_full_report(self, context: dict) -> dict:
        raise NotImplementedError(
            "run_full_report() is retired - the new pipeline is utils.finance_calc + utils.roadmap "
            "+ agents.graph, wired into the UI in Phase 8. See Implementation Plan - MVP 1.md."
        )

    def route_chat(self, query: str, context: dict) -> str:
        raise NotImplementedError(
            "route_chat() is retired - chat routing moves onto agents.graph in Phase 8. "
            "See Implementation Plan - MVP 1.md."
        )
