# MVP 2 Implementation Plan — 2-Hour Priority Cut

Sources:

- [Implementation Plan - MVP 2.md](Implementation%20Plan%20-%20MVP%202.md) is the authoritative, full-rigor MVP 2 plan. This document does not replace it — it selects the slice of it that fits a **2-hour session**, trims that slice's internal rigor explicitly (never silently), and hands back to the full plan for everything else.
- [Architecture Plan - MVP 2.md](Architecture%20Plan%20-%20MVP%202.md) remains the architecture authority; nothing here contradicts it.
- `docs/verification/mvp2/phase-0.md` — `mvp2-phase-0-done` is already tagged and verified; this document starts from there.

## 0. Why this document exists, and how to use it

Phase MVP2-0 — pure tooling and a regression baseline, explicitly "no MVP 2 domain behavior" — was itself a multi-hour undertaking once done at the rigor the full plan requires (baseline manifest, a dedicated regression suite, ruff/mypy adoption across the whole repo, a CI workflow, a phase verifier script, a dependency-boundary checker, and a full evidence document). Phases MVP2-1 through MVP2-8 are each larger than Phase 0: two-person fixture review, per-threshold boundary tests, 200+-example property suites, full `AppTest` UI coverage, and (from MVP2-2 onward) entirely new infrastructure — a reviewed retrieval corpus, an OpenRouter model runtime, a strategy-policy registry, a report-presentation layer, a conversation/tool system, a scenario workspace, and a full evaluation/release harness. None of that fits in 2 hours, and pretending otherwise would produce something that only looks done.

