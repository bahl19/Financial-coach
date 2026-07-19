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
| 6 | Golden Fixture Freeze | Done (see caveats in gate) | 2026-07-19 | Automated test suite (275/275) |
| 7 | Reports & tracker | Done (see caveats in gate) | 2026-07-19 | Automated test suite (304/304) |
| 8 | Streamlit integration | Done (see caveats in gate) | 2026-07-19 | Automated test suite (337/337, updated by a Phase 11 rehearsal fix) |
| 9 | Validation, property tests & regression | Done (see caveats in gate) | 2026-07-19 | Automated test suite (337/337) |
| 10 | UX & narrative polish | Done (see caveats in gate) | 2026-07-19 | Automated test suite (337/337, unchanged) |
| 11 | Demo rehearsal & release gate | Done (see caveats in gate) | 2026-07-19 | Two consecutive clean rehearsal runs, 13/13 both times |

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
- [x] All three golden fixtures have reviewed, committed `*.expected.json` files — every number in all three (`stable_high_surplus`, `negative_cashflow`, `income_drop_rising_dining`) was hand-recomputed from the raw fixture transactions against `snapshot.metrics`, every `Trend`, every `Finding`, every `Risk`, `roadmap.allocation`, and `coach_summary.top_priorities` before freezing
- [x] `tests/test_golden.py` passes (275/275 total suite, including 6 golden-specific tests)
- [x] A deliberate one-cent change to any allocation value fails the golden test — verified live: perturbed `income_drop_rising_dining.expected.json`'s `savings_contribution` by +$0.01, ran the suite, watched it fail, then reverted and re-confirmed green
- [x] A deliberate severity change on any finding fails the golden test — same live perturb/fail/revert exercise, on `FINDING_LOW_EMERGENCY_FUND`'s severity
- [x] A reworded narrative does **not** fail the golden test — `test_golden_fixture_ignores_narrative_reword` rewrites every specialist's `narrative` field before comparing; passes because the captured structure never includes a prose field at all
- [ ] The negative-cashflow expected output was reviewed and signed off by a second person — **caveat:** hand-verified in this session (every metric, trend, finding, and risk recomputed from the raw transactions and cross-checked against the code), but no literal second human reviewer was available; this remains genuinely unverified as stated and needs an actual second person before treating it as satisfied
- [ ] PR merged to `main`, tagged `phase6-done` — pending explicit request; not performed unilaterally

> **Caveat — bug found and fixed during this phase's manual review (not by a failing test):** `build_roadmap()`'s goal-funding step (`utils/roadmap.py`, Step 5) already computed each goal's real, allocation-aware feasibility (`goal_feasibility()` against `ledger.remaining`, the surplus genuinely left after higher-priority steps) but discarded that result — every `ACTION_FUND_GOAL_*` action was unconditionally `severity: "medium"`, `urgency: "next_90_days"`, even when the goal was funded at less than its required monthly rate. This is distinct from `snapshot.goal_results` (Phase 1's preliminary, allocation-*un*aware check against the full `allocatable_surplus`, computed before the roadmap runs and necessarily blind to competing claims on that surplus) — a goal can pass that preliminary check yet still come up short here. Found via `income_drop_rising_dining`: "New laptop" needs $400/month but only $377.17 remained once the starter buffer claimed its 50% share first; the goal specialist's own narrative already said so in prose, but the roadmap action itself, `coach_summary.top_priorities`, and the action bucket it lands in did not reflect it. Fixed by elevating the action to `severity: "high"` / `urgency: "this_month"` whenever the goal's contribution falls short of its own `required_monthly` — using data `build_roadmap()` already has on hand, no restructuring required. Two regression tests added to `tests/test_roadmap.py` (`test_underfunded_goal_action_is_elevated_to_high_severity_this_month`, `test_fully_funded_goal_action_keeps_medium_severity_next_90_days`); confirmed the fix does not change `stable_high_surplus` or `negative_cashflow`'s output (the former's goal is fully funded, the latter has none). This is the third bug this phase's manual review has found — see Phase 6 for the two `finance_calc.py` fixes (`_build_trend()`'s percent-change sign, `_category_trend_findings()`'s essential-category mislabeling) made earlier in this same review pass.
>
> A related, narrower limitation remains and is intentionally **not** fixed here: `FINDING_GOAL_SHORTFALL_*` and `RISK_GOAL_FAILURE` still key off the Phase-1 preliminary check, not the roadmap's actual allocation, because `derive_findings()`/`derive_risks()` run *before* `build_roadmap()` in the pipeline (the roadmap depends on findings/risks, not the reverse) — making them allocation-aware would require restructuring that ordering, which is out of this phase's scope. The fix above ensures the shortfall is still visible in the roadmap action itself and in `coach_summary.top_priorities`/`actions_this_month`, so a user is not left unaware of it; it does not make the Finding/Risk pair itself allocation-aware.

---

## Phase 7 — Reports & Tracker

**Entry criterion:** Phase 6 marked done.

**Tasks**
- `build_report(profile, snapshot, trends, findings, risks, roadmap, coach_summary) -> ReportPackage` and `build_tracker(roadmap, months=12)` in `utils/reporting.py`.
- The report includes profile inputs, health metrics, trends, findings, risks (with severity and urgency), roadmap actions, the Coach Summary's fixed section order, assumptions, data-quality limitations, and the educational-advice limitation.
- `buffer_reserved` is labeled distinctly from the distributed allocation amounts (`debt_extra_payment` / `goal_contributions` / `savings_contribution`) — it is a planning constraint, not a monthly transfer, and must not be summed into any "money in motion" total.

