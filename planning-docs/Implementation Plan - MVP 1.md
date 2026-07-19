# MVP 1 Implementation Plan: Phased, Gated Delivery

Source: [Architecture Plan.md](Architecture%20Plan.md). This plan converts that document's component model into **strictly sequential phases**. A phase may involve multiple people working concurrently on its own tasks, but **no work on the next phase starts until the current phase's gate is fully checked and signed off**.

**MVP 1 is a standalone, independently shippable product.** It contains no MVP 2 work. The strategy-policy layer, RAG corpus, embedding retrieval, and preference-capture UI all belong to [MVP 2](Architecture%20Plan%20-%20MVP%202.md) and begin only after Phase 11's gate is fully green. Do not start MVP 2 work in parallel, and do not leave MVP 2 stubs, contracts, or feature flags in the MVP 1 codebase.

This revision incorporates `Review.md`'s structural review and the fixes recorded in [gaps.md](gaps.md): a deterministic Trend/Insight/Risk Engine (Phase 2), structured specialist output (Phase 3), a consistency validator (Phase 4), Coach synthesis (Phase 5), and a golden-fixture freeze (Phase 6). See `Architecture Plan.md`'s Review Triage section for the full Critical/Important/Production/Future split — this plan implements only the Critical tier.

## Rules for every phase

1. A phase has a fixed task list, an entry criterion, and an exit gate (a checklist).
2. The exit gate must be 100% checked — not "mostly" — before the next phase opens.
3. Mark a phase done by: merging its PR(s) to `main`, ticking every gate box below, recording the date and verifier in the **Phase Status Tracker**, and tagging the commit (`git tag phaseN-done`).
4. If a gate fails, fix and re-verify inside the same phase. Do not start the next phase "in the meantime."
5. **Every phase is mandatory, and the chain is strictly linear: 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11.** No phase is optional and no phase may be skipped or reordered. Each phase is verifiable using only work completed in earlier phases — if a gate item cannot be checked with what exists at that point, the gate item is in the wrong phase.
6. MVP 2 work does not begin until Phase 11 is green. MVP 1 must be demonstrably bug-free and fully tested on its own first.

## Phase Status Tracker

| Phase | Name | Status | Completed | Verified by |
|---|---|---|---|---|
| 0 | Contracts & fixtures | Done (see caveats in gate) | 2026-07-19 | Automated test suite (48/48) |
| 1 | Ingestion + Financial core + data quality | Done (see caveats in gate) | 2026-07-19 | Automated test suite (102/102) |
| 2 | Trend, Insight, and Risk Engine | Done (see caveats in gate) | 2026-07-19 | Automated test suite (124/124) |
| 3 | Roadmap Planner (LangGraph) + structured specialists + Scenarios | Done (see caveats in gate) | 2026-07-19 | Automated test suite (202/202) |
| 4 | Consistency Validator | Done (see caveats in gate) | 2026-07-19 | Automated test suite (228/228) |
| 5 | Coach Synthesis | Done (see caveats in gate) | 2026-07-19 | Automated test suite (263/263) |
| 6 | Golden Fixture Freeze | Not started | | |
| 7 | Reports & tracker | Not started | | |
| 8 | Streamlit integration | Not started | | |
| 9 | Validation, property tests & regression | Not started | | |
| 10 | UX & narrative polish | Not started | | |
| 11 | Demo rehearsal & release gate | Not started | | |

---

## Phase 0 — Contracts & Fixtures (blocking)

**Entry criterion:** Team has read the Architecture Plan's Canonical Contracts section and agreed on it.

**Tasks**
- Implement `utils/contracts.py` (`TypedDict`/dataclasses) for: `Transaction`, `Debt`, `Goal`, `PlanningAssumptions`, `FinancialProfile`, `ReviewItem`, `FinancialSnapshot` (including `gross_surplus`, `allocatable_surplus`, `required_commitments`, `period`, `is_partial_period`, `data_quality_flags`), `Trend`, `Finding`, `Risk`, `SpecialistResult`, `Roadmap` (with `allocation` and per-action `action_id`), `ValidationResult`, `CoachSummary`, `ReportPackage`.
- Do **not** define `PreferenceProfile`, `DecisionContext`, `EvidenceQuery`, `EvidenceBundle`, `StrategyPolicy`, or `PlanValidation` — those are MVP 2 contracts and must not appear in the MVP 1 codebase.
- Implement `default_assumptions()`, `validate_profile()`, `validate_assumptions()`.
- Commit real, loadable **input** fixture files under `fixtures/*.json`: a valid `FinancialProfile`, an invalid one (bad budget split), a debt with negative balance, an empty debt/goals profile, and one example each of `Finding`/`Trend`/`Risk`/`SpecialistResult` for contract tests.
- Commit the three **golden-fixture input profiles** under `fixtures/golden/*.input.json`: (1) stable high surplus, (2) negative cashflow / income collapse, (3) sharp income drop with rising dining spend. Their *expected outputs* are authored later, in Phase 6 — they cannot exist until the pipeline that produces them does.
- Add `tests/test_contracts.py`. Add `pytest` and `hypothesis` to `requirements.txt` as dev dependencies (`hypothesis` is used in Phase 9).

