"""Base class for specialist agents (Architecture Plan.md, Component 4).

Owns the `SpecialistResult` shape and the ask-or-fallback narrative pattern
(Liskov substitution / template method) so every specialist is
interchangeable behind one contract regardless of which one it is - the
graph and any future caller holds a collection of agents and never branches
on which concrete class it has.

Subclasses implement only `_build_summary(...)` (their own narrow, allocated
inputs -> LLM prompt text + structured fields) and `_fallback_narrative(...)`
(the same structured fields -> an offline, rule-based narrative). Neither
subclass method may accept the whole shared context or profile - the
allocated figure and whatever narrow supporting data a specialist needs are
each an explicit argument, so a specialist can only narrate the number it
was given, never recompute its own.
"""

from typing import Optional

from utils.llm import complete, is_live


class BaseAgent:
    name = "Agent"
    system_prompt = ""

    def _ask(self, user_prompt: str, max_tokens: int = 800) -> tuple:
        """Returns (narrative_or_None, is_live_bool)."""
        reply = complete(self.system_prompt, user_prompt, max_tokens=max_tokens)
        return reply, is_live()

    def _build_summary(self, **kwargs) -> tuple:
        """Returns (llm_prompt_text, structured_fields_dict). Must be
        implemented by every subclass; this is the only method a specialist
        needs to write to participate in the shared result shape.

        `llm_prompt_text` may be falsy (empty string or None) to signal
        "nothing to ask about" (e.g. no debts, no goals) - run() then skips
        the LLM call entirely and goes straight to the fallback narrative,
        rather than spending a call on an empty prompt."""
        raise NotImplementedError

    def _fallback_narrative(self, structured: dict) -> str:
        """Builds an offline, rule-based narrative directly from the
        structured fields _build_summary() produced - must not require an
        LLM or network access."""
        raise NotImplementedError

    def run(self, **kwargs) -> dict:
        """Template method: assembles the one SpecialistResult shape every
        specialist returns. Subclasses never override this."""
        summary_text, structured = self._build_summary(**kwargs)
        if summary_text:
            narrative, live = self._ask(summary_text)
        else:
            narrative, live = None, False
        if narrative is None:
            narrative = self._fallback_narrative(structured)
        return {
            "schema_version": "1.0",
            "agent": self.name,
            "narrative": narrative,
            "allocated_amount": structured.get("allocated_amount"),
            "why_allocated": structured.get("why_allocated"),
            "expected_effect": structured.get("expected_effect", ""),
            "tradeoffs": structured.get("tradeoffs", ""),
            "what_to_monitor": structured.get("what_to_monitor", ""),
            "finding_refs": structured.get("finding_refs", []),
            "trend_refs": structured.get("trend_refs", []),
            "recommends_action_ids": structured.get("recommends_action_ids", []),
            "supporting_tables": structured.get("supporting_tables", {}),
            "live": live,
        }