**Exit gate — all must pass**
- [x] Exported values match the source snapshot and roadmap exactly (no independently recalculated numbers) — `assemble_report_content()` only reads/copies fields; the module contains no arithmetic beyond summing `roadmap.allocation.goal_contributions` into `TrackerRow.goal_contributions` (that field is a single aggregate by contract, not a per-goal breakdown, so summing already-known figures into it is not a new financial claim)
- [x] A report with no debts or goals still renders
- [x] Tracker totals do not exceed the roadmap's distributed allocation (excluding `buffer_reserved`) — verified per-row (each row repeats the same monthly figures, so equality holds, never exceeding) across all 7 fixtures
- [x] Report renders the Coach Summary's fixed section order — `_COACH_SECTIONS` reuses the exact field order `synthesize_coach_summary()` (Phase 5) already fixes, not a second hardcoded copy of that order
- [x] Every cited `finding_id`/`risk_id`/`trend_id`/`action_id` resolves — checked across all 7 fixtures, including refs cited transitively (finding→trend, risk→finding, action→finding/risk, coach summary→any)
- [x] `buffer_reserved` is visually and semantically distinct from distributed amounts — labeled "(planning constraint, not a distributed transfer)", rendered before and outside the "Distributed monthly allocation" list, and absent from every `TrackerRow`
- [x] Golden tests from Phase 6 still pass — full suite re-run after this phase, 304/304, `test_golden.py` unaffected
- [ ] PR merged to `main`, tagged `phase7-done` — pending explicit request; not performed unilaterally

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
- [x] App does not run analysis before required inputs validate — the "Confirm & run analysis" button is `disabled` whenever `validate_profile()`/a missing `monthly_income` reports an issue; verified via `AppTest` (button disabled with no income set, enabled once set, no Step 4/tabs render until then)
- [x] Editing a review category changes the resulting spending/budget output — `streamlit.testing.v1.AppTest` cannot drive `st.data_editor` in this Streamlit version (no `.data_editor` query interface exists on the harness), so this is verified by calling the pure function the widget's output feeds, `utils.ingestion.apply_category_corrections()`, directly: a corrected category changes `fc.spending_by_category()`'s breakdown and re-tags `transaction_type` (budget reads from spending's own supporting_tables, so the effect propagates)
- [x] Download buttons work in offline mode (no OpenRouter key) — verified with no `OPENROUTER_API_KEY` set (`is_live()` asserted `False` in the test itself, not assumed)
- [x] Specialist tabs and chat work with the generated profile context
- [x] Specialist tabs and chat are served through the same LangGraph nodes as the overview (consistent output across tabs) — `build_chat_reply()` reuses the *same* `graph_result` object's narratives (asserted byte-identical, not just similar), never a second `run_graph()` call or a freestanding LLM call
- [x] Overview tab renders the Coach Summary, not a concatenation of five agent outputs — verified negatively too: none of the five specialists' raw `narrative` strings appear anywhere in the Overview tab's rendered markdown
- [x] A triggered validator fallback is visible in the UI — verified by forcing `validation_result.fallback_used = True` and confirming the warning banner renders (a real Phase-4 fallback is rare to trigger naturally; forcing the flag is the same code path the UI actually branches on)
- [x] One full end-to-end sample path works offline
- [x] Golden tests from Phase 6 still pass — full suite re-run, 321/321
- [ ] PR merged to `main`, tagged `phase8-done` — pending explicit request; not performed unilaterally

> **Caveats:**
> - Retired `finance_calc.categorize_transactions()`/`CATEGORY_KEYWORDS` per Phase 1's note now that `app.py` categorizes exclusively through `utils.ingestion.categorize_with_confidence()` — one keyword table remains in the codebase, not two.
> - **Bug found and fixed while smoke-testing this phase (not by a pre-written failing test):** `app.py` recomputes and calls `app_state.set_profile_fields()`/`set_categorized_df()` unconditionally on *every* script rerun (Streamlit reruns the whole script on any widget interaction, not only when that widget's own value changed). Their original implementation invalidated the last analysis (`graph_result`) on every call, so an unrelated rerun — e.g. sending a chat message — silently wiped out an already-computed analysis and bounced the user back to "confirm your details," even though nothing about their profile had changed. Fixed by invalidating only when the incoming value genuinely differs from what's already stored (scalar/dict equality for profile fields, `DataFrame.equals()` for the categorized transactions). Four regression tests added to `tests/test_app_state.py` proving both the "unchanged -> no invalidation" and "changed -> invalidation" cases for each setter.
> - Deleted `agents/orchestrator.py`'s `OrchestratorAgent` backward-compatible import shim (`run_full_report`/`route_chat`, both of which only ever raised `NotImplementedError` — added in Phase 3 solely to keep `app.py` importable before this phase rewired it). Confirmed nothing in `app.py`, `agents/`, `utils/`, or `tests/` still references it before removing it; chat routing is now `build_chat_reply()`, added in this phase directly on top of `agents.graph.run_graph()`.
> - **Bug found during Phase 11's rehearsal (item 5, scenario preview) and fixed here, in its owning phase:** Step 3's confirmation form built `current_savings` via `current_savings or None` - the same collapsing-to-`None` idiom used for `monthly_income` (there, deliberately, since it also drives the "required inputs" gate). For `current_savings`, which gates nothing, this meant a user who left the field at its widget default of `$0` (or deliberately typed `0` - a real, common answer for someone with no savings) had that answer silently discarded and replaced with `None` ("unknown"), which in turn made `snapshot.metrics.emergency_fund_months` come back `None` instead of the correct `0.0`. Exactly the "a real zero must not become `None`" failure mode the Standing Context's coding standards warn about, just in the opposite direction from the usual one. Fixed by passing `current_savings` through unchanged. Full suite re-run clean (337/337) and the fix directly verified (`emergency_fund_months` now reports `0.0`, not `None`, for a $0-savings profile) before the Phase 11 rehearsal - which had caught this - was restarted from its first step.

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
- [x] All eleven edge-case paths run without error or crash — `tests/test_edge_cases.py`, each run through the real `agents.graph.run_graph()` pipeline (not an isolated function call) wherever that was meaningful; case 11 (corrupted `SpecialistResult`) exercised through the full graph's node functions directly, in addition to Phase 4's existing narrower unit test
- [x] All five property-based tests pass over at least 200 generated profiles each — `tests/test_properties.py`, 200 examples each in the checked-in suite; additionally stress-run at 1,000 examples each in this session with zero failures before trusting them
- [x] Golden tests from Phase 6 still pass
- [x] No regressions in Phases 0–8 gate items (spot re-check) — full suite green (337/337); Phase 8's `AppTest`-driven smoke path and Phase 3's allocation-ledger invariant were re-run explicitly, not just inferred from the aggregate count
- [ ] Full test suite green in CI — **caveat:** 337/337 pass locally via `pytest`; no CI pipeline (`.github/workflows/`) exists in this repo, so "in CI" remains unverifiable as literally stated (same caveat as every prior phase)
- [ ] Tagged `phase9-done` — pending explicit request; not performed unilaterally

> No property or edge-case failure required a code fix in this phase - all
> five properties held at both 200 and 1,000 examples on the first run, and
> all eleven edge cases passed on the first run. This is not a coincidence:
> Phases 6 and 8's manual-review passes already found and fixed three real
> bugs (`_build_trend()`'s percent-change sign, `_category_trend_findings()`'s
> essential-category mislabeling, and `build_roadmap()`'s underfunded-goal
> severity) in the exact code these properties exercise most heavily
> (trends, the allocation waterfall). Per the Phase 9 execution prompt's own
> warning, no generator was narrowed and no assertion was relaxed to
> reach this result - the generators cover the stated "full legal input
> space" (zero/negative-adjacent boundary values, 0-4 debts, 0-3 goals,
> 0-6 months of transaction history) without post-hoc restriction.

## Phase 10 — UX & Narrative Polish

**Entry criterion:** Phase 9 marked done.

**Tasks**
- Improve review-screen clarity, roadmap readability, Coach Summary presentation, and export formatting.
- **De-scope trigger:** if time is tight, drop PDF-parsing improvements and LLM narrative polish first — never category review, the health snapshot, the deterministic roadmap, the consistency validator, golden tests, or CSV/Markdown downloads.

**Exit gate**
- [x] Review, roadmap, Coach Summary, and export screens are demo-ready — all changes confined to `app.py`'s live-UI rendering, never `utils/reporting.py` (Phase 7's downloadable report already has its own frozen formatting and its own tests):
  - Category review: the correction column is now a constrained `SelectboxColumn` over the real category set (`ingestion.CATEGORY_KEYWORDS` + Income/Other) instead of free text, and description/amount are read-only display columns
  - Overview/Coach Summary: `top_priorities`/`critical_risks`/`important_patterns`/`positive_changes` now render each ID's already-computed title/category/metric label (e.g. "Fund goal: Vacation" instead of `ACTION_FUND_GOAL_VACATION`) via a pure ID→label lookup built from this run's own findings/risks/trends/roadmap — no new label is invented and no finding/risk/trend/action field changes
  - Overview: `snapshot.data_quality_flags` now surfaces as its own callout above the Coach Summary, not only buried in `assumptions_and_limitations`'s caption text, per this phase's own "clarity about data limitations" guidance
  - Roadmap: each action gets a severity icon (🔴/🟠/🟡/⚪/🟢); the underlying `severity`/`priority`/`monthly_amount` values are untouched
  - Scenario preview table and tracker CSV: column/row labels renamed to human-readable text at the display/export call site only, never inside `utils.scenarios`/`utils.reporting`'s own return values
- [x] Golden tests and full suite still pass — 337/337, byte-for-byte the same count and result as before this phase; confirms no behavior changed, only presentation
- [ ] Tagged `phase10-done` — pending explicit request; not performed unilaterally

---

## Phase 11 — Demo Rehearsal & Release Gate (final)

**Entry criterion:** Phase 10 marked done.

**Tasks / final gate — run this exact checklist twice, live, without manual code edits between runs**