**Exit gate — all must pass**
- [x] Rejects a budget split that does not total 1.0
- [x] Rejects debt balances or minimum payments below zero
- [x] Accepts an empty debt or goals list
- [x] Unknown values preserved as `None`, never coerced to zero
- [x] `fixtures/*.json` and `fixtures/golden/*.input.json` exist and load without error
- [x] No MVP 2 contract (`PreferenceProfile`, `StrategyPolicy`, `EvidenceBundle`, `DecisionContext`, `PlanValidation`) exists anywhere in the codebase
- [ ] `tests/test_contracts.py` passes in CI — **caveat:** 48/48 pass locally via `pytest`; no CI pipeline (`.github/workflows/`) exists in this repo yet, so "in CI" is currently unverifiable as literally stated
- [ ] PR merged to `main`, tagged `phase0-done` — pending explicit request; not performed unilaterally

---

## Phase 1 — Ingestion + Financial Core + Data Quality

**Entry criterion:** Phase 0 marked done.

**Tasks (can run in parallel with each other, not with later phases)**
- Ingestion: `load_transactions()`, `categorize_with_confidence()`, `tag_transaction_types()`, `build_review_items()`, `questionnaire_to_profile_fields()` in `agents/data_agent.py` / `utils/ingestion.py`. `tag_transaction_types()` is cheap category-derived tagging (`Debt Payment` category → `debt_payment`, `Income` category → `income`, everything else → `expense`/`unknown`) — not a dedicated classifier.
- **Data quality:** `detect_data_quality_issues(transactions) -> list[dict]` producing flags for: exact duplicate rows (same date + description + amount), missing months inside the date range, a partial trailing month (last month's data ends before month-end), fewer than 2 complete months of history, and zero income transactions. Store the result on `FinancialSnapshot.data_quality_flags`. This is deliberately a handful of DataFrame checks — **not** the full anomaly engine, which is deferred to Production per the Review Triage. It exists here because Phase 2's `data_quality` finding type has no other input source.
- Financial core: `calculate_financial_snapshot()`, `calculate_health_score()` in `utils/finance_calc.py`, computing average monthly expenses, `gross_surplus = monthly_income - average_monthly_expenses`, `required_commitments` (debt minimums *not already reflected* in `average_monthly_expenses` via the existing `Debt Payment` category — do not double-subtract minimums already inside expenses), `allocatable_surplus = max(0, gross_surplus - required_commitments - minimum_monthly_buffer)`, savings rate, debt-to-income, emergency-fund months, total debt, payoff comparison, budget variance, and goal feasibility.

**Standing constraint:** no LLM call anywhere in this phase — the financial core is deterministic only. `monthly_surplus` stays as an alias of `gross_surplus` for backward compatibility; new code reads `gross_surplus`/`allocatable_surplus` explicitly.

**Exit gate — all must pass**
- [x] An unmatched expense is `Other`, confidence `0.0`, appears in the review list
- [ ] A user category correction persists into the profile used by calculation — **caveat:** `categorize_with_confidence()`'s non-mutation precondition is verified; the full path through session state is Phase 8's job and not yet wireable
- [x] Existing sample data loads without new required columns
- [x] A `Debt Payment`-categorized transaction is tagged `transaction_type: "debt_payment"` and is not double-counted in `required_commitments`
- [x] Debt balances never go negative in payoff timelines
- [x] `allocatable_surplus` is never negative, and equals `max(0, gross_surplus − required_commitments − minimum_monthly_buffer)` for every Phase 0 fixture
- [x] `gross_surplus <= 0` forces `allocatable_surplus == 0` (verified with the negative-cashflow golden input)
- [x] A fixture with a duplicated transaction and a missing month produces the corresponding `data_quality_flags`
- [x] A user with no debt gets an empty/explicit debt-free result, not a crash
- [ ] Both components' unit tests pass in CI — **caveat:** 102/102 pass locally; no CI pipeline exists yet (same caveat as Phase 0)
- [ ] PRs merged to `main`, tagged `phase1-done` — pending explicit request

> **Note:** the "a plan cannot allocate more than `allocatable_surplus`" invariant is deliberately **not** in this gate — no plan exists until Phase 3. It is verified in Phase 3's gate instead.

---

## Phase 2 — Trend, Insight, and Risk Engine

**Entry criterion:** Phase 1 marked done (needs a working `FinancialSnapshot` with `gross_surplus`/`allocatable_surplus`/`data_quality_flags`).

This phase exists because specialist agents currently re-derive the same pattern independently — or invent a plausible-sounding one — with no shared record. That is `Review.md`'s core finding. Everything here is a pure function; no LLM call anywhere in this phase.

**Tasks**
- `compute_trends(profile, snapshot) -> list[Trend]` — MVP 1 scope is 6 trend types: monthly income, monthly expenses, monthly surplus, category spending, debt balances, savings balances (including `emergency_fund_months` as a runway trend). Each returns a `Trend` (`trend_id`, `metric`, `period`, `start_value`, `end_value`, `absolute_change`, `percent_change`, `direction`, `classification`).
- `derive_findings(snapshot, trends) -> list[Finding]` — MVP 1 scope is 8 finding types: income changes, expense changes, category trends, cashflow deterioration/improvement, debt risks, emergency-fund risks, goal feasibility issues, and **data-quality problems (read from `snapshot.data_quality_flags`, produced in Phase 1)**. Every `Finding` carries `severity`, `urgency`, `confidence`, and `fact_or_inference` (`fact` or `deterministic_inference` only — MVP 1 never generates an LLM `hypothesis`-labeled finding; unusual-spending and spending-substitution inference are explicitly deferred, not approximated).
- `derive_risks(snapshot, findings) -> list[Risk]` — MVP 1 scope is 6 risk types: negative cashflow, insufficient emergency fund, high-interest debt, high debt-service burden, overspending vs. budget, goal failure. Supersedes the old flat `risk_flags` list; keep `risk_flags` as a derived, backward-compatible projection of `Risk` objects, never a second independent source.
- Confidence rule: a fact-based finding gets `confidence: 1.0`; a deterministic-inference finding (e.g. overspending past a defined threshold) gets a confidence from a fixed, documented formula based on distance past the threshold — never an LLM-invented number.

**Standing constraint:** `Trend`/`Finding`/`Risk` objects are computed exactly once per snapshot. No specialist agent, roadmap step, or report recomputes a percent-change or risk classification independently — they reference the ID.

**Exit gate — all must pass**
- [x] All 6 trend types compute correctly against the Phase 0 fixtures
- [x] All 8 finding types compute correctly, each with `severity`/`urgency`/`confidence`/`fact_or_inference` populated
- [x] The data-quality finding type is populated from `snapshot.data_quality_flags` and produces findings for the duplicate-transaction and missing-month fixture from Phase 1
- [x] All 6 risk types compute correctly, each referencing at least one `finding_id` where applicable
- [x] No `Finding` is tagged `hypothesis`
- [x] The income-drop-plus-rising-dining golden input produces the expected `Trend`/`Finding` IDs with correct classification
- [x] `risk_flags` (legacy) is a correct projection of the new `Risk` objects, not independently computed
- [ ] PRs merged to `main`, tagged `phase2-done` — pending explicit request

> **Caveats carried over from Phase 0/1, unchanged:** "passes in CI" still means "passes locally via `pytest`" — no CI pipeline exists in this repo yet.
>
> **Interface limitations found and documented in code, not silently papered over:**
> - `derive_findings()`/`derive_risks()`'s signature is `(snapshot, ...)` only, per this plan — it does not receive raw `debts`, so "debt risk" and "high-interest debt" detection use proxies (`debt_to_income_percent`, and `total_interest / total_debt` at minimums-only) rather than inspecting individual APRs directly. An **earlier version of the high-interest-debt risk was structurally broken** (compared avalanche vs. snowball total interest, which are always identical at the baseline `extra_monthly=0.0` comparison since there's no extra payment to allocate differently) — this was caught before shipping and replaced with the total-interest-to-debt-ratio proxy; see `utils/finance_calc.py`'s `_high_interest_debt_risk` docstring.
> - "Overspending vs. budget" uses the sharp-expense-increase finding as a proxy for "overspending relative to recent history," not literally "overspending relative to the 50/30/20 recommendation" (the bucketed split isn't in `FinancialSnapshot.metrics`).
> - "Debt balances" and "savings balances" trend types are proxied by monthly `Debt Payment`/`Savings/Investing` category *spend* (the only historical time series MVP 1 has, with no persisted balance snapshots) rather than literal balance-over-time trends. The "emergency-fund runway" trend is a target-vs-actual comparison, not a time-series trend, for the same reason.
>
> If better accuracy is wanted for the debt-related risks, the fix is adding `max_debt_apr`/`total_minimum_payments` to `FinancialSnapshot.metrics` — a small, additive contract extension, not implemented here since it reopens Phase 0's frozen contract and wasn't requested.

---

## Phase 3 — Roadmap Planner (LangGraph) + Structured Specialists + Scenarios

**Entry criterion:** Phase 2 marked done (needs `Trend[]`/`Finding[]`/`Risk[]`).

> **⚠️ Highlighted fix — this phase corrects a real double-allocation bug, not a refactor of taste.** Today, `agents/orchestrator.py:34` hands Debt a hardcoded 30% of surplus, `agents/savings_agent.py:22` independently claims a hardcoded 50% of surplus, and `agents/goal_agent.py:16-20` treats the *entire* surplus as available to *each* goal — three uncoordinated claims on the same money, with nothing checking they stay under 100%. The fix is ordering: `build_roadmap()` runs **first**, as the single deterministic waterfall allocator over `allocatable_surplus`, and Debt/Savings/Goal narrate the dollar figure it already assigned them instead of computing their own share.

**Tasks**

*Roadmap core*
- `build_roadmap(profile, snapshot, findings, risks) -> Roadmap` implementing the deterministic priority order — (1) resolve invalid/missing inputs before allocating, (2) protect the configured buffer and debt minimums, (3) fund a starter emergency buffer below target, (4) direct remaining debt allocation to avalanche when high-interest debt exists, (5) fund feasible high-priority goals, (6) allocate remainder to savings — returning an `allocation` dict (`buffer_reserved`, `debt_extra_payment`, `goal_contributions` per goal, `savings_contribution`) whose *distributed* values (excluding `buffer_reserved`) sum to no more than `allocatable_surplus`. Each `Roadmap.actions[]` entry gets a stable `action_id` and references `finding_refs`/`risk_refs` alongside `metric_refs`.
- `explain_roadmap()` — LLM narrative with fallback to the unchanged action list — in `agents/roadmap_agent.py` / `utils/roadmap.py`.

> **Design decision (divergence from `Review.md` item 4, recorded deliberately):** the six-step waterfall order is **fixed and does not vary with finding/risk severity**. Severity and urgency control *presentation* (Coach Summary bucketing, UI emphasis) and *report ordering*, not the allocation sequence. A deterministic, always-identical ordering is auditable and testable; a severity-reshuffled one is neither. Do not add severity-based reordering to `build_roadmap()` in MVP 1.

*Structured specialist output — this is what makes Phase 4 possible*
- Refactor all five specialist agents to return a `SpecialistResult` alongside their narrative:
  ```python
  {
      "agent": "Debt Analyzer",
      "narrative": "...",                        # free text, display only
      "allocated_amount": 720.0,                 # copied from roadmap.allocation; None for non-allocating agents
      "why_allocated": "ACTION_ACCELERATE_DEBT", # action_id, not prose
      "expected_effect": "...",
      "tradeoffs": "...",
      "what_to_monitor": "...",
      "finding_refs": ["FINDING_HIGH_APR_DEBT"],
      "trend_refs": ["TREND_DEBT_BALANCE_3M"],
      "recommends_action_ids": ["ACTION_ACCELERATE_DEBT"],
  }
  ```
  `allocated_amount` is **always** copied from `roadmap.allocation`, never computed. Spending and Budget do not allocate money, so their `allocated_amount` is `None` and `recommends_action_ids` may be empty.
- Refactor `agents/savings_agent.py` — stop calling `fc.monthly_cashflow(context["transactions"])` and computing `surplus * 0.5` (`savings_agent.py:16,22`); take `spending_result`'s `monthly_cashflow` for context and `roadmap_result.allocation["savings_contribution"]` for the figure to narrate.
- Refactor `agents/budget_agent.py` to take `spending_result`'s `by_category` instead of recomputing `fc.spending_by_category` via `actual_budget_split` (`budget_agent.py:17`). Budget doesn't allocate surplus, so it needs no `roadmap_result` dependency.
- Refactor `agents/debt_agent.py` — stop reading `context.get("extra_debt_payment", 0)`; take `roadmap_result.allocation["debt_extra_payment"]`.
- Refactor `agents/goal_agent.py` — stop treating `context.get("monthly_surplus", 0)` as available to every goal (`goal_agent.py:16-20`); take each goal's allocated contribution from `roadmap_result.allocation["goal_contributions"]`.
- **Refactor `agents/orchestrator.py`:** delete `_enrich_context()`'s `extra_debt_payment` default (`:34`) and its `monthly_surplus` recomputation (`:33`) — both now come from `build_roadmap()`. Reduce `run_full_report()` to a thin wrapper over the graph invocation, or delete it. Preserve the `ROUTES` keyword mapping, which Phase 8 rewires for chat. Leaving the old fan-out path alive means two code paths, one of which still contains the bug.

*LangGraph orchestration*
- Add `langgraph` to `requirements.txt`; build `agents/graph.py`:
  - **Stage 1** (from Phases 1-2, feeds this stage): `FinancialSnapshot`, `Trend[]`, `Finding[]`, `Risk[]`.
  - **Stage 2** (parallel): `spending` node; `build_roadmap()` node.
  - **Stage 3** (after Stage 2): `budget` and `savings` read `spending_result`; `savings`, `debt`, `goal` read `roadmap_result.allocation`.
  
  No checkpointer, no interrupts, no state persisted past a single invocation. Graph state is one typed schema with a result key per node: `spending_result`, `roadmap_result`, `debt_result`, `savings_result`, `budget_result`, `goal_result`.

*Scenarios*
- `apply_assumptions()`, `compare_scenarios()` in `utils/scenarios.py`.

**Standing constraint:** `build_roadmap()` is the only place a dollar allocation decision is made. Every specialist narrates a number it already produced. When `gross_surplus <= 0`, no specialist may narrate a positive extra-payment or investment amount — this must be true **by construction here**, before Phase 4 adds the automated check.

**Fallback if the graph isn't stable by the end of this phase:** call `build_roadmap()` directly first, then the specialist agents with its `allocation` values passed as plain function arguments (no graph); revisit LangGraph after Phase 11 rather than blocking the gate. Do **not** fall back to the old hardcoded 30%/50%/full-surplus behavior — that reintroduces the bug this phase exists to fix.

**Exit gate — all must pass**
- [x] Every roadmap action points to a snapshot metric, and to a `finding_id`/`risk_id` where one exists
- [x] Action priorities are unique and sequential; every action has a stable `action_id`
- [x] `sum(distributed allocation)` (goal contributions summed, `buffer_reserved` excluded) never exceeds `allocatable_surplus` — enforced structurally by an allocation-ledger abstraction (`utils/roadmap.py:_AllocationLedger`), not just checked after the fact
- [x] Every specialist returns a complete `SpecialistResult`; `allocated_amount` is copied from `roadmap.allocation`, never computed locally
- [x] `grep -rn '\* 0\.3\|\* 0\.5' agents/` returns no allocation-related matches
- [x] `agents/orchestrator.py` no longer sets `extra_debt_payment` or recomputes `monthly_surplus`
- [x] Invalid ratios/negative rates return validation issues, not silent acceptance
- [x] Previewing a scenario does not mutate the base profile
- [x] Graph runs without a checkpointer and completes within a single invocation
- [x] Graph-produced `Roadmap` matches calling `build_roadmap()` directly (no drift)
- [x] `savings` and `budget` consume `spending_result` instead of recomputing `monthly_cashflow`/`spending_by_category`
- [x] `debt`, `savings`, and `goal` quote the exact dollar figures in `roadmap.allocation`
- [x] The negative-cashflow golden input produces a roadmap where `debt_extra_payment`, `savings_contribution`, and every `goal_contributions` entry are `0`
- [ ] PRs merged to `main`, tagged `phase3-done` — pending explicit request

> **Caveat carried over, unchanged:** "passes in CI" still means "passes locally via `pytest`" — no CI pipeline exists yet.
>
> **A real regression caught and fixed before it shipped:** deleting `agents/orchestrator.py`'s old `OrchestratorAgent` class (as the task list implies) would have broken `app.py`'s import entirely — `streamlit run app.py` would crash on startup, not just have a stale feature. `app.py` isn't rewired until Phase 8, so a class-shaped shim was kept: it imports and instantiates cleanly, and its two methods raise a clear, explicit error only if actually *called* (not at import time), pointing to Phase 8. This is different from — and less invasive than — the "keep the old code fully working" approach Phase 1 used for `categorize_transactions`, because the old orchestrator's methods are not merely superseded, they are *incompatible* with the new narrow specialist interfaces and cannot be preserved working as-is.
>
> **One documented, deliberate exception to "every specialist shares one result shape":** `GoalPlannerAgent.run()` returns a `list[SpecialistResult]`, one per goal, rather than a single result — goals are inherently a collection, and folding them into one narrative would lose the per-goal traceability Phase 4's validator needs (a shortfall in one goal must not be indistinguishable from a shortfall in another). This is recorded in the class docstring and in `tests/test_specialist_agents.py`'s Liskov check, which explicitly carves out this one exception rather than silently special-casing it.

---

## Phase 4 — Consistency Validator

**Entry criterion:** Phase 3 marked done (needs a `Roadmap` **and** structured `SpecialistResult` objects — without the latter, most checks below are not implementable).

This phase generalizes the Phase 3 fix into a standing automated check, so a future change cannot silently reintroduce the double-allocation bug or a similar drift.

**Tasks**
- `validate_consistency(roadmap, specialist_results, snapshot, findings, risks, trends) -> ValidationResult` in `utils/validation.py`.

  **Structured checks** (authoritative — operate on `SpecialistResult` fields, fully deterministic):
  1. Every `recommends_action_ids` entry exists in `roadmap.actions`.
  2. The order of `recommends_action_ids` is consistent with those actions' `priority` values.
  3. Each `allocated_amount` exactly equals the corresponding `roadmap.allocation` entry.
  4. If `allocation[x] == 0`, no specialist reports `allocated_amount > 0` for `x` and no `recommends_action_ids` entry maps to an action allocating `x`.
  5. Every `finding_refs`/`trend_refs`/`risk_refs` entry resolves against this invocation's objects.
  6. No action's `monthly_amount` exceeds `allocatable_surplus`.

  **Prose checks** (secondary safety net over the free-text `narrative`, best-effort by design):
  7. Every `$` amount in a narrative appears in an allowlist derived from `roadmap.allocation` + `snapshot.metrics`.
  8. Every `%` in a narrative resolves to a `Trend.percent_change` or a snapshot metric.
  9. No narrative quotes an income/expense/surplus value absent from `snapshot.metrics`.

  Checks 7-9 are explicitly best-effort — they will not catch a figure spelled "twelve hundred". They are defense in depth; checks 1-6 are the guarantee.
- On failure: replace the offending narrative with a deterministic fallback built from `roadmap.actions`/`allocation`/findings (the same style as each agent's existing offline fallback), and set `ValidationResult.fallback_used = True`. This must be visible in tests and disclosed in a demo, never hidden.
- Wire as a graph stage after Stage 3 in `agents/graph.py`.

**Exit gate — all must pass**
- [x] Each of checks 1-6 has a dedicated test that deliberately breaks the invariant and confirms it is caught
- [x] Each of checks 7-9 has a test with an obvious in-prose violation and confirms it is caught
- [x] A corrupted `SpecialistResult` (`allocated_amount` not matching `roadmap.allocation`) is replaced by the deterministic fallback, with `fallback_used = True`
- [x] A clean run reports `valid: True`, `fallback_used: False` — verified across every committed fixture, not just one
- [x] The negative-cashflow golden input passes check 4 (nothing recommends a positive allocation)
- [ ] PR merged to `main`, tagged `phase4-done` — pending explicit request

> **Caveat carried over, unchanged:** "passes in CI" still means "passes locally via `pytest`" — no CI pipeline exists yet.
>
> **Design refinement beyond the plan's literal wording, per the Phase 4 execution prompt:** the two check tiers live in **separate modules** (`utils/validation_structured.py`, `utils/validation_prose.py`), not just separate functions in one file — the plan named only `utils/validation.py` as the location, but the prompt's guidance ("blurring them in one file invites someone later to treat a heuristic as a guarantee") took precedence. `utils/validation.py` is now a thin composer exposing `validate_consistency()` (pure detection) and `apply_consistency_fallback()` (a genuinely separate remediation step) — a check never mutates what it inspects.
>
> **Two real bugs caught while building the "clean run must be valid" test — not the checks being wrong, the checks working as intended:**
> 1. The prose checks' dollar/percent allowlists were initially built only from `roadmap.allocation` + a handful of `snapshot.metrics` keys, which is too narrow — legitimate narrative content (spending's category totals, savings' emergency-fund target range, a computed "over/under by $X" in budget's fallback) isn't drawn from either source. Fixed by widening each check's allowlist to also include the specific specialist's own `supporting_tables` (its grounding data), which is exactly the "prose heuristics tightened until they produce false failures on legitimate text" failure mode the execution prompt warned against.
> 2. `agents/debt_agent.py`'s no-debts path never set `allocated_amount` (left it `None`), but `roadmap.allocation["debt_extra_payment"]` is always a concrete `0.0`, never `None` — check 3 correctly flagged this as a real mismatch. Fixed the agent (not the check): `None` is reserved for agents that never allocate at all (spending, budget); debt is an allocating agent that happens to allocate `$0` here, and that distinction matters to the validator.
>
> **A latent test-isolation flaw caught before it could mask a real bug:** `test_validation.py`'s helper originally built `specialist_results` via a blocklist ("everything except `roadmap_result`"), but LangGraph's `invoke()` returns the *full* merged state — `profile`/`snapshot`/`findings`/`risks`/`trends`/`validation_result` were all leaking in as bogus pseudo-entries. Every check happened to degrade safely against them (`dict.get()` on a `Finding`/`Risk`/etc. returns `None`, so no crash, no false violation) — which meant the tests were passing without that being proof the checks worked on real data. Replaced with an explicit allowlist of the five actual specialist-result keys.
>
> **Graph extension beyond Phase 3's original signature:** `agents/graph.py`'s `GraphState`, `run_graph()`, and `run_pipeline_direct()` now also carry `trends` — Phase 3 didn't need it, but `validate_consistency()` requires it (checks 5 and 8), so it has to flow through the graph. This is a required extension of Phase 3's own interface for Phase 4's stated dependency, not scope creep into Phase 3's territory.

---

## Phase 5 — Coach Synthesis

**Entry criterion:** Phase 4 marked done (needs validated specialist results).

A lightweight top-level synthesis, not a new subsystem — it does not calculate or allocate money.

**Tasks**
- `synthesize_coach_summary(snapshot, trends, findings, risks, roadmap, specialist_results) -> CoachSummary` in `utils/coach.py`, producing the fixed section order: Overall Financial Health, What Changed, Critical Risks, Important Patterns, Positive Changes, Your Priorities (max 3 `action_id`s), Actions This Week / This Month / Next 90 Days / Long-Term, Assumptions and Data Limitations.
- Every list holds IDs (`trend_id`/`finding_id`/`risk_id`/`action_id`) — no freestanding new claims.
- Action bucketing into week/month/90-day/long-term is driven by each action's `urgency` field.
- The Assumptions and Data Limitations section surfaces `snapshot.data_quality_flags`, so limited-confidence data is disclosed rather than silently ignored.
- Wire as the final graph stage, after the consistency validator.

**Standing constraint:** this step ranks and selects from what Phases 2-4 already produced. It does not invent a risk, finding, or number, and it does not implement trade-off suppression beyond urgency ranking — that refinement is Important-tier, not this phase's job.

**Exit gate — all must pass**
- [x] `top_priorities` never exceeds 3 entries and every entry resolves to a real `action_id`
- [x] Every other list's entries resolve to a real `Trend`/`Finding`/`Risk`/`action_id`
- [x] Actions are bucketed by their `urgency` value, verified against a fixture with mixed urgencies
- [x] `data_quality_flags` present in a fixture appear in the Assumptions and Data Limitations section
- [x] The section order is fixed and matches the spec above in a rendered example
- [ ] PR merged to `main`, tagged `phase5-done` — pending explicit request

> **Caveat carried over, unchanged:** "passes in CI" still means "passes locally via `pytest`" — no CI pipeline exists yet.
>
> **A real gap caught in my own test, not a code bug:** the first pass at "top_priorities never exceeds 3" only ever ran against fixtures that happen to produce ≤3 actions (verified by inspection: max was 3, across every committed fixture) — so the cap had never actually been exercised as a truncation. Added a dedicated test with three goals forced into one profile (5 total actions) to prove the 4th+ action is genuinely excluded, not just coincidentally absent.
>
> **A naming gap flagged rather than silently resolved:** `Urgency` (`utils/contracts.py`) has exactly four values — `immediate`, `this_month`, `next_90_days`, `long_term` — but `CoachSummary` has four action buckets named `this_week`/`this_month`/`next_90_days`/`long_term`. There is no `this_week` urgency value. The shapes line up 4-to-4, so `immediate -> actions_this_week` is the only mapping that doesn't invent a fifth value or leave a bucket permanently empty; this is documented explicitly in `utils/coach.py`'s module docstring as a naming choice, not new data. Worth a second look if the urgency vocabulary ever changes.
>
> **`specialist_results` is accepted but not consumed:** matches the signature specified in `Architecture Plan.md`, Component 4, but every section of `CoachSummary` is fully derivable from `snapshot`/`trends`/`findings`/`risks`/`roadmap` alone — inventing a use for the parameter would itself violate this phase's "no freestanding new claims" rule, so it is documented as unused rather than silently dropped from the signature or given a manufactured purpose.

---

## Phase 6 — Golden Fixture Freeze

**Entry criterion:** Phase 5 marked done — the full deterministic pipeline (snapshot → trends → findings → risks → roadmap → specialists → validation → coach summary) now produces every output a golden fixture needs to capture.

This phase exists because expected outputs cannot be authored earlier: the expected snapshot needs Phase 1, expected trends/findings/risks need Phase 2, expected allocation needs Phase 3, and expected top priorities need Phase 5. It is placed here, before Reports and Integration, so it catches regressions **during** the remaining work rather than after it.

**Tasks**
- For each of the three golden input profiles from Phase 0 (stable high surplus; negative cashflow; income drop with rising dining), run the full pipeline.
- **Manually review every output for correctness before freezing.** Freezing unreviewed output enshrines whatever bug exists at that moment — this review is the point of the phase, not a formality. Have a second person check the negative-cashflow case specifically.
- Freeze the reviewed results into `fixtures/golden/*.expected.json`, capturing: `snapshot.metrics`, `Trend[]`, `Finding[]` (id + severity + urgency + confidence + fact_or_inference), `Risk[]`, `roadmap.allocation`, `roadmap.actions[].action_id` + `priority`, and `coach_summary.top_priorities`.
- Add `tests/test_golden.py` asserting exact equality on all numeric and enum fields, ignoring narrative prose (per `Review.md` item 27: "Narrative wording may vary, but no amount, priority, severity, or factual claim may drift").

**Exit gate — all must pass**
- [ ] All three golden fixtures have reviewed, committed `*.expected.json` files
- [ ] `tests/test_golden.py` passes
- [ ] A deliberate one-cent change to any allocation value fails the golden test
- [ ] A deliberate severity change on any finding fails the golden test
- [ ] A reworded narrative does **not** fail the golden test
- [ ] The negative-cashflow expected output was reviewed and signed off by a second person
- [ ] PR merged to `main`, tagged `phase6-done`

---

## Phase 7 — Reports & Tracker

**Entry criterion:** Phase 6 marked done.

**Tasks**
- `build_report(profile, snapshot, trends, findings, risks, roadmap, coach_summary) -> ReportPackage` and `build_tracker(roadmap, months=12)` in `utils/reporting.py`.
- The report includes profile inputs, health metrics, trends, findings, risks (with severity and urgency), roadmap actions, the Coach Summary's fixed section order, assumptions, data-quality limitations, and the educational-advice limitation.
- `buffer_reserved` is labeled distinctly from the distributed allocation amounts (`debt_extra_payment` / `goal_contributions` / `savings_contribution`) — it is a planning constraint, not a monthly transfer, and must not be summed into any "money in motion" total.

**Exit gate — all must pass**
- [ ] Exported values match the source snapshot and roadmap exactly (no independently recalculated numbers)
- [ ] A report with no debts or goals still renders
- [ ] Tracker totals do not exceed the roadmap's distributed allocation (excluding `buffer_reserved`)
- [ ] Report renders the Coach Summary's fixed section order
- [ ] Every cited `finding_id`/`risk_id`/`trend_id`/`action_id` resolves
- [ ] `buffer_reserved` is visually and semantically distinct from distributed amounts
- [ ] Golden tests from Phase 6 still pass
- [ ] PR merged to `main`, tagged `phase7-done`

---

## Phase 8 — Streamlit Integration

**Entry criterion:** Phase 7 marked done.

**Tasks**
- Wire the full screen sequence in `app.py`: upload/questionnaire → category review → income/savings/debts/goals/assumptions confirmation → analysis (Overview showing the Coach Summary, Health & Roadmap, specialist tabs, chat) → scenario preview/rerun → report/tracker download.
- Session-state adaptor: build the dict `{transactions, monthly_income, current_savings, debts, goals, monthly_surplus: gross_surplus, allocatable_surplus, extra_debt_payment: allocation["debt_extra_payment"], savings_contribution: allocation["savings_contribution"], goal_contributions: allocation["goal_contributions"]}` from the confirmed profile/snapshot/roadmap, and pass it as the LangGraph state consumed by the specialist nodes.
- Wire the Overview tab to invoke the full graph (Stage 1 through the consistency validator and Coach synthesis); wire specialist tabs and chat (`route_chat`) to reuse the same graph nodes rather than a second orchestration path.
- Surface `ValidationResult.fallback_used` in the UI when a narrative was replaced — disclosed, not hidden.

**Standing constraint:** the UI is the only writer to `st.session_state`; domain components (including graph nodes) stay pure and return values rather than mutating shared state.

**Exit gate — all must pass**
- [ ] App does not run analysis before required inputs validate
- [ ] Editing a review category changes the resulting spending/budget output
- [ ] Download buttons work in offline mode (no OpenRouter key)
- [ ] Specialist tabs and chat work with the generated profile context
- [ ] Specialist tabs and chat are served through the same LangGraph nodes as the overview (consistent output across tabs)
- [ ] Overview tab renders the Coach Summary, not a concatenation of five agent outputs
- [ ] A triggered validator fallback is visible in the UI
- [ ] One full end-to-end sample path works offline
- [ ] Golden tests from Phase 6 still pass
- [ ] PR merged to `main`, tagged `phase8-done`

---

## Phase 9 — Validation, Property Tests & Regression

**Entry criterion:** Phase 8 marked done.

**Tasks**
- Exercise and fix these **eleven distinct edge-case paths**:
  1. Invalid input (fails `validate_profile`)
  2. Zero debts
  3. Exactly one debt
  4. Multiple debts (exercises avalanche ordering)
  5. Zero goals
  6. Unknown/unmatched transaction category
  7. Negative cashflow (`gross_surplus <= 0`)
  8. Zero income
  9. Partial trailing month
  10. Duplicate transactions
  11. Corrupted `SpecialistResult` (validator catches it and falls back)
- **Property-based tests** (`hypothesis`) over randomly generated valid `FinancialProfile`s asserting:
  - `sum(distributed allocation) <= allocatable_surplus` always
  - `allocatable_surplus >= 0` always
  - no debt balance goes negative in any payoff schedule
  - payoff month count is monotonically non-increasing as extra payment increases
  - `gross_surplus <= 0` implies every distributed allocation is `0`
- Fill any test gaps found while doing this. Do not add features in this phase.

**Exit gate — all must pass**
- [ ] All eleven edge-case paths run without error or crash
- [ ] All five property-based tests pass over at least 200 generated profiles each
- [ ] Golden tests from Phase 6 still pass
- [ ] No regressions in Phases 0–8 gate items (spot re-check)
- [ ] Full test suite green in CI
- [ ] Tagged `phase9-done`

---

## Phase 10 — UX & Narrative Polish

**Entry criterion:** Phase 9 marked done.

**Tasks**
- Improve review-screen clarity, roadmap readability, Coach Summary presentation, and export formatting.
- **De-scope trigger:** if time is tight, drop PDF-parsing improvements and LLM narrative polish first — never category review, the health snapshot, the deterministic roadmap, the consistency validator, golden tests, or CSV/Markdown downloads.

**Exit gate**
- [ ] Review, roadmap, Coach Summary, and export screens are demo-ready
- [ ] Golden tests and full suite still pass
- [ ] Tagged `phase10-done`

---

## Phase 11 — Demo Rehearsal & Release Gate (final)

**Entry criterion:** Phase 10 marked done.

**Tasks / final gate — run this exact checklist twice, live, without manual code edits between runs**
- [ ] **1.** Load sample transactions
- [ ] **2.** Confirm an unknown category can be changed before analysis
- [ ] **3.** Enter a debt, a goal, and a minimum buffer
- [ ] **4.** Run health calculation; score and risks are plausible and explained
- [ ] **5.** Change an assumption; the scenario changes without corrupting the base result
- [ ] **6.** Download report and tracker; exported totals match the rendered plan
- [ ] **7.** Repeat the full journey in offline mode with no OpenRouter key
- [ ] **8.** Confirm the Debt Analyzer, Goal Planner, and Savings Strategist tabs quote the exact same dollar figures as `roadmap.allocation`, and that those sum to no more than `allocatable_surplus`
- [ ] **9.** Load the negative-cashflow golden fixture; verify no specialist proposes a positive extra-payment or investment, and the roadmap reads as a cashflow-recovery plan
- [ ] **10.** Load the income-drop-plus-rising-dining golden fixture; verify the Coach Summary ranks the income drop as critical/immediate and cites the right `Finding`/`Trend` IDs
- [ ] **11.** Confirm the Overview shows one coherent Coach Summary, not five concatenated specialist blocks
- [ ] **12.** Confirm a data-quality-limited fixture discloses its limitation in the Coach Summary
- [ ] **13.** `pytest` green: contracts, unit, golden, and property-based suites all pass

**MVP 1 is "done" only when this gate is fully green.** At that point — and only then — MVP 2 may begin.