**What this document does instead:** picks the single highest-value, already-decoupled phase — MVP2-1, "Financial Position, Resilience Score, Actions, and Preferences" — because it is the one phase in the entire plan that consumes only frozen MVP 1 contracts and involves **no retrieval and no model call** (stated explicitly in the original phase's own scope). It is already architecturally isolated from every phase after it. This document trims *that one phase's* internal rigor down to a 2-hour-shaped subset, states every cut explicitly, and leaves Phases MVP2-2 through MVP2-8 completely untouched and unstarted.

**No phase is blocked by what's left out.** The dependency graph in Implementation Plan - MVP 2.md section 1.5 already has MVP2-1 depending on nothing but MVP 1's public contracts (`mvp2.profile -> MVP 1 public contracts only`). Everything downstream (knowledge, runtime, strategy, presentation, conversation, scenarios) depends on MVP2-1, never the reverse. Deferring 2 through 8 wholesale therefore removes zero prerequisites this document's own scope needs — the arrow only ever points the other way.

**This is a planning document, not a completed-work claim.** It does not tag `mvp2-phase-1-done` (that tag still means the *full* Phase 1, per the original plan, exactly as `mvp2-phase-0-done` was only tagged after Phase 0's full gate was green). See section 5 for exactly what remains before that tag is honest.

---

## 1. Delivery Law (2-Hour Cut)

### 1.1 Active order for this session

```text
MVP2-0 accepted (mvp2-phase-0-done, already tagged)
  -> MVP2-1-PRIORITY: 2-hour-shaped subset of Phase MVP2-1 (this document's only scope)
  -> everything else in Implementation Plan - MVP 2.md: untouched, not started
```

No phase in the full plan is reordered, skipped-with-a-stub, or partially imported. `mvp2/profile/` is the only package this document creates; `mvp2/knowledge/`, `mvp2/runtime/`, `mvp2/strategy/`, `mvp2/presentation/`, `mvp2/conversation/`, `mvp2/scenarios/` do not exist after this session, exactly as they didn't before it.

### 1.2 What "in scope for this cut" means

A task is in scope only if it is:

1. Required to produce a working `FinancialResilienceScore` and its supporting `FinancialDimensionAssessment[]`/`Action[]`/`DecisionContext` objects, **and**
2. Achievable, at reduced-but-real rigor, inside roughly 2 hours of focused work.

Every task that fails either test is listed explicitly in section 5 ("Deferred within MVP2-1") — not silently dropped.

### 1.3 Rigor relaxations for this session (disclosed, not silent)

These apply **only** to this document's execution. They are not a redefinition of what Phase MVP2-1 "done" means in the full plan — they are what makes a 2-hour session honest about what it can actually verify.

| Full-plan requirement | This session's version | Why |
|---|---|---|
| Two-person review of hand-recomputed fixtures | Single-reviewer (matches the established, disclosed project norm since MVP 1 Phase 6/`phase11-done` and MVP2-0 — no second reviewer has been available at any point in this solo project) | Not a new deviation; consistent with existing disclosed limitations |
| "One test immediately below, at, and immediately above every numeric boundary" for all 7 dimensions | Representative boundary tests (below/at/above) for the **6 score-owning dimensions only** | ~18 boundary tests per dimension × 7 is not a 2-hour task; representative coverage still catches the most common off-by-one class of bug |
| Hypothesis property tests "at least 200 valid profiles per policy" | Hypothesis still used; default example count (no explicit `max_examples` override) | Still real property coverage of the invariants that matter (score bounds, missing-data-never-increases-score), just not exhaustively tuned |
| Full `AppTest` coverage of confirm/skip/reset/rerun preference widgets | Preference *logic* unit-tested directly; UI wiring is a stretch item (section 6), not required | UI wiring for a feature nothing downstream reads yet (no strategy phase to consume a confirmed preference) is the lowest-value item in the phase |
| `docs/verification/mvp2/phase-1.md`, full template | A shorter evidence note for this session, same file, clearly marked partial | Evidence discipline is kept; length is not |
| All 7 financial dimensions | 6 dimensions — every one that feeds a `FinancialResilienceScore` component. `budget_variance_and_spending_stability` (no score contribution) is deferred | Cuts the one dimension that doesn't move the headline number, not one that does |

Section 1.4's No-regression Rule and section 1.5's No-cross-dependency Rule from Implementation Plan - MVP 2.md are **not** relaxed: the full MVP 1 suite and `mvp2-phase-0-done`'s regression/dependency-boundary suites must stay green throughout, and `tests/mvp2/test_dependency_boundaries.py` must be extended (not bypassed) to cover the new `mvp2/` package the moment it exists — this is explicitly cheap and non-negotiable. See **Task 0** below: Phase MVP2-0 left deliberate tripwires that fire on the first `mvp2/` commit, and clearing them correctly is the first ~10 minutes of this session.

---

## 2. Engineering Rules for This Session

Unchanged from Implementation Plan - MVP 2.md section 2 (SOLID application, coding standards, test rules, OpenAI Cookbook usage rule) — reproduced here only where this cut's smaller scope changes what applies:

- Section 2.5 (OpenAI Cookbook references) **does not apply to this session's work.** MVP2-1 makes no model call and no retrieval call by design (original plan: "No retrieval or model call exists in this phase"), so none of the seven Cookbook references are relevant until MVP2-2/MVP2-3.
- Section 2.3's required verification commands apply unchanged: `python -m pytest -q`, `python -m pytest -q tests/mvp2`, `python -m ruff check .`, `python -m mypy mvp2 utils agents`, `git diff --check`. `scripts/verify_mvp2_phase.py --phase 1` should gain a `PHASE_CHECKS[1]` entry mirroring `PHASE_CHECKS[0]`'s shape once this cut's tests exist.
- Section 2.4's "no monkey-patched financial calculations," "every registry entry has positive/boundary/ineligible/malformed/fallback tests," and "missing data is `None`, never zero" rules apply in full — these are what make even a trimmed cut trustworthy.

---

## 3. Phase Status Tracker (Priority)

| Phase | Complete feature unit | Status | Tag |
|---|---|---|---|
| MVP2-0 | MVP 1 handoff and regression baseline | Done | `mvp2-phase-0-done` |
| **MVP2-1-Priority** | **6 score-owning financial dimensions, Financial Resilience Score v1, goal-aligned actions, decision context, preference data model (no UI)** | **This document's target (~2 hours)** | none yet |
| MVP2-1 (full) | 7th dimension, preference UI + `AppTest`, exhaustive boundary/property tests, full evidence doc, two-reviewer sign-off | Deferred — resumes from the Priority cut, does not restart it | `mvp2-phase-1-done` (not yet) |
| MVP2-2 | Reviewed corpus and governed local RAG | Deferred, not started | — |
| MVP2-3 | Agent capability, structured tools, OpenRouter runtime, budgets | Deferred, not started | — |
| MVP2-4 | Constrained adaptive strategy | Deferred, not started | — |
| MVP2-5 | Novice profile and Detailed audit report | Deferred, not started | — |
| MVP2-6 | NLP report interaction and suggested prompts | Deferred, not started | — |
| MVP2-7 | Immutable scenarios and integrated app | Deferred, not started | — |
| MVP2-8 | Evaluation, hardening, rehearsal, release | Deferred, not started | — |

---

## Phase MVP2-1-Priority — Financial Position, Resilience Score, and Actions (2-Hour Cut)

**Independent unit:** from frozen MVP 1 structured outputs, deterministically build a financial-position profile (6 of 7 dimensions), a transparent coaching score, and goal-aligned actions. No retrieval or model call exists in this phase — unchanged from the full plan.

**Entry criterion:** `mvp2-phase-0-done` is verified on `main`. Already true.

**Consumes:** frozen MVP 1 profile, snapshot, trends, findings, risks, baseline roadmap, validation, and report identifiers — unchanged.

**Produces:** `PreferenceProfile` (data model + `confirm`/`skip`/`reset` functions, no Streamlit wiring), `FinancialDimensionAssessment[]` for 6 dimensions, `FinancialResilienceScore`, normalized `Action[]` references, and `DecisionContext`.

### Package and dependency layout

Identical to the full plan — nothing about the package shape changes when the scope inside it is trimmed:

```text
mvp2/
  __init__.py
  contracts.py              # leaf; stdlib/typing/Pydantic only
  errors.py                 # typed MVP 2 domain errors
  hashing.py                # canonical JSON + SHA-256 helpers
  profile/
    __init__.py
    preferences.py
    dimensions.py
    scoring.py
    actions.py
    decision_context.py
    rules_v1.py
tests/mvp2/
  fixtures/profile/
  test_contracts.py
  test_preferences.py
  test_dimensions.py
  test_resilience_score.py
  test_goal_actions.py
  test_decision_context.py
```

`mvp2/contracts.py` must not import `utils`, `agents`, Streamlit, Chroma, or model code — same leaf-module rule as everything else in this repo, checked by `tests/mvp2/test_dependency_boundaries.py`.

### Tasks — in scope for this session

#### Task 0. Unblock the repo for its first `mvp2/` package — do this first (~10 min)

Phase MVP2-0 deliberately left tripwires that fire the moment `mvp2/` appears. These are **not** optional cleanup: two of them turn the suite red on the very first commit of this cut, and one silently weakens CI. All three are in scope, cheap, and were verified against the current `main` (`4fa5894`) rather than assumed:

- [ ] **`tests/mvp2/test_dependency_boundaries.py::test_no_mvp2_package_exists_yet` will fail immediately.** It asserts `not (REPO_ROOT / "mvp2").exists()`. Its own docstring already specifies the correct resolution: *"this test's failure is expected and it should be replaced by real per-file graph enforcement using `_MVP2_DEPENDENCY_GRAPH`, not silently deleted."* Replace it — do not delete it, and do not weaken it to a no-op.
- [ ] **`_MVP2_DEPENDENCY_GRAPH` as encoded forbids the package layout above.** It maps `"mvp2.profile": {"mvp1_public"}`, so enforcing it literally makes `mvp2/profile/*` importing `mvp2.contracts` / `mvp2.errors` / `mvp2.hashing` a boundary violation — yet the layout requires exactly those imports, and Implementation Plan - MVP 2.md's own package layout puts them there. Resolve by adding the shared leaf modules (`mvp2.contracts`, `mvp2.errors`, `mvp2.hashing`) as universally-importable, and keep the leaf rule itself enforced (they may import stdlib/typing/Pydantic only, never `utils`/`agents`/Streamlit/a sibling subpackage). This is an encoding gap in Phase 0's placeholder graph, not a change to the architecture's intent.
- [ ] **`.github/workflows/ci.yml`'s mypy step is hardcoded to `python -m mypy utils agents`**, with an inline comment stating it must be manually extended when `mvp2/` lands. Add `mvp2`. Without this, CI stops type-checking the *only* package that is not mypy-exempt (`pyproject.toml` grants `ignore_errors` to `utils.*`/`agents.*` but deliberately not to `mvp2.*`), while local runs via `scripts/verify_mvp2_phase.py` — whose `_mypy_targets()` already adds `mvp2` automatically — would still catch errors. That divergence is worse than either state alone.
- [ ] **Add `PHASE_CHECKS[1]` to `scripts/verify_mvp2_phase.py`**, mirroring `PHASE_CHECKS[0]`'s shape. Today `--phase 1` exits 2 ("no checks defined"), by design; this cut is what defines them.

#### A. Phase-owned contracts

- [ ] `PreferenceProfile`, `FinancialDimensionAssessment`, `FinancialResilienceScore`, `DecisionContext`, and a phase-owned `ActionRecommendation` — exactly as the full plan's Task A, this is cheap (TypedDicts/dataclasses + a validator function) and gates everything else, so it stays fully in scope.
- [ ] Schema version `1.0`; reject unsupported versions and unknown enum/field values at the boundary.
- [ ] Canonical sorted-key UTF-8 JSON + SHA-256 helpers in `mvp2/hashing.py` (needed by `DecisionContext` and later phases; cheap to write once).
- [ ] Deep-copy inputs at the service boundary; one test proves a source MVP 1 object is unchanged after a profile-service call.
- [ ] Commit valid, missing-data, negative-cashflow, no-debt, no-goal fixtures under `tests/mvp2/fixtures/profile/` (multi-goal/low-runway/high-debt-service/partial-history/duplicate-data fixtures are a stretch item — section 6).

#### B. Preferences — data model only

- [ ] Implement `confirm_preferences()`, `skip_preferences()`, `reset_preferences()` against the allowlisted `debt_payoff_style`/`planning_style`/`goal_tradeoff` values.
- [ ] `source=user_confirmed`/`source=user_skipped` + UTC timestamp.
- [ ] Do not infer preferences from transactions/locale/demographics/model output — same hard rule as the full plan.
- [ ] **Not in scope this session:** the `app.py` confirm/skip/reset UI step and its `AppTest` coverage (section 6, stretch). Nothing else in this cut reads a confirmed preference, so its absence blocks nothing here.

#### C. Financial dimensions — 6 of 7

Implement these six registry entries in `profile/rules_v1.py` (the exact set that feeds a `FinancialResilienceScore` component):

```text
cashflow_adequacy
liquidity_and_emergency_runway
debt_servicing_and_interest_burden
savings_capacity_and_consistency
goal_funding_progress
data_confidence
```

**Deferred this session:** `budget_variance_and_spending_stability` — it contributes no score points and its rule (adverse-finding-severity → status mapping) is the most subjective of the seven. Cutting it does not change the score total or break any other dimension's independence (each dimension's registry entry is self-contained by design).

For each of the six:

- [ ] Return exactly one status: `resilient`, `adequate`, `watch`, `stressed`, `critical`, `unknown`.
- [ ] Return metric refs, calculation refs, evidence refs (empty — no retrieval yet), data confidence, and at least one action ref.
- [ ] Missing data never produces `resilient`.
- [ ] Register by ID via a plain dict/registry, not a UI-label conditional.

Freeze the same v1 thresholds table the full plan specifies (cashflow, liquidity, debt, savings, goal funding, data confidence rows only — omit the budget/spending row for now):

| Dimension | Critical | Stressed | Watch | Adequate | Resilient | Unknown |
|---|---|---|---|---|---|---|
| Cashflow adequacy | `gross_surplus < 0` | `gross_surplus == 0` | `gross_surplus > 0` and `allocatable_surplus == 0` | positive allocatable surplus below 15% of income | allocatable surplus at least 15% of income | missing/zero income or missing surplus |
| Liquidity/runway | `<0.5` month | `0.5–<1` | `1–<target` | `target–<1.5×target` | `>=1.5×target` | expenses/runway/target unavailable |
| Debt servicing | minimum-payment DTI `>=40%` | `30–<40%` | `20–<30%` | `>0–<20%` | no debt / 0% | income or DTI unavailable while debt exists |
| Savings capacity | savings rate `<0%` | `0–<5%` | `5–<10%` | `10–<20%` | `>=20%` | savings rate unavailable |
| Goal funding | critical goal failure | high-priority goal has `pace_ratio <0.5` | any goal has `pace_ratio <1` | all goals at pace with one data limitation | all goals at pace without limitation | no goal or goal inputs unavailable |
| Data confidence | `NO_TRANSACTIONS` | `ZERO_INCOME_TRANSACTIONS` or total deduction `>=6` | deduction `3–5` | deduction `1–2` | no flags | source/flags unavailable |

- [ ] One representative boundary test (at, one-below, one-above) per dimension — not the full plan's exhaustive per-threshold set.

**Two MVP 1 input semantics to resolve deliberately, not discover as bugs** (both verified against `utils/finance_calc.py` on `main`, so neither is a blocker — but both are easy to get subtly wrong):

- `debt_to_income_percent` is `None` **only** when `monthly_income` is missing or `<= 0`. A profile with no debts yields `0.0`, never `None` (`total_minimum_payments` is `0`). So the `unknown` row ("income or DTI unavailable **while debt exists**") requires reading `profile["debts"]` too, not the metric alone: no-debt-and-no-income is `resilient` per the table's "no debt / 0%" row, while has-debt-and-no-income is `unknown`. Test both.
- The metric is genuinely minimum-payment-based (`sum(min_payment) / monthly_income * 100`), which is what the threshold table's "minimum-payment DTI" wording requires — confirmed, not assumed. No new calculation is needed in `mvp2/`; reuse the frozen metric.

#### D. Financial Resilience Score v1 — full scope, kept whole

This is the headline deliverable, so it is **not** trimmed relative to the full plan:

- [ ] Keep MVP 1 `health_score` byte-identical (already proven by `tests/mvp2/test_mvp1_regression.py` from Phase 0 — no new work here, just don't touch it).
- [ ] Compute integer component points exactly as specified: cashflow (max 25), liquidity (max 20), debt (max 20), savings (max 15), goal funding (max 10), data confidence (max 10) — sum to max 100.
- [ ] Freeze all six `financial-resilience-v1` formulas verbatim from Implementation Plan - MVP 2.md section "Phase MVP2-1 / D" (cashflow clamp formula, liquidity clamp, debt linear decrease 20%→40%, savings clamp, goal-funding weighted mean with high=3/medium=2/low=1, data-confidence deduction table).
- [ ] Emit formula version, calculation refs, missing-input refs, component maxima, limitations.
- [ ] Never use the CIBIL 300–900 scale or bureau terminology; label the score "Financial Resilience Score — not a credit/CIBIL score" wherever it is rendered.
- [ ] A reviewer (single reviewer this session, per section 1.3) manually recomputes all six components for at least **two** fixtures (healthy, stressed/missing-data) — the full plan asks for three; two is the 2-hour-shaped version of the same check, still a real hand-verification, not skipped.

#### E. Goal-aligned actions

- [ ] Convert existing roadmap/finding/risk responses into stable action references — no LLM involved, matching the full plan's hard rule.
- [ ] Rank by: invalid/missing-data resolution → hard constraint/negative cashflow → confirmed goal impact → severity → urgency → roadmap priority → stable action ID.
- [ ] No-goal fallback sequence (`financial_resilience_baseline`): resolve data → stabilize negative cashflow → protect commitments/buffer → establish emergency runway → address high-cost debt → improve savings consistency → ask user to set a goal.
- [ ] Every one of the 6 in-scope dimensions has at least one action.
- [ ] **Deferred this session:** multi-goal tie-break ordering by priority/date/ID beyond a single representative multi-goal test (full exhaustive multi-goal ordering coverage is section 5).

#### F. Decision context — simplified

- [ ] `derive_decision_context(profile, snapshot, findings, risks, preferences, dimensions, score, actions)`.
- [ ] Derive 2–4 evidence topics deterministically from active finding/risk/dimension/action IDs — the topics are produced now so `DecisionContext` is real and complete; nothing consumes them yet (MVP2-2 does), which is fine, since producing an unconsumed-but-correct object is not the same as leaving a stub.
- [ ] **MVP2-1 owns the canonical topic vocabulary — it is not blocked on the corpus that will later use it.** Deriving a topic does not require MVP2-2's 10–15 reviewed documents to exist; the dependency runs the other way (`mvp2.knowledge -> mvp2.profile contracts/IDs only`, Implementation Plan - MVP 2.md section 1.5), so MVP2-2's per-document `topic` metadata must later conform to the enum defined here. Define it as a closed enum in `mvp2/contracts.py` this session, sized to the topic list MVP2-2 already enumerates (starter emergency buffer, staged runway, minimum-payment protection, avalanche/snowball trade-offs, negative-cashflow stabilization, irregular-income budgeting, competing-goal sequencing, plan simplification, cautious trend interpretation, monthly review) so the later corpus has a fixed target rather than a moving one.
- [ ] `jurisdiction=general`, user currency, `audience=individual_consumer`.
- [ ] Deterministic ordering, capped reference lists — same rule as the full plan.

#### G. Minimal offline diagnostic (replaces the full plan's UI task)

The full plan's Task-adjacent UI requirement ("offline app shows confirmed preferences and a temporary structured profile diagnostic") is kept, but shrunk to the cheapest honest version:

- [ ] Add one collapsed `st.expander("MVP 2 profile diagnostic (preview)")` in `app.py`, placed after the existing Step 4 tabs, rendering the 6 dimension statuses and the resilience score as plain structured output (a dataframe or JSON, not styled) — proves the new module is wired into the real app and runs offline, without spending time on presentation polish that belongs to MVP2-5.
- [ ] No preference confirm/skip/reset widget this session (section 1.3/6).

### Required tests (2-hour scope)

- [ ] Contract round-trip and rejection tests pass.
- [ ] Source MVP 1 objects remain unchanged after a profile-service call (one test, not exhaustive).
- [ ] Each of the 6 dimensions has one below/at/above boundary test.
- [ ] Score component math reproduces the two hand-reviewed fixtures exactly and sums to 0–100.
- [ ] Missing data never increases a score or creates a healthy status (property test, default Hypothesis example count).
- [ ] No-debt earns full debt points without fabricating debt facts.
- [ ] No-goal earns zero goal points and produces the resilience-baseline action sequence.
- [ ] Every in-scope dimension resolves metric/calculation/action refs.
- [ ] Debt dimension: `unknown` vs `resilient` is correct for both no-debt-no-income and has-debt-no-income (the `None`-DTI ambiguity resolved in Task C).
- [ ] `tests/mvp2/test_dependency_boundaries.py` extended to actually check `mvp2/profile/*` against the section-1.5 graph now that it exists (was previously inert/future-only per Phase 0's own tests), with `test_no_mvp2_package_exists_yet` **replaced by** real enforcement rather than deleted (Task 0).
- [ ] A planted reverse-import fixture (e.g. `mvp2/profile` importing a later subpackage, or a shared leaf importing `utils`) is still rejected — proving the extended checker is not vacuously passing, the same standard Phase 0 held itself to.
- [ ] MVP 1 goldens, MVP2-0's regression suite, and the complete suite remain green.

**Not required this session** (full-plan items, explicitly deferred — see section 5): exhaustive per-threshold boundary tests for all 7 dimensions; 200-example property runs; `AppTest` coverage of preference widgets; multi-goal/low-runway/high-debt-service/partial-history/duplicate-data fixture variants beyond what Task A already commits.

### Exit gate (2-hour scope)

- [ ] Every task/test above is complete.
- [ ] A single reviewer manually recomputes all six score components for two fixtures (healthy, stressed/missing-data).
- [ ] Offline app shows the structured profile diagnostic (section G) without any RAG/model dependency.
- [ ] `docs/verification/mvp2/phase-1.md` is written, explicitly marked **"Priority cut — see sections 5–6 of Implementation Plan - MVP 2 Priority.md for what remains before `mvp2-phase-1-done`."**
- [ ] Full test suite (`python -m pytest -q`) and `python -m ruff check .` / `python -m mypy mvp2 utils agents` are green.
- [ ] **Not tagged `mvp2-phase-1-done`** — that tag is reserved for the full Phase 1 gate. This cut's evidence file and any commit are the actual record of what shipped; tagging (like every tag in this project) happens only on explicit user request, and only once the full gate — not this cut — is met, unless the user explicitly decides otherwise.

---

## 4. Deferred Phases — Full Scope Unchanged

Phases MVP2-2 through MVP2-8 are **exactly** as specified in Implementation Plan - MVP 2.md. Nothing about their scope, formulas, contracts, or exit gates changes because of this document. They are listed here only to make the "nothing kept is blocked by what's left out" guarantee checkable line by line:

| Phase | What it needs from earlier phases | Needed from this cut? |
|---|---|---|
| MVP2-2 (RAG/knowledge) | `DecisionContext.topics`, approved profile/action IDs from MVP2-1 | Yes, but only *reads* MVP2-1's output — MVP2-1-Priority already produces a real, complete `DecisionContext`, so MVP2-2 is not blocked *by this cut specifically*; it is simply not started this session |
| MVP2-3 (runtime/tools) | Completed contracts + `KnowledgeGateway` (MVP2-2) | Not started; correctly blocked by MVP2-2 not existing yet — exactly as the original plan's own entry criteria already require |
| MVP2-4 (strategy) | Profile/score/actions/preferences (MVP2-1) + evidence (MVP2-2) + runtime (MVP2-3) | Not started; same reasoning |
| MVP2-5 (presentation) | MVP2-1 + MVP2-2 + MVP2-4 | Not started |
| MVP2-6 (conversation) | MVP2-5 + MVP2-2 + MVP2-3 | Not started |
| MVP2-7 (scenarios) | Everything through MVP2-6 | Not started |
| MVP2-8 (eval/release) | Everything through MVP2-7 | Not started |

Every "not started" phase above was *already* going to be blocked by its own stated entry criterion before this document existed — that is the original plan's own strictly-sequential design (section 1.1: "The only permitted order is..."). This document does not introduce any new blocking; it simply stops, honestly, at the first phase boundary a 2-hour session can actually clear.

### 4.1 Blocking audit — every in-scope component vs. everything deferred

This is the check that the "nothing kept is blocked by anything cut" claim is actually true, done per-component against the real code on `main` (`4fa5894`) rather than asserted. **Result: no in-scope component depends on any deferred MVP2 phase.** Four repo-state items *did* need pulling into scope; they are now Task 0 and are not deferrals.

| In-scope component | Everything it needs | Supplied by | Blocked by anything deferred? |
|---|---|---|---|
| Contracts, errors, hashing | stdlib/typing/Pydantic only | itself (leaf) | No |
| `PreferenceProfile` + confirm/skip/reset | allowlisted enum values, UTC clock | itself | No — the deferred piece is the *widget*; the deferred widget cannot block the data model it would have written to |
| 6 dimensions | `gross_surplus`, `allocatable_surplus`, `emergency_fund_months`, `average_monthly_expenses`, `debt_to_income_percent`, `savings_rate_percent`, goal fields, data-quality flags | frozen MVP 1 `SnapshotMetrics` + `profile` — **all verified present** | No |
| Data-confidence dimension + score component | flag codes `NO_TRANSACTIONS`, `ZERO_INCOME_TRANSACTIONS`, `MISSING_MONTHS`, `DUPLICATE_TRANSACTIONS`, `INSUFFICIENT_HISTORY`, `PARTIAL_TRAILING_MONTH` | `utils/ingestion.py` — **all six verified to exist**, matching the deduction table exactly | No |
| Goal-funding dimension + score component | `required_monthly`, `shortfall`, goal `priority` | `utils.finance_calc.goal_feasibility()` returns exactly `required_monthly`/`feasible`/`shortfall`; priority is on the frozen `Goal` contract — **verified** | No |
| Debt dimension + score component | minimum-payment DTI | `debt_to_income_percent` is genuinely `sum(min_payment)/income*100` — **verified**, not an approximation | No |
| `FinancialResilienceScore` | the 6 dimensions above | in-scope, all 6 kept | No — and the deferred 7th dimension (`budget_variance_and_spending_stability`) contributes **zero** score points, so the headline number is complete, not partial |
| Goal-aligned actions | roadmap actions, findings, risks | frozen MVP 1 pipeline; plan forbids LLM-created actions, so no MVP2-3 runtime needed | No |
| `DecisionContext` | active IDs, preferences, a topic vocabulary | in-scope; **MVP2-1 owns the topic enum** — `mvp2.knowledge -> mvp2.profile` means the corpus conforms to it later, never the reverse | No |
| Offline diagnostic in `app.py` | `st.expander` + the score/dimension objects | Streamlit + in-scope objects | No — deliberately renders raw structured output so it needs nothing from MVP2-5's presentation layer |

**Deferred-but-consumed check (the reverse direction):** nothing kept in this cut *reads* a deferred artifact. Specifically — no in-scope code path calls a `KnowledgeGateway` (MVP2-2), a `ModelGateway`/`ToolExecutor` (MVP2-3), a `StrategyPolicy` (MVP2-4), a `ReportPresentation` (MVP2-5), a `ConversationResponse` (MVP2-6), or a `ScenarioRunner` (MVP2-7). `FinancialDimensionAssessment.evidence_refs` is the only field that will *eventually* be filled by a deferred phase, and the full plan already specifies it as **empty until retrieval exists** — so an empty list here is the specified correct value, not a stub awaiting MVP2-2.

**One honest caveat, recorded rather than smoothed over:** `DecisionContext.topics` is *produced* but nothing *consumes* it until MVP2-2. That is intentional (the object would be incomplete and later need reopening otherwise), and it is the only in-scope output with no in-scope reader. It is testable on its own terms — determinism, ordering, 2–4 cap, valid enum members — so it is verified work, not speculative work, but it will not be exercised end-to-end until MVP2-2 lands.

---

## 5. Deferred Within MVP2-1 Itself (the checklist for finishing the phase properly)

A later session returning to finish Phase MVP2-1 — not restart it — should treat this exact list as its checklist, then proceed to tagging `mvp2-phase-1-done` and starting MVP2-2:

1. Implement the 7th dimension, `budget_variance_and_spending_stability` (registry entry + threshold table row + boundary tests).
2. Add the `app.py` preference confirm/skip/reset UI step (before MVP 2 analysis, per the full plan's Task B) and its `AppTest` coverage (confirm, skip, reset, rerun).
3. Fill in the remaining fixture variants from Task A: multi-goal, low-runway, high-debt-service, partial-history, duplicate-data.
4. Expand each of the 6 already-implemented dimensions from representative boundary tests to the full plan's exhaustive below/at/above-every-threshold set.
5. Raise the missing-data-never-increases-score property test to the full plan's "at least 200 valid profiles" via an explicit `max_examples=200`.
6. Add a third hand-reviewed fixture (multi-goal or low-runway) to the score-component manual recomputation.
7. Get an actual second reviewer for at least the negative-cashflow-class fixtures, if one ever becomes available (same disclosed, carried-forward limitation as MVP 1 Phase 6 and MVP2-0).
8. Expand `docs/verification/mvp2/phase-1.md` from this session's short note to the full template's fields.
9. Only then: tag `mvp2-phase-1-done` (on explicit user request) and begin MVP2-2 exactly as Implementation Plan - MVP 2.md section 1.1 specifies.

---

## 6. If Time Remains This Session (stretch, in priority order)

Only attempt these after every item in the Phase MVP2-1-Priority "Required tests" and "Exit gate" sections above is green. Stop at whichever point the 2 hours run out — each item here is independently useful and does not need the one after it:

1. Preference confirm/skip/reset UI + one `AppTest` (moves item 2 of section 5 partly off the deferred list).
2. The 7th dimension, `budget_variance_and_spending_stability` (moves item 1 of section 5 off the deferred list).
3. Polish the diagnostic expander from raw structured output into the Simple-style compact cards the full Phase MVP2-5 will eventually own properly — kept deliberately minimal, not a real preview of Phase 5's UI, to avoid quietly doing Phase 5 work inside a Phase 1 session.
4. Widen boundary-test coverage toward the full per-threshold set for the highest-traffic dimension (`cashflow_adequacy`) as a proof the remaining expansion (section 5 item 4) is mechanical, not risky.

---

## 7. Definition of Done for This 2-Hour Session

This session is complete only when:

1. `mvp2/profile/*` exists, is fully wired into `app.py`'s offline diagnostic, and computes a `FinancialResilienceScore` from real MVP 1 pipeline output.
2. All four Task 0 items are done: `test_no_mvp2_package_exists_yet` replaced (not deleted) by real graph enforcement, the shared-leaf gap in `_MVP2_DEPENDENCY_GRAPH` closed, `mvp2` added to CI's mypy step, and `PHASE_CHECKS[1]` added so `scripts/verify_mvp2_phase.py --phase 1` runs.
3. The full MVP 1 suite, Phase 0's regression/dependency-boundary suites, and this session's new tests are all green in one `python -m pytest -q` run.
4. `ruff check .` and `mypy mvp2 utils agents` are clean.
5. `docs/verification/mvp2/phase-1.md` exists and is honestly marked as a Priority-cut, not a full Phase 1 sign-off.
6. Sections 4 and 5 of this document are still accurate — i.e., nothing was quietly started in MVP2-2 through MVP2-8, and every deferred item in section 5 is still actually deferred, not half-done and unrecorded.

Tagging `mvp2-phase-1-done` and starting MVP2-2 are explicitly **not** part of this session's Definition of Done — see section 5.