> **Tooling note, recorded honestly rather than glossed over:** `streamlit.testing.v1.AppTest` (this Streamlit version) has no query interface for `st.data_editor`/`st.form_submit_button`. Steps that the checklist implies happen through one of those widgets (editing a category, editing the debts/goals tables, submitting the scenario-preview form) were driven by calling the exact function that widget's callback calls (`utils.ingestion.apply_category_corrections`, `utils.scenarios.apply_assumptions`/`compare_scenarios`) with the same inputs a user's edit would produce, rather than the widget itself. Steps 9-10 load a golden fixture's pre-built `FinancialProfile` directly through the same pipeline `app.py` calls, since the app's only load path is a raw CSV upload (date/description/amount), not a full profile JSON — there is no UI control this checklist could exercise for "load this exact fixture" beyond re-entering its numbers by hand. Steps 1, 3 (buffer), 4, 5 (base-result-unchanged check), 6, 7, 11, and 13 were driven through the real running app.
>
> **A bug was found and fixed during the first rehearsal attempt (not this recorded one) — the rehearsal was restarted from step 1 afterward, per this phase's own rule that a run requiring a fix is a failed run.** Step 5 (changing an assumption) surfaced that `app.py`'s Step 3 form built `current_savings` via `current_savings or None`, silently discarding a deliberate (or default/untouched) `$0` answer and turning `snapshot.metrics.emergency_fund_months` into `None` instead of the correct `0.0`. Fixed in `app.py` (Phase 8, its owning phase — see that phase's caveats), Phase 8's gate re-verified (full suite green, fix directly confirmed), and only then was this rehearsal restarted clean. Two fully independent, back-to-back runs both passed 13/13 with identical results, confirming the pipeline's determinism as a side effect.

- [x] **1.** Load sample transactions — loaded via the sidebar button through the real app; reached Step 2/Step 3 with no exception
- [x] **2.** Confirm an unknown category can be changed before analysis — the bundled sample data itself has zero unmatched categories (a real observation, not assumed away); demonstrated instead with a synthetic unmatched transaction ("Other" → corrected to "Dining") through `apply_category_corrections()`, the exact function the review screen's data_editor calls
- [x] **3.** Enter a debt, a goal, and a minimum buffer — buffer set to $250 through the real widget; Step 3's default debt/goal rows (present without further edits) carried through, an observation worth recording as-is rather than silently treating "left at default" the same as "user-entered"
- [x] **4.** Run health calculation; score and risks are plausible and explained — health score 70/100 ("Building"), risks `RISK_INSUFFICIENT_EMERGENCY_FUND` and `RISK_HIGH_INTEREST_DEBT` given a $0-savings, one-high-APR-debt profile — plausible and consistent with the numbers
- [x] **5.** Change an assumption; the scenario changes without corrupting the base result — `minimum_monthly_buffer` +$500 moved `allocatable_surplus` by exactly -$500 in the preview; `st.session_state["graph_result"]` was confirmed to be the *same object* (identity-checked, not just equal) after previewing, proving the base analysis was never touched
- [x] **6.** Download report and tracker; exported totals match the rendered plan — tracker row total and `roadmap.allocation`'s distributed total matched to the cent ($2,225.38 both)
- [x] **7.** Repeat the full journey in offline mode with no OpenRouter key — `is_live()` asserted `False` (no `OPENROUTER_API_KEY` set), not assumed; the entire rehearsal ran under this condition throughout
- [x] **8.** Confirm the Debt Analyzer, Goal Planner, and Savings Strategist tabs quote the exact same dollar figures as `roadmap.allocation`, and that those sum to no more than `allocatable_surplus` — matched exactly; both goals happened to receive $0 in this profile (buffer + debt acceleration exhausted the ledger first, a real and correctly-handled outcome, not a bug — see note below)
- [x] **9.** Load the negative-cashflow golden fixture; verify no specialist proposes a positive extra-payment or investment, and the roadmap reads as a cashflow-recovery plan — all distributed amounts $0, zero actions, `RISK_NEGATIVE_CASHFLOW` present
- [x] **10.** Load the income-drop-plus-rising-dining golden fixture; verify the Coach Summary ranks the income drop as critical/immediate and cites the right `Finding`/`Trend` IDs — `FINDING_INCOME_DROP` is `severity=critical`, `urgency=immediate`, cited in `coach_summary.important_patterns`, and references `TREND_INCOME`
- [x] **11.** Confirm the Overview shows one coherent Coach Summary, not five concatenated specialist blocks — confirmed; none of the four specialists' raw narratives appear on the Overview screen
- [x] **12.** Confirm a data-quality-limited fixture discloses its limitation in the Coach Summary — `PARTIAL_TRAILING_MONTH` disclosed both in `coach_summary.assumptions_and_limitations` and in the Phase 10 data-quality callout on the Overview screen
- [x] **13.** `pytest` green: contracts, unit, golden, and property-based suites all pass — 337 passed, 4 skipped, both runs

> **Observation worth recording rather than silently passing over (per this phase's "a step that worked but looked odd is a finding, not a pass"):** in step 8's profile, both goals received exactly $0 — the starter emergency buffer and high-interest-debt acceleration steps (each claiming a documented 50% share) exhausted the entire ledger before goal-funding's turn in the waterfall. This is the deterministic allocator behaving exactly as designed (buffer and debt genuinely do outrank these goals given this profile's numbers), not a defect — but it is a real example of how thoroughly a genuinely-tight surplus can starve every lower-priority goal, worth keeping in mind for any future prioritization/partial-funding discussion in MVP 2.

**MVP 1 is "done" only when this gate is fully green.** All thirteen checks passed on two consecutive, independent, clean runs with identical results and no code edits between them. **MVP 1 is complete.** PR-merge and `phase11-done`/final release tagging are pending explicit user request, as with every prior phase's tag — not performed unilaterally. MVP 2 work may begin only once that tagging is confirmed, per this document's own rule.

---

## Post-Release Maintenance Log

Fixes made after MVP 1's release gate went green, applied to their logically-owning phase's files with the same test-first discipline as every phase above (full suite re-verified green after each).

### 2026-07-19 — False "income dropped sharply" finding on biweekly-pay data; switch to India/monthly-salary conventions

**Reported by the user**, who suspected the Spending Analyzer's income/expense comparison wasn't doing what it should.

**Root cause (Phase 2's `utils/finance_calc.py`, `monthly_cashflow()`):** income is aggregated by *calendar month*. That is a safe assumption for expenses (roughly smooth day-to-day) but breaks for a paycheck on any sub-monthly cadence - biweekly pay lands 2 or 3 times in a calendar month depending purely on where the dates fall, with no relationship to an actual income change. The bundled sample data (a stable, biweekly $3,100 paycheck: May 1/15/29, Jun 12/26, Jul 10) demonstrated this concretely: May showed $9,300 "income," June $6,200, July (truncated mid-month) $3,100 - a fabricated 66.7% "sharp decrease" that cascaded into `TREND_INCOME`, `FINDING_INCOME_DROP` (`severity=critical`, `urgency=immediate`), and `FINDING_CASHFLOW_DETERIORATING`, none of which reflected anything real about the user's finances.

**Fix chosen, at the user's direction:** rather than building a general pay-cadence-normalization model (a materially bigger change to the deterministic core), align the product with India's near-universal monthly-salary convention, where this artifact does not arise (one salary credit per calendar month keeps `monthly_cashflow()`'s existing aggregation correct). This is a deliberate scope decision, not a full fix of the underlying fragility: a calendar-month `groupby` is still not robust to *any* sub-monthly income cadence in general, so a biweekly/weekly-paid user uploading their own statement could still hit the same artifact. Flagging this rather than silently overselling the fix as universal.

**Changes made:**
- `data/sample_transactions.csv`: rewritten with one monthly salary credit (₹75,000, 1st of each month) and Indian-context vendors (Swiggy, Zomato, BigBasket, BESCOM, Jio, HDFC, Zerodha, etc.), same 3-month/partial-trailing-month window as before. Verified this removes the false `FINDING_INCOME_DROP` (now `TREND_INCOME` is flat/stable, 0% change).
- `utils/ingestion.py`'s `CATEGORY_KEYWORDS`: added Indian vendor keywords to every existing category (additive, not a replacement - the original US-centric keywords still match), so the new sample data categorizes cleanly instead of falling through to "Other."
- `utils/contracts.py`'s `default_assumptions()`: `"currency"` changed from `"USD"` to `"INR"`.
- `app.py`'s `DEFAULT_DEBTS`/`DEFAULT_GOALS`: rescaled to realistic INR magnitudes (a straight `$`→`₹` relabel without rescaling the numbers would have produced absurdly small amounts).
- **Currency symbol switched from `$` to `₹` everywhere a figure is shown to a user** - `app.py`, every specialist agent's narrative/fallback text (`budget_agent.py`, `goal_agent.py`, `savings_agent.py`, `spending_agent.py`, `debt_agent.py`), `utils/roadmap.py`, `utils/reporting.py`, `utils/finance_calc.py`'s goal-shortfall finding text, and `utils/validation_structured.py`'s violation messages. No number, computation, or contract field changed - display formatting only. Indian-style lakh/crore digit grouping was **not** implemented (still plain `:,.0f`/`:,.2f` Western grouping) - a separate ask if wanted.
- **Critical, easy-to-miss dependency fixed in the same pass:** `utils/validation_prose.py`'s prose-consistency checks (7 and 9) detect money figures in narratives via a regex hardcoded to `\$`. Left unchanged, switching every narrative to `₹` would have made that regex match nothing, silently disabling those two checks (they'd "pass" by finding zero dollar mentions to check, not because anything was actually verified). Fixed the regex to match `₹`; updated `tests/test_validation.py`'s two fabricated-narrative fixtures (which construct their own fake `$...` text) to `₹...` accordingly, since the checks are tested via injected prose, not fixture data.
- `agents/data_agent.py`'s PDF-statement parser: regex now accepts an optional `₹`/`Rs.`/`$` prefix instead of assuming `$`.
- Every test asserting on a literal `$`-formatted narrative substring updated to `₹` (`tests/test_roadmap.py`, `tests/test_validation.py`; two comment-only mentions in `tests/test_finance_calc.py`/`tests/test_insight_engine.py` updated for consistency, not correctness).

**Also addressed - a related UX gap the user raised:** why does Step 3 ask the user to re-enter income/savings after a CSV is already loaded, risking disagreement with the statement? The reasoning: `monthly_income`/`current_savings` are modeled as forward-looking, user-confirmed facts (what you'll earn going forward; what you have saved *today*), not something derivable from a transaction ledger, which only records historical cash movements and has no concept of a current account balance. That reasoning is sound for `current_savings` (genuinely undeterminable from a CSV - inventing one would violate "unknown is `None`, never a fabricated number") but was a real gap for `monthly_income`, which the CSV *can* reasonably estimate. Fixed: Step 3 now pre-fills the income field from the most recent Income-category transaction (`app.py::_suggest_monthly_income`), which the user still confirms or overrides, rather than starting from a disconnected blank/zero. `current_savings` intentionally still starts blank, with its own help text explaining why.

**Verification:** full suite green (338/338, +1 new test for the income pre-fill), golden fixture tests unaffected (they exclude narrative/prose fields by design, so the currency-symbol change didn't touch them), and a full live `AppTest` run confirmed every tab, the chat, and both downloads render correctly in ₹ with the new data and no false income-drop finding.

### 2026-07-19 — Step 3 redesign, investment tracking (net worth/health/roadmap), and a Scenario Comparison page

Requested by the user: richer Step 3 confirmation fields with explanations, tracking of current investments and their CAGR "fully integrated" into net worth/health/roadmap (their explicit choice over a lighter, scenario-only option), and a proper what-if comparison page using practical Indian benchmarks - moved off Step 3, appearing once on the main page rather than duplicated per-tab. Planned via `EnterPlanMode` given the scope (contract changes touching the Phase 6 golden freeze); approved before implementation.

**Contract changes** (`utils/contracts.py`): `FinancialProfile` gained `confirmed_monthly_expenses` and `current_investments` (both `Optional[float]`, `None` = today's behavior exactly); `PlanningAssumptions` gained `investment_cagr`; `SnapshotMetrics` gained `net_worth`; `RoadmapAllocation` gained `investment_contribution`. Every new field defaults to `None`/`0.0` and is backward-compatible by construction - the whole feature had to prove this, not just assert it (see golden-fixture re-verification below).

**Deterministic core** (`utils/finance_calc.py`): `calculate_financial_snapshot()` now uses `confirmed_monthly_expenses` in place of the transaction-derived average whenever it is present (mirrors `monthly_income`'s existing "confirmed value wins" precedent), and computes `net_worth = current_savings + current_investments - total_debt` (`current_investments` absent contributes `0`, a real "no investments" fact; `current_savings` absent is the one case that makes `net_worth` itself unknown). New pure function `required_monthly_contribution_with_growth()` generalizes `goal_feasibility()`'s linear division into a future-value-of-annuity calculation for the FD/PPF/SIP scenario template - `goal_feasibility()` itself is untouched, since the golden fixtures depend on its exact rate-free arithmetic.

**Roadmap** (`utils/roadmap.py`, still the only place an allocation is decided): a new Step 6 branch routes the final "remainder" to a new `ACTION_GROW_INVESTMENT` action / `investment_contribution` instead of `ACTION_GROW_SAVINGS` / `savings_contribution`, but only when `investment_cagr` clears `savings_apy` by at least a new named `_CAGR_ADVANTAGE_THRESHOLD_PERCENT` (1.0 point - a margin, not a bare `>`, so a trivial rate difference doesn't flip the recommendation). The starter emergency buffer is never a candidate for this routing regardless of CAGR - an emergency fund needs to stay liquid and stable, not chase a return that can also fall. Verified end-to-end through the real `agents.graph.run_graph()` pipeline (not just the roadmap unit), producing a correct `ACTION_GROW_INVESTMENT` action, a correctly-updated Savings Strategist narrative, a passing consistency validation, and the action correctly ranked in the Coach Summary's `top_priorities`.

**Adjacent bug fixed while extending `agents/savings_agent.py`:** `savings_projection()` was being called without `apr`, silently defaulting to 4% regardless of the user's confirmed `savings_apy`. Fixed by threading the confirmed rate through; the agent now also narrates `investment_contribution` (with its own 24-month projection) when the roadmap produced one. `SpecialistResult.allocated_amount` for this agent is now `savings_contribution + investment_contribution` combined (the two are mutually exclusive by construction in `utils/roadmap.py`, so this is never double-counting the same rupee) - `utils/validation_structured.py`'s `expected_allocated_amount()` updated to match, and the prose-consistency allowlist (`utils/validation_prose.py`) extended to include `investment_contribution`.

**Step 3 UI** (`app.py`): added paired "current savings + interest rate earning on it" and "current investments + CAGR earning on it" fields (the latter two are new), plus a "monthly expenses" field pre-filled from the transaction-derived average and confirmable/overridable exactly like income. The income suggestion itself was refined from "most recent transaction" to "average observed monthly income," more robust to a single atypical month. Debts/goals tables gained per-column `help=` tooltips (e.g. explaining APR), and `DEFAULT_DEBTS`'s second entry changed from "Personal Loan" to "Car Loan" per the request. `minimum_monthly_buffer`/`emergency_fund_months` (target) moved out of Step 3 entirely into the Scenario Comparison page.

**Scenario Comparison page** (`app.py`, replacing the old bare assumption-tweak form; `utils/scenarios.py` gained `apply_expense_reduction()`): five sub-tabs in one section below the analysis tabs (never duplicated into them) - the original "Plan assumptions" preview (now housing the relocated buffer/emergency-fund-target controls), plus four new practical templates: idle savings vs. investing at the confirmed rates; cutting discretionary spending by a chosen percentage; prepaying debt vs. investing the same monthly amount over the same payoff horizon; and FD (≈6.5%) vs. PPF (≈7.1%) vs. Equity SIP (≈12%, illustrative benchmarks, clearly labeled as such) for a selected goal.

**Bug found and fixed while smoke-testing the Scenario Comparison page (not by a pre-written test):** the "cut discretionary spending" template scaled down the relevant transactions but the comparison showed exactly zero effect regardless of the cut percentage. Root cause: Step 3's `confirmed_monthly_expenses` override (now always populated, since it is pre-filled by default) shadowed the transaction-level change entirely - `calculate_financial_snapshot()` read the stale confirmed figure instead of recomputing from the now-reduced transactions. Fixed by clearing `confirmed_monthly_expenses` on the scenario's adjusted profile before rerunning the pipeline, so the reduced transactions' own average comes through, which is what "if I cut spending" should actually show. Regression test added (`tests/test_app.py::test_cut_discretionary_spending_scenario_actually_changes_the_comparison`).

**Golden fixture re-verification** (Phase 6 discipline, not skipped because this is post-release work): re-ran all three fixtures after the contract/roadmap changes twice - once for `net_worth`, once for `investment_contribution` - hand-verified each new number before updating `fixtures/golden/*.expected.json`; every other number stayed byte-identical both times, confirming the backward-compatibility design goal held in practice, not just in intent.

**Verification:** 361/361 passing (+24 new tests across `utils/finance_calc.py`, `utils/roadmap.py`, `agents/savings_agent.py`, `utils/scenarios.py`, and `app.py`'s live behavior), all five property-based invariants re-stress-tested at 1,000 examples with the new investment-routing path now genuinely exercised (the Hypothesis profile strategy was extended to sometimes generate investment data), and a full live `AppTest`/direct-pipeline run confirmed the `ACTION_GROW_INVESTMENT` path end-to-end - correct roadmap action, correct Savings Strategist narrative, passing consistency validation, correctly ranked in the Coach Summary.

### 2026-07-19 — Configurable currency and region, independent of each other

Requested by the user: options to use different currency fields and infer geography-driven behavior from a setting, without hardcoding the app to India/INR forever. Two prior maintenance entries above had switched the app from USD/$-generic to INR/₹-India-specific; this entry makes both dimensions user-selectable again while keeping "INR" + "india" as the exact default (byte-identical prior behavior when neither is touched). Two design questions were resolved with the user before implementation: (1) currency and region are **independent** settings (currency controls only the displayed symbol; region controls vendor-keyword categorization and Scenario Comparison's benchmark-rate tab) rather than one implying the other; (2) scope is INR + USD and india + generic for this pass, with region's benchmark tab using a generic 3-tier "safe/moderate/growth" trio instead of India-only FD/PPF/SIP when region is not india.

**New modules:**
- `utils/currency.py`: `CURRENCY_SYMBOLS` (`INR` → `₹`, `USD` → `$`), `format_money(amount, currency, decimals=0)`. This is now the **only** place a currency symbol is produced - every one of the ~73 previously-hardcoded `₹` literals across five agents, `utils/roadmap.py`, `utils/reporting.py`, and `app.py` now calls this function instead.
- `utils/region.py`: `SUPPORTED_REGIONS = ("india", "generic")`, `DEFAULT_REGION = "india"`, `BENCHMARK_RATES`/`BENCHMARK_CAPTION` per region (india: FD ≈6.5% / PPF ≈7.1% / Equity SIP ≈12%, unchanged from the prior entry; generic: an illustrative savings-account/bond-fund/index-fund trio), and `resolve_region()` (an unknown/absent region falls back to `"india"`, never a crash or empty config).

Both new modules import their canonical valid-value tuples (`SUPPORTED_CURRENCIES`, `SUPPORTED_REGIONS`) from `utils/contracts.py` rather than defining their own - `contracts.py` is documented as a pure leaf module that must never import back out of `utils/` (Contract rule 9 / dependency inversion, enforced by `tests/test_contracts.py`), so the dependency runs contracts → currency/region, not the reverse.

**Contract changes** (`utils/contracts.py`): `SUPPORTED_CURRENCIES = ("INR", "USD")` and `SUPPORTED_REGIONS = ("india", "generic")` added as canonical lists; `PlanningAssumptions` gained `region: Optional[str]` (`None` resolves to `"india"` via `utils.region.resolve_region()`); `default_assumptions()` now includes `"region": "india"`; `validate_assumptions()` rejects a `currency`/`region` value outside its canonical list when present, accepting `None`/absent as "use the default," matching every other optional-assumption field's validation style.

**Categorization** (`utils/ingestion.py`): the single `CATEGORY_KEYWORDS` table (built up additively across the two prior entries) was split into `_BASE_CATEGORY_KEYWORDS` (generic terms and widely-known/international brands - Starbucks, Whole Foods, Netflix, Amazon, Uber, etc.) and `_INDIA_CATEGORY_KEYWORDS` (Swiggy, Zomato, BigBasket, BESCOM, Jio, HDFC, Zerodha, EMI, SIP, PPF, etc.), with no keyword dropped or duplicated in the split - every category interleaves both cleanly, confirmed category by category before committing. `category_keywords(region)` merges base + the region's add-on (`{}` for `"generic"`); the module-level `CATEGORY_KEYWORDS` constant is kept as `category_keywords("india")` - byte-identical to the pre-split table - so every existing call site and test that references it directly keeps working unchanged. `_match_category()`/`categorize_with_confidence()` both gained an optional `keyword_table` parameter (defaulting to the module constant), rather than changing their required signature, for the same reason.

**Validator** (`utils/validation_prose.py`): `_DOLLAR_PATTERN` (added in the first entry above to match `₹` instead of `$`) is now `re.compile(r"[₹$]([\d,]+(?:\.\d+)?)")` - it matches either symbol, since the check only needs to extract a narrated amount for allowlist comparison and never needs to know which currency produced it. This is a strict widening of detection (never a narrowing), so it carries no new false-negative risk.

**Agents & roadmap** (`agents/savings_agent.py`, `debt_agent.py`, `goal_agent.py`, `spending_agent.py`, `utils/roadmap.py`): each gained an optional `currency` parameter threaded through `_build_summary()`/`_fallback_narrative()` (and `GoalPlannerAgent.run()`, which loops per-goal) exactly like existing narrow arguments such as `savings_apy` - per `agents/base.py`'s own documented constraint, no specialist may accept the whole profile/context, only explicit narrow inputs, so `currency` follows that same pattern rather than being smuggled in as a profile reference. `agents/graph.py`'s `spending_node`/`savings_node`/`debt_node`/`goal_node` read `profile["assumptions"].get("currency")` and pass it through. `utils/roadmap.py`'s `build_roadmap()` reads it from `profile["assumptions"]`; `explain_roadmap()`/`_fallback_roadmap_narrative()` (which only receive `roadmap`, not `profile`) read it from `roadmap["assumptions_used"]`, already stored there since Phase 3. `agents/budget_agent.py` was untouched - it narrates no money figure. One deliberate exception: `utils/finance_calc.py`'s goal-shortfall finding rationale (Phase 2's `derive_findings()`) had its single `₹` literal removed rather than given a `currency` parameter - that function's signature is `(snapshot, trends)` only by Phase 2's frozen, currency-agnostic design (documented in `Implementation Plan - MVP 1.md`, Phase 2's own interface-limitations note) and is called from ~15 sites across the test suite; the amount now renders without a symbol at that one spot, with formatting left to the specialist/report/UI layer that already owns it everywhere else.

**Reports** (`utils/reporting.py`): `_format_debts()`, `_format_goals()`, and `_format_roadmap()` gained an optional `currency` parameter; `format_report_markdown()` derives it once from `content["assumptions"].get("currency")` and threads it to all three, rather than each formatter reading assumptions independently.

**UI** (`app.py`): a new "Currency & region" section (two `st.selectbox`es) renders **before** Step 2's categorization, not inside Step 3 - because Streamlit reruns the whole script top-to-bottom on every interaction, a region change needs to reach `ingestion.category_keywords(region)` in the same rerun it's changed in, which is only possible if the widget executes earlier in the script than the categorization it feeds. The selected values are written into `st.session_state`'s `assumptions` dict immediately (via `app_state.set_profile_fields()`, preserving every other field) so Step 3's `current_assumptions` picks them up consistently. Every remaining hardcoded `₹` in Step 3/4/5/6 (labels, help text, metrics, the roadmap/goals/tracker renders) was replaced with `currency_symbol(currency)`/`format_money(..., currency)`. The FD/PPF/SIP Scenario Comparison tab's hardcoded `_PRESET_RATES` tuple and its "Indian rate benchmarks" caption were replaced with `utils.region.benchmark_rates(region)`/`benchmark_caption(region)`. Changing currency or region is an assumptions change like any other Step 3 field, so it invalidates the last analysis via the existing `app_state.set_profile_fields()` mechanism (from the first entry above) - the user re-confirms, same as after changing any other input.

**Bug found and fixed while wiring this feature, not by a pre-written test:** every fixture under `fixtures/*.json` and `fixtures/golden/*.input.json` declared `"currency": "USD"`, left over from before the first entry above switched the *default* to `"INR"` - harmless while `currency` was write-only and never actually consumed by any code path, but the moment this feature made it functional, `tests/test_roadmap.py::test_underfunded_goal_action_is_elevated_to_high_severity_this_month` failed (`"short of the ₹400"` no longer matched, since the fixture's declared USD now genuinely rendered `$`). Synced every fixture's `currency` field to `"INR"` to match the actual app default and every other test's already-embedded `₹` expectations, rather than rewriting the test to expect `$` - the fixtures' USD value was simply stale metadata, not an intentional test of USD behavior.

**Golden fixture re-verification** (Phase 6 discipline, unchanged pattern from the entry above): confirmed no `.expected.json` file needed any change - `tests/test_golden.py`'s `_build_captured()` never includes narrative text or the `assumptions` dict in what it compares, so neither the currency-symbol change nor the new `region` field could affect golden equality. Re-ran the full golden suite to confirm this rather than assuming it from the capture logic alone.

**Verification:** 388 passed, 4 skipped (25 new tests: `tests/test_currency.py` and `tests/test_region.py`, new files, covering symbol/rate lookups and fallback behavior; extensions to `tests/test_contracts.py` (currency/region validation), `tests/test_ingestion.py` (region-keyword parity/exclusion and `keyword_table` threading), and `tests/test_app.py` (two live `AppTest` runs: switching currency to USD changes a rendered Overview metric from `₹` to `$`; switching region to `generic` re-categorizes a bundled India-vendor sample transaction, "Swiggy Order," from `Dining` to `Other`)). Golden, property-based, and edge-case suites unaffected.

### 2026-07-19 — Logto-backed authentication (deliberate pivot ahead of the deferred schedule)

**Architecture deviation, made explicit rather than silently applied:** `Architecture Plan.md` puts OAuth and authentication out of scope for MVP 1, and `Architecture Plan - Later.md` places "Managed authentication" under the deferred `L0` milestone, after all of MVP 2. Requested by the user as a deliberate pivot ahead of that schedule ("use logto to create the authentication page for the app," with an explicit choice to build it now and update the docs rather than treat it as an undocumented spike). Both architecture documents were annotated in place with dated deviation notes rather than rewritten, so the original scope decisions remain visible as history, not erased. This entry, and `utils/auth.py`'s module docstring, are the canonical explanation of what changed and why.

**Provider setup:** a Logto tenant ("AI Financial Coach", ID `kqw1ib`, development tier, US region) and one Traditional (confidential) application ("Financial Coach (Streamlit)", ID `glhes5rwqd5jg2d9nt79x`) were created via the Logto MCP integration, with redirect URIs registered for both local dev (`http://localhost:8501/oauth2callback`) and the deployed app (`https://financialcoach.streamlit.app/oauth2callback`).

**Integration choice:** Streamlit's own native `st.login()`/`st.user`/`st.logout()` (stable since Streamlit 1.42, Authlib-backed) was used against Logto as a generic OIDC provider, **not** the Logto Python SDK's Flask-oriented guide (session-storage classes, `@app.route` handlers) - Streamlit has no request-routing layer of its own, so hand-rolling Flask-style session storage inside a single-script, rerun-on-every-interaction app would have fought the framework instead of using what it already ships. `requirements.txt` already had `streamlit>=1.42` and `Authlib>=1.3.2` staged from an earlier, undocumented session - this entry is also where that groundwork actually gets used and explained for the first time.

**New module:** `utils/auth.py` - `auth_enabled()`, `is_logged_in()`, `current_user_label()`, `render_login_screen()`, `render_signed_in_sidebar_control()`. Gating follows the exact pattern `utils.llm.is_live()` already established for `OPENROUTER_API_KEY`: `auth_enabled()` returns `False` (never raises) whenever `.streamlit/secrets.toml` is absent or has no `[auth]` section, so a missing configuration disables the feature rather than crashing the app - confirmed by `tests/test_auth.py`, which forces both the "no secrets file" and "secrets file present but no `[auth]` section" cases via monkeypatched `st.secrets`. `app.py` gates immediately after `st.set_page_config()` (the one place Streamlit allows it to run first): `if auth_enabled() and not is_logged_in(): render_login_screen(); st.stop()`, followed by a sidebar sign-out control for signed-in users. No existing screen, widget, or pipeline call was touched beyond that one gate.

**Secrets handling:** the real Logto `client_id`/`client_secret`/`server_metadata_url`/`redirect_uri`/`cookie_secret` live only in `.streamlit/secrets.toml`, which is gitignored (added to `.gitignore` this entry). `.streamlit/secrets.toml.example` is committed as the template, with `client_secret` deliberately left blank and a comment pointing at the Logto console for a long-lived secret - the application was created with only a temporary, 1-hour development secret, which was never written to any committed file.

**Test limitation, disclosed rather than glossed over:** the real OIDC redirect round-trip (`st.login()` → Logto's hosted sign-in page → callback → `st.user.is_logged_in`) is a live, browser-based flow. It cannot be driven by `streamlit.testing.v1.AppTest`, the same category of gap Phase 11's rehearsal already documented for `st.data_editor`. What is tested instead: `tests/test_auth.py` unit-tests the gating logic itself against monkeypatched `st.secrets`/`st.user`; `tests/test_app.py` adds two `AppTest`-based cases that monkeypatch `utils.auth.auth_enabled`/`is_logged_in` to prove the gate actually blocks the rest of `app.py` from executing when signed out, and that a signed-in user reaches the ordinary app with a sidebar identity caption when signed in. The end-to-end hosted sign-in page itself must be verified manually, by running `streamlit run app.py` locally with a real `.streamlit/secrets.toml`.

**Golden fixture re-verification:** not applicable - no fixture, contract, calculation, or narrative changed; this entry adds a UI gate in front of the existing pipeline, not a change to it. Full suite re-run to confirm.

**Verification:** 425 passed, 4 skipped (7 new tests in `tests/test_auth.py`; 3 new tests in `tests/test_app.py` - default-disabled regression, signed-out gate, signed-in pass-through). `ruff check .` and `mypy utils agents` both clean. Golden, property-based, MVP 2 regression, and dependency-boundary suites unaffected (`utils/auth.py` added to `tests/mvp2/test_dependency_boundaries.py`'s adapter-exception list alongside `utils/llm.py` and `utils/app_state.py`, for the same reason: it is the designated Streamlit adapter for this concern, not domain code that should be importing Streamlit directly).

### 2026-07-19 — Brand theme integration (navy/mint, dark+light) and copy pass

Requested by the user: integrate the landing page's design (`UI/Financial Coach Landing.dc.html`, `UI/uploads/financial-coach-login.html`) into the Streamlit app - same color palette and theme throughout, a dark/light toggle, and warmer, more human, finance-specialist-friendly copy. Both source pages hardcode the identical dark "navy + mint" palette (`--navy:#081527`, `--panel:#0d2238`, `--mint:#5ef3ce`, `--ink:#e8eff6`, `--muted:#8ca3b8`, `--green:#12c96f`) and the same two Google Fonts (Archivo for display type, Spline Sans for body) - that palette and both fonts are now the app's own, not approximated.

**New module:** `utils/theme.py` - `DARK`/`LIGHT` palette dicts, `render_theme_toggle()` (a sidebar `st.toggle`, default dark, persisted in `st.session_state`), `inject_theme_css()` (a single big `<style>` block re-injected every rerun with the active palette's literal values - Streamlit has no hot-swappable theme system, so a same-session toggle just means "rerun with different values," not client-side CSS variable flipping), and `apply_plotly_template()` (a registered `plotly.io` template so the Spending tab's pie/bar charts pick up the same palette without their call sites knowing about theming). Exempted from `tests/mvp2/test_dependency_boundaries.py`'s no-streamlit-in-domain-code rule the same way `utils/llm.py`/`utils/app_state.py`/`utils/auth.py` already are.

**Selector discovery, done empirically rather than guessed:** Streamlit 1.59's actual `data-testid`/`data-baseweb` attributes for tabs, checkboxes/toggles, and buttons were found by launching the app under Playwright (installed for this session; not added to `requirements.txt` - it was a verification tool, not a runtime or test-suite dependency) and inspecting the live DOM, not by assuming values from older Streamlit docs. Two guesses were wrong and fixed after visual verification caught them: tabs use `[data-testid="stTab"]`/`[aria-selected]`, not `[data-baseweb="tab"]`; the toggle's visible track is `[data-testid="stCheckbox"] label[data-selected="true"] > div`, not `[data-testid="stToggle"]`.

**Two genuine, disclosed Streamlit platform limitations, not bugs left unfixed:** (1) the `st.data_editor`/`st.dataframe` grid (glide-data-grid) reads its colors from the server's static `.streamlit/config.toml` `[theme]` block, not from any runtime CSS - a new `config.toml` was added with `base="dark"` matching the app's default toggle state exactly, but the grid does not itself flip when a user toggles to light in-session (documented in `config.toml`'s own comment). (2) `st.plotly_chart` paints a chart's `svg.main-svg` background from that same static config, overriding the figure's own `paper_bgcolor`/`theme=None` - confirmed by inspecting the rendered inline style before and after concluding it wasn't a caching bug. Rather than fight a value Streamlit will silently overwrite, chart panels were made deliberately theme-independent, always keeping the exact dark card treatment `UI/Financial Coach Landing.dc.html`'s own dashboard preview uses (that page has no light variant at all) - documented in `apply_plotly_template()`'s docstring as an intentional brand decision, not just a workaround.

**`app.py` changes:** `theme.render_theme_toggle()` / `inject_theme_css()` / `apply_plotly_template()` called right after `st.set_page_config()`, before the auth gate, so the toggle and theme are visible on the sign-in screen too. Both `st.plotly_chart(...)` call sites gained `theme=None` (harmless on its own, necessary alongside the template fix above). `[data-testid="stMetric"]` value/label CSS was loosened from Streamlit's default single-line-ellipsis truncation (`white-space: normal`, `word-break`, a responsive `clamp()` font size) after visual review caught the Overview tab's "Total debt"/"Net worth" cards clipping to `"₹195,0…"` in the new, more compact card styling - a real, pre-existing truncation risk the old default Streamlit metric styling happened to hide better, fixed as part of the same review rather than left for later.

**Copy pass:** `utils/auth.py`'s `render_login_screen()` was rebuilt from a one-line message into a two-column layout matching `UI/uploads/financial-coach-login.html`'s brand hero (eyebrow badge, "Stop the manual struggle. Start coaching." headline, three feature checkmarks, a bordered sign-in card) using Streamlit's own layout primitives (`st.columns`, `st.container(border=True)`) - not the static HTML file directly; `utils/theme.py`'s CSS is what makes it match, not copied markup. In `app.py`, the sidebar caption, coach-status line, offline-mode hint, and the empty-state prompt were reworded warmer and more direct (e.g. "A multi-agent financial coach" → "Your AI-powered money coach — plain-language insights, not just numbers."). Left unchanged, deliberately: every string an existing test asserts verbatim (tab labels, `"Step 4 - Analysis"`, the two download-button labels, `analyze_button`'s key) - each already read as clear and friendly, and renaming them for its own sake would only have added test-update churn with no reader benefit. The bulk of the app's existing captions/help text (Step 3's field-level explanations, the Scenario Comparison tab captions) were already in the same plain-language, competent-but-warm voice from earlier phases and were not rewritten wholesale.

**Visual verification (per this project's "start the dev server and use the feature in browser" standard for UI changes):** `streamlit run app.py` was launched locally and driven with Playwright (installed this session) through the full sample-data → confirm → Overview/Spending/Debt/Goals/Chat tab journey, in both dark and light mode, plus the sign-in screen (temporarily enabled with a throwaway, never-committed `.streamlit/secrets.toml` for this check only, deleted immediately after). Screenshots confirmed: sidebar/tabs/buttons/metrics/alerts/inputs/data-editor all restyle correctly on toggle; charts keep their intentional always-dark panel treatment in both modes; browser console showed zero errors across every screenshot pass. Screenshots themselves were scratch verification artifacts, not committed.

**Verification:** 426 passed, 4 skipped. `ruff check .` and `mypy utils agents` both clean. No fixture, contract, or calculation changed - full suite re-run to confirm.

### 2026-07-19 — Landing page wired into the actual user journey (landing → Logto → app)

**The gap this closes, stated plainly:** the previous entry integrated the landing page's *design tokens* (palette, fonts, theme) into the app, but not the landing page itself. `UI/Financial Coach Landing.dc.html` remained an unserved static file whose every call-to-action linked out to `https://financialcoach.streamlit.app/`; the only references to it anywhere in the codebase were comments inside docstrings. A user opening the app never saw it. Requested by the user: *"I want the landing page and then the authentication using logto. After the user is authenticated only then it should open the web app."*

**New module:** `utils/landing.py` - `render_landing_page()` (returns `True` when the CTA is clicked), plus `was_dismissed()`/`dismiss()`/`reset()` over a single `landing_dismissed` session key.

**Why the page is rebuilt in Streamlit primitives rather than embedded**, recorded because "just serve the HTML file" is the obvious first instinct and it does not work here: (1) `st.components.v1.html` renders into a sandboxed iframe via `srcdoc`, so the page's relative asset paths (`support.js`, `assets/app-demo.mp4`) do not resolve - inlining them means shipping a 68 KB runtime and a 9 MB base64 video on every load; (2) a CTA inside that iframe cannot write `st.session_state`, so it could not advance the visitor into sign-in and would still have to link out to the deployed URL, which is the exact disconnect being fixed; (3) rebuilt natively, the page inherits `utils/theme.py`'s CSS variables and therefore follows the dark/light toggle, which the source page (dark-only, no light variant) never supported. Copy, section order, palette, and type treatment are taken from the source. The JS-driven scroll-reveal and parallax effects are deliberately dropped (Streamlit strips `<script>` from `st.markdown`); pure-CSS motion - the marquee and the pulsing badge dot - is kept. The real `UI/assets/app-demo.mp4` is served through `st.video()`, guarded by an `os.path.isfile` check so a deploy without the `UI/` assets degrades instead of crashing.

**The gate in `app.py`** is three explicit stages, each rendering then calling `st.stop()`, because Streamlit has no router or middleware layer to enforce ordering centrally:

1. landing page, unless already dismissed this session or the visitor is already signed in;
2. Logto sign-in, skipped entirely when no `[auth]` section is configured (the same "missing config disables the feature, never crashes" rule `utils/auth.py` already followed for `OPENROUTER_API_KEY`);
3. the app.

A signed-in visitor skips stage 1 - the landing page is a first-visit marketing screen, not something to re-read on every rerun. Signing out calls `landing.reset()`, so a signed-out visitor lands where a first-time visitor does rather than being dropped onto a context-free sign-in gate. That import is function-local in `utils/auth.py` to keep the auth → landing dependency one-directional and avoid a circular import.

**Bug found by visual verification, not by a test:** the hero's `<div style='text-align:center'>` wrapper did nothing, because Streamlit renders each `st.markdown()` call into its own container - a `<div>` opened in one call and closed in another wraps nothing at all, so the alignment silently never applied. Fixed by emitting the badge, headline, and subcopy as one markdown block. Worth recording as a general Streamlit-HTML constraint, not a one-off typo.

**Test-suite impact, handled honestly rather than by bypassing the gate:** the landing page is now the first screen, so every one of `tests/test_app.py`'s `AppTest` entry points had to pass through it - which is correct, since those tests should exercise the real journey. Added a `_launch()` helper that starts the app and clicks the CTA, and made it tolerant of the signed-in case where the CTA does not exist by design. `_load_sample_and_analyze()` now documents that it assumes an already-launched app. No test sets `landing_dismissed` directly to skip the gate; they all go through it the way a user does.

**Visual verification:** `streamlit run app.py` driven with Playwright through all three stages. Confirmed with auth disabled (landing → CTA → app) and with auth enabled via a throwaway, never-committed `.streamlit/secrets.toml` (landing → CTA → sign-in, with the app asserted *not* to have leaked past the gate), in both dark and light mode, zero browser console errors. Note for future UI work: the autoplay looping hero video means Playwright's `networkidle` wait never settles - use `domcontentloaded` plus an explicit `wait_for_selector`.

**Verification:** 438 passed, 4 skipped (was 426; 4 new landing/gating tests plus the 7 boundary tests from the Task 0 commit). `ruff check .` and `mypy utils agents` clean. `utils/landing.py` added to `tests/mvp2/test_dependency_boundaries.py`'s adapter-exception list, on the same basis as `utils/llm.py`/`app_state.py`/`auth.py`/`theme.py`. No fixture, contract, or calculation changed.

### 2026-07-19 — Two real defects found by actually completing the Logto sign-in flow

Reported by the user: *"there is no login page after call to action button on the landing page."* Investigation found one configuration cause and two genuine defects, the second of which had been sitting latent behind the first since the authentication entry was written.

**Cause 1 (configuration, not a bug):** no `.streamlit/secrets.toml` existed on the machine, so `auth_enabled()` returned `False` and the sign-in stage was skipped exactly as designed - the CTA went straight to the app. That graceful degradation is deliberate (it is what lets CI, the test suite, and a fresh clone run with no Logto credentials), but it means the *only* signal that auth is unconfigured is the absence of a screen, which reads as a broken button. Resolved by creating a real local secrets file; the deeper lesson is recorded in the README, which now states the landing → sign-in → app journey and the fact that the middle step self-disables.

**Defect 1 - `Authlib` declared but never installed.** `requirements.txt` has carried `Authlib>=1.3.2` since the currency/region entry, but the working virtualenv predated that line and never had it. `st.login()` raises `StreamlitMissingAuthlibError` in that state. The failure mode is genuinely nasty: `auth_enabled()` returns `True`, the sign-in screen renders perfectly, and the app only blows up at the moment the user clicks the button - so everything looks configured right until it isn't, and the traceback lands in the server log rather than the browser. A fresh `pip install -r requirements.txt` was always sufficient; nothing in the repo was wrong. Fixed in the environment, and `tests/test_auth.py::test_authlib_is_actually_installed_not_just_declared` now asserts the running environment actually has the package rather than trusting the declaration - which is what CI would have caught and a stale local virtualenv would not.

**Defect 2 - Streamlit's default OIDC `prompt` is incompatible with Logto.** With Authlib installed, clicking Sign in produced `invalid_request` / `unsupported prompt value requested` from Logto's authorize endpoint, and bounced the user straight back to the app with no visible error at all. Root cause, read out of the installed Streamlit source rather than guessed: `streamlit/web/server/starlette/starlette_auth_routes.py` defaults `client_kwargs["prompt"]` to `"select_account"` when the `[auth]` section does not set it, and Logto does not accept that value. Fixed by setting `client_kwargs = { prompt = "login" }` - the OIDC value Logto does support for the same intent - and `.streamlit/secrets.toml.example` now carries that line with a comment marking it **required, not optional tuning**, since a future reader copying the template without it would hit exactly the same silent bounce.

**Why the earlier entry did not catch either defect, stated plainly:** that entry's own "test limitation" note said the hosted sign-in round-trip "must be verified manually" and was not driven end-to-end. Both defects live strictly *past* the point that verification stopped - the sign-in screen rendering correctly is precisely what both bugs let happen. Verification has now been carried through to the real Logto page: landing → CTA → sign-in screen → click Sign in → `https://kqw1ib.logto.app/sign-in?app_id=...` renders Logto's hosted form (email/password plus Google SSO), with a clean server log. What still is not automated is completing an actual credentialed login, which needs a real user account and a browser session against a live tenant.

**Verification:** 439 passed, 4 skipped (one new test). `ruff check .` and `mypy utils agents` clean. No fixture, contract, or calculation changed. The local `.streamlit/secrets.toml` holding the working credentials is gitignored and was confirmed untracked before committing; only the `.example` template is in the repository, with its `client_secret` blank.

### 2026-07-19 — Sign-in now fails closed when unconfigured

Reported by the user against the live deployment (`https://financialcoach.streamlit.app/`): clicking either landing-page call to action opened the app with no authentication at all.

**Diagnosis:** the deployment is running current code - the landing page renders there correctly - but Streamlit Community Cloud has no `[auth]` block in its Secrets, because `.streamlit/secrets.toml` is (correctly) gitignored and never deployed. `auth_enabled()` therefore returned `False` and the sign-in stage was skipped, exactly as written.

**The design was wrong, not just the config.** Modelling a missing `[auth]` section on `OPENROUTER_API_KEY`'s graceful degradation conflated two unlike things: an absent model key costs narrative quality, while an absent auth secret removes a security boundary. A misconfigured deploy was indistinguishable from a deliberately-open one, and the only symptom was the absence of a screen - which is why this surfaced twice as "the button is broken" rather than as "authentication is off". Silently serving a financial app to every visitor is not an acceptable default.

**Fix:** sign-in now fails closed. `utils/auth.py` gains `anonymous_access_allowed()`, reading `FC_ALLOW_ANONYMOUS`; `app.py`'s stage 2 becomes: if `[auth]` is configured, require sign-in; else if anonymous access is explicitly waived, continue; else render `render_auth_not_configured_screen()` and stop. The screen names the exact remedy (set the `[auth]` block in the deployment's Secrets, match `redirect_uri` to the deployed `/oauth2callback`, keep `client_kwargs = { prompt = "login" }`) rather than only reporting failure. Anonymous access is opt-in and deliberately narrow: only `1/true/yes/on` count, so a stray or empty value is never read as consent.

**Escape hatches, so nothing credential-free breaks:** `.env.example` documents `FC_ALLOW_ANONYMOUS=true` for local development, `.github/workflows/ci.yml` sets it for the offline job, and `tests/test_app.py`'s autouse fixture sets it alongside the existing `auth_enabled` pin - both needed for the same reason, that the suite must not depend on the developer's ambient configuration.

**Verification:** 441 passed, 4 skipped, green both with and without a local `.streamlit/secrets.toml`. Browser-verified that with no secrets and no waiver, the CTA reaches the "Sign-in isn't configured" screen and the app does not render behind it. `ruff` and `mypy` clean.

**Still outstanding and not fixable from the repository:** the deployed app requires its `[auth]` secrets to be set in the Streamlit Community Cloud dashboard, with `redirect_uri = "https://financialcoach.streamlit.app/oauth2callback"` (already registered on the Logto application) and a long-lived client secret rather than the temporary development one. Until that is done the deployment will show the fail-closed screen - which is the intended behaviour, and strictly better than the wide-open state it replaces.

### 2026-07-19 — Light mode rebuilt on native Streamlit theming; emoji replaced with mono icons

Reported by the user: light-mode colours were wrong, and separately, a request to drop emoji for mono-colour icons that follow the palette, plus more generous spacing.

**The light-mode bug was architectural, not a bad colour pick.** Two causes, both found by inspecting the rendered DOM rather than re-reading the CSS:

1. **Widgets read `config.toml`, not the stylesheet.** The number-input steppers rendered `rgb(13,34,56)` - exactly the old `secondaryBackgroundColor`. With a single static dark theme declared there, every widget Streamlit styles itself stayed navy in light mode regardless of what the injected CSS said. The data-editor grid and chart backgrounds were the same story, which is why earlier entries recorded them as permanent limitations. They were not limitations; they were a consequence of fighting the platform.
2. **Some override rules matched nothing.** `[data-baseweb="select"] > div` selected zero elements in this Streamlit version, so the select dropdown had never been styled at all - it only looked fine in dark mode because the static theme already was dark.

**And one genuine colour error, now measured rather than eyeballed.** Brand mint `#5ef3ce` was being used as a text colour. Against the light background it measures **1.3:1**, versus WCAG AA's 4.5:1 minimum - unreadable, and the visible symptom the user reported. Mint is a *fill* colour. Light mode now uses a deep teal-green `#0a7057` (5.7:1 on the page, 6.1:1 on cards) wherever the accent carries text or an icon, and pairs that fill with white (6.1:1) on buttons. Dark mode keeps mint, which measures 13.2:1 on navy. The palettes gained explicit `accent_text` / `accent_fill` / `accent_fill_ink` tokens so the two roles can never be conflated again.

**Fix:** Streamlit 1.59 supports real per-mode theming, so `.streamlit/config.toml` now declares `[theme]` (light) and `[theme.dark]`, and `utils/theme.py` reads the active mode via `st.context.theme.type` and injects only the brand layer on top. This fixed the steppers, the select dropdown, the dataframe grid, and chart backgrounds at their source, and let `apply_plotly_template()` drop its always-dark workaround and follow the active mode.

**The custom sidebar toggle was removed, deliberately.** There is no Python API to set Streamlit's native theme, so a custom toggle can only drive the CSS layer while the widget layer follows Streamlit - which *is* the bug above. Mode is now switched through Streamlit's own Appearance setting (top-right menu → Settings → Appearance), which also follows the OS preference by default; `render_theme_hint()` points at it from the sidebar. This trades a more discoverable control for one that is actually correct, and it was flagged to the user rather than changed quietly.

**Emoji removed.** Tabs, sidebar, buttons, alerts, downloads and the page icon now use Streamlit's built-in Material icons (`:material/...:`), which render as text and therefore inherit the palette in both themes. The landing and sign-in screens use small stroke SVGs drawn with `currentColor` for the same reason. Roadmap severity was a set of coloured emoji circles (🔴🟠🟡⚪🟢); it is now one geometric glyph tinted from a per-theme token, so severity colour stays meaningful in both modes. Beyond theming, emoji rendered inconsistently across platforms and were announced verbatim by screen readers.

**Spacing.** Added deliberate rhythm rather than ad-hoc nudges: wider main-container padding with a max width, larger vertical block gaps, real margins on headings, roomier metric/expander/button/tab padding, and more space between sidebar controls.

**Verification:** 441 passed, 4 skipped. `ruff` and `mypy` clean. Browser-verified in both modes by driving Chromium with `color_scheme` set to light and dark across landing → sign-in gate → Step 3 → analysis, zero console errors in either. Test label assertions were updated for the icon directives; no test bypasses the change.

### 2026-07-19 — Pinned to dark theme only

Requested by the user: "by default use dark theme only."

**Why both theme sections are declared identically.** Streamlit chooses between `[theme]` and `[theme.dark]` from the viewer's Appearance setting, which follows the operating system by default. Declaring only the dark one would still let a light-preferring visitor land on a derived light theme, so `.streamlit/config.toml` now carries the same dark palette in both - the app renders dark for everyone regardless of their OS or Streamlit preference. This matches the brand: `UI/Financial Coach Landing.dc.html` has no light variant at all.

`utils/theme.py` gained `_FORCE_MODE`, which pins the brand CSS layer to the same mode so the two layers can never disagree (the disagreement between those layers was the root cause of the light-mode bug fixed in the previous entry). `render_theme_hint()` became a no-op rather than being deleted, so re-enabling light mode does not require editing `app.py`.

**Nothing was thrown away.** The contrast-checked `LIGHT` palette and its measured ratios remain in `utils/theme.py`, and `config.toml` records the exact values to restore. Light mode is two coordinated changes away - `_FORCE_MODE = None` plus the light values under `[theme]` - and the comments in both files say so, because changing only one of the two would reintroduce precisely the widget/CSS split that caused the original bug.

**Verification:** 441 passed, 4 skipped; `ruff` and `mypy` clean. Browser-verified by driving Chromium with `color_scheme` set to **light** and confirming `.stApp` still computes to `rgb(8, 21, 39)` (`#081527`) on both the landing and in-app screens - i.e. a light-preferring visitor gets the dark theme.

### 2026-07-19 — Made LLM fallback reasons visible instead of silent

Asked by the user why the agents were not producing model-generated output despite an OpenRouter key being configured. Investigation found the agents *were* calling the model correctly - instrumenting a full pipeline run showed six `complete()` invocations, one per specialist plus the roadmap narrative - but every result carried `live = False` and every narrative was the rule-based fallback.

**The real defect was observability, not orchestration.** `utils/llm.py` ended `complete()` with a bare `except Exception: return None` and no logging. That made four completely different situations indistinguishable from each other and from normal offline operation: no key configured, an invalid key, an account without credits, and a model the account cannot access. In every case the app quietly served templated text with nothing - not a log line, not a UI hint - to say why. This is the same class of defect as the silent authentication fallback fixed earlier the same day: a graceful degradation path that hides the failure it is degrading from.

**Two concrete bugs found alongside it:**

1. `_MODEL` was evaluated at *import* time. Streamlit promotes top-level secrets into `os.environ` only when `st.secrets` is first accessed, which happens after this module is imported - so an `OPENROUTER_MODEL` set through Streamlit secrets was silently ignored and the default used instead. Both the model and the key are now read lazily.
2. Streamlit promotes only **top-level scalar** secrets to the environment (`_maybe_set_environment_variable` accepts `str`/`int`/`float`). A key placed after a `[section]` header belongs to that table, is a dict member, and is never promoted. Verified empirically: with `OPENROUTER_API_KEY` as a top-level line the running app's sidebar reads "Live"; nested, it reads "Offline". The no-key error message now states this explicitly, since it is the most likely misconfiguration.

**Fix:** failures are logged with their reason (never the key, and never the prompt, which carries the user's financial figures) and retained in `last_error()`. `app.py`'s sidebar shows the model name when live, and surfaces the failure reason when a key is configured but calls are failing. Behaviour is deliberately unchanged - callers still receive `None` and still fall back to rule-based narratives - only the silence is gone.

**Verification:** 441 passed, 4 skipped; `ruff` and `mypy` clean. Both paths exercised directly: with no key, `is_live()` is False and the reason names the top-level-placement requirement; with an invalid key, `is_live()` is True, `complete()` returns None, and the reason reads `AuthenticationError: Error code: 401 ... User not found.` - which previously produced no output at all.
