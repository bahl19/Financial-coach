# MVP 2 Implementation Plan: Strictly Sequential, Gated Delivery

Sources:

- [Architecture Plan - MVP 2.md](Architecture%20Plan%20-%20MVP%202.md) is the MVP 2 scope and architecture authority.
- [Implementation Plan - MVP 1.md](Implementation%20Plan%20-%20MVP%201.md) defines the mandatory MVP 1 handoff.
- [intent.md](intent.md) defines the product intent: stable, grounded, cost-aware coaching before breadth.
- [Architecture Plan - Later.md](Architecture%20Plan%20-%20Later.md) owns every deferred live, regulated, persistent, or portfolio capability.

This plan converts MVP 2 into a small number of complete, strictly sequential implementation phases. It is written so a developer unfamiliar with the repository can execute one checklist item at a time without inventing architecture, formulas, dependencies, or acceptance criteria.

MVP 2 does **not** begin from the currently implemented MVP 1 Phase 5. It begins only after MVP 1 Phase 11 is complete, verified, merged, and tagged.

---

## 1. Delivery Law

### 1.1 Mandatory phase order

The only permitted order is:

```text
MVP 1 Phase 11 accepted
  -> MVP2-0 release handoff and regression baseline
  -> MVP2-1 financial position, resilience score, actions, and preferences
  -> MVP2-2 reviewed corpus and governed local RAG
  -> MVP2-3 bounded tools, OpenRouter model runtime, and budgets
  -> MVP2-4 constrained adaptive strategy
  -> MVP2-5 novice profile and Detailed audit report
  -> MVP2-6 NLP report interaction and suggested prompts
  -> MVP2-7 immutable scenarios and full Streamlit integration
  -> MVP2-8 evaluation, hardening, rehearsal, and release
```

There is no parallel phase work. A developer may parallelize tasks **inside the currently open phase** only when the file ownership is disjoint and the phase owner integrates and verifies the combined result before the gate.

### 1.2 What “phase complete” means

A phase is complete only when all of the following are true:

- [ ] Every task and phase-specific checklist item is implemented; no `TODO`, `pass`, placeholder, disabled test, fake success, or future capability stub remains.
- [ ] Every phase test passes locally in a clean virtual environment.
- [ ] The complete test suite for MVP 1 plus all completed MVP 2 phases passes.
- [ ] Every deterministic/golden/property invariant introduced by earlier phases still passes.
- [ ] Offline mode passes without `OPENROUTER_API_KEY`.
- [ ] No secret, raw financial record, full report, or prompt body appears in logs or committed fixtures.
- [ ] Static checks, dependency-direction checks, and `git diff --check` pass.
- [ ] The phase evidence file under `docs/verification/mvp2/phase-N.md` contains commands, results, fixture IDs, known limitations, verifier, date, and accepted commit SHA.
- [ ] The phase PR is reviewed and merged to `main`.
- [ ] The merged commit is tagged `mvp2-phase-N-done`.
- [ ] The Phase Status Tracker is updated only after verifying the merged commit, not the feature branch.

“Implemented,” “works on my machine,” “tests mostly pass,” and “the UI looks right” do not mean complete.

### 1.3 Gate failure rule

If any gate fails:

1. Keep the current phase open.
2. Record the failure and reproduction command in its evidence file.
3. Fix the defect in the current phase.
4. Run the failed test, the phase suite, and the complete cumulative suite again.
5. Do not design, code, branch, or merge the next phase while the failure exists.

### 1.4 No-regression rule

Every phase runs three layers of verification:

1. **Phase tests:** prove the new capability.
2. **Cumulative MVP 2 tests:** prove all completed MVP 2 capabilities still work together.
3. **Frozen MVP 1 tests and goldens:** prove the baseline product has not changed.

The `baseline_balanced` path must preserve frozen MVP 1 numeric/enum/ID outputs exactly. Narrative fields may vary only where MVP 1 golden rules already permit narrative variation. No phase may update an MVP 1 expected fixture merely to make a regression pass. A changed expected value requires a documented defect in the old expectation, two-person review, and an explicit architecture decision.

### 1.5 No-cross-dependency rule

Each phase may import only:

- Python/third-party libraries approved in that phase;
- frozen MVP 1 public contracts/services;
- completed MVP 2 phases to its left in the dependency chain;
- its own package.

It may not import a later phase, call an unimplemented future service, register a future tool, create a future schema “for convenience,” or rely on a later UI to validate its output.

Add an AST/import-boundary test that enforces this direction. The allowed dependency graph is:

```text
mvp2.profile       -> MVP 1 public contracts only
mvp2.knowledge     -> mvp2.profile contracts/IDs only
mvp2.runtime       -> shared MVP 2 contracts; no domain calculation imports
mvp2.strategy      -> profile + knowledge + runtime protocols + MVP 1 roadmap
mvp2.presentation  -> profile + knowledge + strategy + MVP 1 report objects
mvp2.conversation  -> presentation + knowledge + runtime
mvp2.scenarios     -> completed deterministic services + runtime tool protocol
app.py             -> one composition root over all completed services
```

Reverse arrows are forbidden. Domain modules never import `app.py`, Streamlit, OpenRouter clients, Chroma clients, or concrete infrastructure adapters.

---

## 2. Engineering Rules for Every Phase

### 2.1 SOLID application

- **Single Responsibility:** calculations, retrieval, model I/O, tool authorization, orchestration, rendering, and persistence-free session state live in separate modules.
- **Open/Closed:** dimensions, policies, model routes, intent rules, tool handlers, and eval graders use reviewed registries. Add a registry entry and tests; do not grow one unbounded conditional.
- **Liskov Substitution:** real/fake/offline gateways implement the same protocol and return the same result/error contracts.
- **Interface Segregation:** callers receive narrow protocols such as `KnowledgeGateway`, `ModelGateway`, `ToolExecutor`, and `ScenarioRunner`; no “god service” exposes every operation.
- **Dependency Inversion:** deterministic domain logic depends on protocols and contracts. Concrete OpenRouter, Chroma, filesystem-manifest, and Streamlit adapters depend on domain interfaces, never the reverse.

### 2.2 Coding standards

- Use pure functions for calculations, status rules, score components, action derivation, eligibility, allocation, comparison, and validation.
- Use `Decimal` or the existing project-wide money-rounding convention at monetary boundaries; never compare displayed rounded values as calculation inputs.
- Use timezone-aware UTC timestamps only for metadata. Financial observations retain their source period/date.
- Use stable IDs and explicit versions; do not derive identity from model prose.
- Preserve unknown as `None`; never convert absent data to zero or “healthy.”
- Validate at every boundary: UI to contract, contract to service, model to schema, tool request to handler, handler to result, and result to renderer.
- Exceptions use typed domain errors. User-facing text is mapped at the composition/UI boundary.
- Catch only errors that can be handled. Never use broad silent `except Exception: return None` in new MVP 2 infrastructure.
- Retries apply only to transient transport/rate/server failures. Schema errors, authorization failures, invalid requests, insufficient credits, and deterministic validation failures do not retry.
- Logs contain request IDs, route/tool IDs, hashes, counts, timings, token/cost totals, and error codes—not financial values, prompts, evidence excerpts, or API keys.
- New public functions have type hints and docstrings describing authority, invariants, and side effects.
- New dependencies are minimal, justified in the phase evidence, version-bounded, and included in a reproducible lock/requirements workflow.

### 2.3 Required verification commands

Establish these commands in MVP2-0 and keep them green thereafter:

```bash
python -m pytest -q
python -m pytest -q tests/mvp2
python -m pytest -q tests/test_golden.py tests/mvp2/test_mvp1_regression.py
python -m ruff check .
python -m mypy mvp2 utils agents
python scripts/verify_mvp2_phase.py --phase N
git diff --check
```

If the repository deliberately chooses different lint/type tools, record that once in MVP2-0 and update this plan before implementation. Do not silently omit a check because the tool is not installed.

### 2.4 Test rules

- Unit tests do not require network access, model keys, a downloaded embedding model, or a persistent user directory.
- Use dependency injection and deterministic fakes; do not monkey-patch financial calculations into returning expected answers.
- Every defect gets a failing regression test before or with the fix.
- Every registry entry has positive, boundary, ineligible, malformed, and fallback tests.
- Property tests cover allocation, score bounds, hash immutability, reference resolution, and missing-data behavior.
- Snapshot/golden tests assert structured values, not whitespace-heavy UI markup.
- Live OpenRouter and real-embedding tests use explicit markers and never run in the default offline CI job.
- A release job runs approved live smoke/eval tests with a hard cost ceiling and sanitized artifacts.

### 2.5 OpenAI Cookbook usage rule

Use Cookbook implementations as design references, not copy-pasted dependencies or reasons to bypass this architecture. In particular:

- use strict structured-output schemas and automated schema evals;
- let the model propose a tool call and let application code validate/execute it;
- build prompt changes through an analyze → measure → improve evaluation flywheel;
- compare model quality and cost with task-specific evals;
- use bounded exponential backoff with jitter for transient API limits;
- keep RAG retrieval measurable and independently testable.

The exact references are listed at the end of this plan.

---

## 3. Phase Status Tracker

| Phase | Complete feature unit | Architecture priority | Status | Completed | Verified by | Tag |
|---|---|---|---|---|---|---|
| MVP2-0 | MVP 1 handoff and regression baseline | P0 | Done (see caveats in [phase-0.md](docs/verification/mvp2/phase-0.md)) | 2026-07-19 | bahl19 + Claude Code | `mvp2-phase-0-done` |
| MVP2-1 | Financial position, resilience score, actions, preferences | P1–P2 | Not started | | | |
| MVP2-2 | Reviewed corpus and governed local RAG | P3 | Blocked by MVP2-1 | | | |
| MVP2-3 | Agent capability and model runtime | P4 | Blocked by MVP2-2 | | | |
| MVP2-4 | Constrained adaptive strategy | P5 | Blocked by MVP2-3 | | | |
| MVP2-5 | Novice profile and Detailed audit report | P6 | Blocked by MVP2-4 | | | |
| MVP2-6 | NLP report interaction and suggested prompts | P7 | Blocked by MVP2-5 | | | |
| MVP2-7 | Immutable scenarios and integrated app | P8 | Blocked by MVP2-6 | | | |
| MVP2-8 | Evaluation, regression, demo, and release | P9–P10 | Blocked by MVP2-7 | | | |

---

## Phase MVP2-0 — MVP 1 Handoff and Regression Baseline

**Independent unit:** a reproducible, verified MVP 1 release baseline and the delivery/test machinery required to prevent regression.

**Entry criterion:** none for planning. Implementation is blocked until every MVP 1 Phase 11 item is green.

**Consumes:** MVP 1 repository only.

**Produces:** accepted baseline commit/tag, baseline manifest, CI/static checks, phase verifier, and evidence template. It produces no MVP 2 domain behavior.

### Tasks

#### A. Prove MVP 1 is actually complete

- [ ] Open [Implementation Plan - MVP 1.md](Implementation%20Plan%20-%20MVP%201.md) and verify Phases 0–11 are marked complete with dates and verifiers.
- [ ] Verify MVP 1 Phase 6 expected golden files exist and were manually reviewed.
- [ ] Verify report/tracker, Streamlit integration, property tests, UX gate, offline journey, and two clean demo rehearsals are complete.
- [ ] Run the entire MVP 1 suite in a newly created virtual environment from committed requirements.
- [ ] Run the full MVP 1 user journey with and without `OPENROUTER_API_KEY`.
- [ ] Confirm the current implementation uses one canonical graph/pipeline and one allocation authority, `build_roadmap()`.
- [ ] Confirm category corrections reach calculations and exports.
- [ ] Confirm negative cashflow produces zero distributed allocation everywhere.
- [ ] Confirm reports, specialist amounts, roadmap allocation, and Coach Summary reconcile.
- [ ] Confirm `phase11-done` exists on the exact accepted commit. If the existing project uses a different tag convention, record the exact tag in evidence.
- [ ] Stop here if any MVP 1 gate is incomplete. Do not create MVP 2 packages or dependency changes.

#### B. Freeze the regression baseline

- [ ] Create `fixtures/mvp2/mvp1_baseline_manifest.json` containing accepted commit SHA, MVP 1 tag, Python version, dependency-lock hash, golden fixture hashes, expected test count, and UTC acceptance timestamp.
- [ ] Add `tests/mvp2/test_mvp1_regression.py` that runs the accepted baseline profiles through the canonical pipeline and compares every frozen numeric, enum, ID, priority, severity, allocation, validation, and report value.
- [ ] Assert MVP 1 `FinancialSnapshot.health_score` remains unchanged. MVP 2 later adds a separate `FinancialResilienceScore`; it must not rewrite this field.
- [ ] Add a test that scans for a second allocation implementation or specialist-side allocation constants.
- [ ] Add a test that baseline report generation is reproducible from the same frozen inputs.
- [ ] Record baseline timings for full tests and offline sample journey; these are diagnostics, not permission to skip slow tests.

#### C. Establish repeatable tooling

- [ ] Add `.github/workflows/ci.yml` if CI is absent. It must install from scratch, run lint, types, all offline tests, goldens, and dependency-boundary checks.
- [ ] Add/standardize `ruff` and `mypy` configuration without weakening existing runtime behavior.
- [ ] Add `scripts/verify_mvp2_phase.py`. It accepts only a completed phase number, runs all required checks through that phase, writes no source files, and exits non-zero on any failure.
- [ ] Add `docs/verification/mvp2/phase-template.md` with environment, commit, commands, outputs, fixture review, security review, regression result, limitations, verifier, and sign-off fields.
- [ ] Add `tests/mvp2/test_dependency_boundaries.py` using AST/module inspection to reject reverse imports and later-phase imports.
- [ ] Define pytest markers: `unit`, `integration`, `property`, `golden`, `live_model`, `real_embedding`, `ui`, and `eval`.
- [ ] Ensure default CI excludes only `live_model` and `real_embedding`; no deterministic or UI test is excluded.
- [ ] Ensure live jobs have an explicit secret check, request cap, token cap, and dollar cap.

### Required tests

- [ ] Clean-environment install succeeds.
- [ ] Full MVP 1 suite passes.
- [ ] All MVP 1 goldens pass unchanged.
- [ ] Baseline manifest hashes match committed artifacts.
- [ ] Deliberately changing one allocation cent fails regression.
- [ ] Deliberately changing one score, severity, priority, or ID fails regression.
- [ ] Narrative-only variation permitted by MVP 1 does not fail a structured golden.
- [ ] Dependency-boundary test rejects a deliberately created reverse-import fixture.
- [ ] CI runs successfully on the merged commit.

### Exit gate

- [ ] Every task and test above is checked.
- [ ] `docs/verification/mvp2/phase-0.md` records the accepted MVP 1 commit and all results.
- [ ] No MVP 2 domain package, contract, flag, corpus, or UI has been added.
- [ ] PR merged and the merged commit tagged `mvp2-phase-0-done`.

---

## Phase MVP2-1 — Financial Position, Resilience Score, Actions, and Preferences

**Independent unit:** from frozen MVP 1 structured outputs, deterministically build a financial-position profile, a transparent coaching score, goal-aligned actions, explicit preferences, and decision context. No retrieval or model call exists in this phase.

**Entry criterion:** `mvp2-phase-0-done` is verified on `main`.

**Consumes:** frozen MVP 1 profile, snapshot, trends, findings, risks, baseline roadmap, validation, and report identifiers.

**Produces:** `PreferenceProfile`, `FinancialDimensionAssessment[]`, `FinancialResilienceScore`, normalized `Action[]` references, and `DecisionContext`.

### Package and dependency layout

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

`mvp2/contracts.py` must not import `utils`, `agents`, Streamlit, Chroma, or model code. Domain services may read MVP 1 mappings through narrow function arguments; they do not mutate them.

### Tasks

#### A. Add phase-owned contracts

- [ ] Implement and validate `PreferenceProfile`, `FinancialDimensionAssessment`, `FinancialResilienceScore`, and `DecisionContext` exactly as defined by the architecture.
- [ ] Add a phase-owned `GoalImpact` and `ActionRecommendation` contract if needed to make action semantics explicit. It must include action ID, verb/title, amount/rule, cadence/date, goal refs or `financial_resilience_baseline`, reason refs, expected metric effect, review trigger, and data confidence.
- [ ] Use schema version `1.0` for each new contract and reject unsupported versions.
- [ ] Reject unknown enum values and unknown object fields at external boundaries.
- [ ] Canonically serialize sorted-key UTF-8 JSON and compute SHA-256 IDs/hashes without timestamps or prose fields.
- [ ] Deep-copy/freeze inputs at the service boundary; tests must prove source MVP 1 objects are unchanged.
- [ ] Commit valid, missing-data, negative-cashflow, no-debt, no-goal, multi-goal, low-runway, high-debt-service, partial-history, and duplicate-data fixtures.

#### B. Implement explicit preferences

- [ ] Implement `confirm_preferences()`, `skip_preferences()`, and `reset_preferences()`.
- [ ] Accept only `debt_payoff_style`, `planning_style`, and `goal_tradeoff` values from the architecture allowlist.
- [ ] Store `source=user_confirmed` or `source=user_skipped` and a UTC confirmation timestamp.
- [ ] Do not infer preferences from transactions, locale, demographics, device behavior, report chat, or model output.
- [ ] In `app.py`, add a confirm/skip/reset preference step after MVP 1 facts are confirmed and before MVP 2 analysis. Session state is the only writer.
- [ ] Skipping preferences must produce `None`/`no_preference` effects and preserve baseline behavior.

#### C. Implement financial dimensions

Implement these seven registry entries in `profile/rules_v1.py`:

```text
cashflow_adequacy
liquidity_and_emergency_runway
debt_servicing_and_interest_burden
savings_capacity_and_consistency
budget_variance_and_spending_stability
goal_funding_progress
data_confidence
```

For every entry:

- [ ] Declare required metric/finding/risk/trend inputs.
- [ ] Return exactly one status: `resilient`, `adequate`, `watch`, `stressed`, `critical`, or `unknown`.
- [ ] Return metric refs, calculation refs, goal impact, evidence refs (empty until retrieval), data confidence, and at least one action ref.
- [ ] A healthy dimension gets a maintain/monitor action with a review cadence.
- [ ] An unknown dimension gets a data-completion action; missing data never produces `resilient`.
- [ ] Register the rule by ID; do not use a UI-label conditional.

Freeze these v1 status thresholds:

| Dimension | Critical | Stressed | Watch | Adequate | Resilient | Unknown |
|---|---|---|---|---|---|---|
| Cashflow adequacy | `gross_surplus < 0` | `gross_surplus == 0` | `gross_surplus > 0` and `allocatable_surplus == 0` | positive allocatable surplus below 15% of income | allocatable surplus at least 15% of income | missing/zero income or missing surplus |
| Liquidity/runway | `<0.5` month | `0.5–<1` | `1–<target` | `target–<1.5×target` | `>=1.5×target` | expenses/runway/target unavailable |
| Debt servicing | minimum-payment DTI `>=40%` | `30–<40%` | `20–<30%` | `>0–<20%` | no debt / 0% | income or DTI unavailable while debt exists |
| Savings capacity | savings rate `<0%` | `0–<5%` | `5–<10%` | `10–<20%` | `>=20%` | savings rate unavailable |
| Budget/spending stability | critical adverse finding | high adverse finding or severe variance | medium adverse finding/variance | low variance and no high finding | stable trend plus no adverse finding | insufficient history/data-quality block |
| Goal funding | critical goal failure | high-priority goal has `pace_ratio <0.5` | any goal has `pace_ratio <1` | all goals at pace with one data limitation | all goals at pace without limitation | no goal or goal inputs unavailable |
| Data confidence | `NO_TRANSACTIONS` | `ZERO_INCOME_TRANSACTIONS` or total deduction `>=6` | deduction `3–5` | deduction `1–2` | no flags | source/flags unavailable |

Use half-open boundaries exactly as written. Add one test immediately below, at, and immediately above every numeric boundary.

#### D. Implement Financial Resilience Score v1

Keep MVP 1 `health_score` byte-identical for regression compatibility. The new score is the only coaching score rendered in MVP 2 and is always labelled “Financial Resilience Score — not a credit/CIBIL score.” Never show both scores side by side.

Compute integer component points before summing:

```text
cashflow_adequacy                    max 25
liquidity_and_emergency_runway      max 20
debt_servicing_and_interest_burden  max 20
savings_capacity_and_consistency    max 15
goal_funding_progress               max 10
data_confidence                     max 10
total                              max 100
```

Freeze these formulas in `financial-resilience-v1`:

- [ ] Cashflow: 0 when surplus is missing/non-positive; 10 when gross surplus is positive but allocatable is zero; otherwise `round(25 * clamp((allocatable_surplus / income) / 0.15, 0, 1))`.
- [ ] Liquidity: `round(20 * clamp(emergency_fund_months / configured_target_months, 0, 1))`; missing inputs earn 0 and create missing refs.
- [ ] Debt: 20 for no debt/0% DTI; 20 through 20% DTI; linearly decrease from 20 to 0 between 20% and 40%; 0 at/above 40% or when required inputs are missing.
- [ ] Savings: `round(15 * clamp(savings_rate_percent / 20, 0, 1))`; negative/missing earns 0.
- [ ] Goal funding: for each goal, `pace_ratio = 1` when required monthly is zero, otherwise `clamp((required_monthly - shortfall) / required_monthly, 0, 1)`; weighted mean uses high=3, medium=2, low=1, then `round(10 * weighted_mean)`. No goals earns 0 and triggers the set-goal action.
- [ ] Data confidence: start at 10; deduct `NO_TRANSACTIONS=10`, `ZERO_INCOME_TRANSACTIONS=4`, `MISSING_MONTHS=3`, `DUPLICATE_TRANSACTIONS=2`, `INSUFFICIENT_HISTORY=2`, `PARTIAL_TRAILING_MONTH=1`; clamp to 0–10.
- [ ] Sum component points; do not add a hidden adjustment, model judgement, or demographic factor.
- [ ] Emit formula version, calculation refs, missing-input refs, component maxima, and limitations.
- [ ] Never use the CIBIL 300–900 scale, CIBIL styling, bureau terminology, approval probability, or creditworthiness claims.

#### E. Implement goal-aligned actions

- [ ] Convert existing roadmap/finding/risk responses into stable action references; do not let an LLM create actions.
- [ ] Rank actions by: invalid/missing-data resolution → hard constraint/negative cashflow → confirmed goal impact → severity → urgency → roadmap priority → stable action ID.
- [ ] For multiple goals, use goal priority high/medium/low, then nearest target date, then stable goal ID.
- [ ] Every displayed dimension has at least one action.
- [ ] If no goal exists, use `financial_resilience_baseline` in this exact order: resolve data → stabilize negative cashflow → protect commitments/buffer → establish emergency runway → address high-cost debt → improve savings consistency → ask user to set a goal.
- [ ] No-goal actions use historical MVP 1 facts and reviewed deterministic rules only. Do not mention current news, laws, rates, products, or market conditions.

#### F. Build decision context

- [ ] Implement `derive_decision_context(profile, snapshot, findings, risks, preferences, dimensions, score, actions)`.
- [ ] Derive 2–4 evidence topics deterministically from active finding/risk/dimension/action IDs and confirmed preferences.
- [ ] Use `jurisdiction=general`, user currency, and `audience=individual_consumer`.
- [ ] Include compact IDs/values required for decisions; exclude raw transactions and full report prose.
- [ ] Make ordering deterministic and cap each reference list.

### Required tests

- [ ] Contract round-trip and rejection tests pass.
- [ ] Source MVP 1 objects remain byte/hash identical after every profile service call.
- [ ] All status-boundary tables have below/at/above tests.
- [ ] Score component math reproduces manually reviewed fixtures exactly and sums to 0–100.
- [ ] Missing data never increases a score or creates a healthy status.
- [ ] No-debt earns full debt points but does not fabricate debt facts.
- [ ] No-goal earns zero goal points and produces the set-goal/resilience action sequence.
- [ ] Multi-goal ordering is deterministic.
- [ ] Every dimension resolves metric/calculation/action refs.
- [ ] Preference skip has no strategy effect and no hidden inferred value.
- [ ] MVP 1 goldens and complete suite remain unchanged.
- [ ] Streamlit preference step passes `AppTest` for confirm, skip, reset, and rerun.

### Exit gate

- [ ] Every task/test above is complete.
- [ ] A reviewer manually recomputes all six score components for at least three fixtures: healthy, stressed debt/low runway, and missing-data/no-goal.
- [ ] Offline app shows confirmed preferences and a temporary structured profile diagnostic without any RAG/model dependency.
- [ ] `docs/verification/mvp2/phase-1.md` is signed.
- [ ] PR merged and tagged `mvp2-phase-1-done`.

---

## Phase MVP2-2 — Reviewed Corpus and Governed Local RAG

**Independent unit:** a local, open-source, metadata-first retrieval service over 10–15 reviewed coaching documents, with deterministic fallback and no user-data embeddings.

**Entry criterion:** `mvp2-phase-1-done` is verified on `main`.

**Consumes:** deterministic `DecisionContext.topics` and approved profile/action IDs only.

**Produces:** validated `EvidenceQuery` and `EvidenceBundle`; it does not select a policy or calculate money.

### Package layout

```text
mvp2/knowledge/
  contracts.py
  manifest.py
  chunking.py
  embedding.py
  chroma_store.py
  fallback.py
  gateway.py
  build_index.py
knowledge/mvp2/
  corpus_manifest.json
  documents/*.md
  reviewed_chunks.json
tests/mvp2/fixtures/retrieval/
tests/mvp2/test_knowledge_*.py
```

### Tasks

#### A. Create and review the corpus

- [ ] Author 10–15 short documents covering starter emergency buffer, staged runway, minimum-payment protection, avalanche/snowball trade-offs, negative-cashflow stabilization, irregular-income budgeting, competing-goal sequencing, simplifying a plan, cautious trend interpretation, and monthly review.
- [ ] Exclude live laws, tax rates, schemes, market news, current rates, return forecasts, named products, and jurisdiction-specific limits.
- [ ] Give every document: `document_id`, title, topic, audience, jurisdiction, publisher, source URI, source version, review date, reviewer, content hash, and `allowed_for_coaching=true`.
- [ ] Require two-person review for any text that can affect policy selection.
- [ ] Fail index construction on duplicate IDs, missing metadata, hash mismatch, future review date, unapproved document, unsupported jurisdiction, or more/fewer than 10–15 active documents.

#### B. Deterministic chunking and index build

- [ ] Normalize UTF-8, LF line endings, surrounding whitespace, and Markdown headings before hashing.
- [ ] Chunk by H2/H3 section first; split oversized sections into paragraphs capped at 1,200 characters; never split a sentence solely to reach a token target.
- [ ] Use stable chunk ID `{document_id}:{heading_slug}:{ordinal}`.
- [ ] Inherit document metadata and add chunk hash, ordinal, character count, and allowed topic.
- [ ] Commit `reviewed_chunks.json`; do not commit Chroma binary/index files.
- [ ] Pin `sentence-transformers/all-MiniLM-L6-v2` to an exact Hugging Face revision recorded in the manifest.
- [ ] Add `sentence-transformers` and `chromadb` as version-bounded dependencies.
- [ ] Build the local persistent collection under a configurable application cache path, never the Git repository or user-upload directory.
- [ ] Make index build idempotent: same manifest and model revision produce the same IDs/hashes and replace no unrelated collection.
- [ ] Provide `python -m mvp2.knowledge.build_index --verify` for install/release verification.

#### C. Metadata-first retrieval

- [ ] Implement `KnowledgeGateway.retrieve(EvidenceQuery) -> EvidenceBundle`.
- [ ] Validate and cap `max_results` at 4.
- [ ] Filter by active corpus version, topics, audience, jurisdiction, and `allowed_for_coaching=true` **before** vector ranking.
- [ ] Query embeddings only inside the filtered candidates.
- [ ] Sort equal-distance results by stable chunk ID.
- [ ] Return evidence ID, document ID, title, topic, excerpt, source URI, publisher, versions, review date, content hash, score/distance, and warnings.
- [ ] Never pass raw profile, transaction, debt, goal, chat, or report text into Chroma.
- [ ] Escape/label corpus text as evidence; instructions inside documents are data, not system instructions.

#### D. Deterministic fallback

- [ ] Implement fallback lookup from topic to reviewed chunk IDs in the manifest.
- [ ] Use fallback when the model asset, Chroma library, collection, or query fails validation/availability.
- [ ] Return the same `EvidenceBundle` contract with `retrieval_mode=deterministic_topic_fallback`, `fallback_used=true`, and a non-sensitive warning code.
- [ ] Unknown topics return an empty bundle with a disclosed warning; they never broaden into another topic.
- [ ] Offline application start must not require rebuilding/downloading the embedding model after assets are installed.

#### E. Retrieval evaluation fixture

- [ ] Create at least 40 reviewed retrieval queries: 3+ per topic, multi-topic, irrelevant, ambiguous, and adversarial instruction-containing queries.
- [ ] Record allowed topics and required/acceptable evidence IDs, not expected prose.
- [ ] Test metadata-filter correctness separately from semantic ranking.
- [ ] Test fallback equivalence for topic coverage.

### Required tests

- [ ] Manifest/hash/schema validation passes and deliberate corruption fails.
- [ ] Chunking is deterministic across repeated runs.
- [ ] Metadata filtering prevents cross-topic/jurisdiction retrieval even when fake similarity ranks it first.
- [ ] Every reviewed query returns required evidence in top four; irrelevant queries return empty/disclosed output.
- [ ] Result count never exceeds four.
- [ ] Citations resolve to active manifest chunks.
- [ ] Chroma/model outage uses deterministic fallback and keeps the app usable.
- [ ] Prompt-injection text in a corpus document cannot become a tool/system instruction.
- [ ] No user-data-shaped field exists in collection metadata or committed chunks.
- [ ] Real pinned-model smoke test passes under `real_embedding` marker.
- [ ] All Phase 0–1 and MVP 1 tests remain green.

### Exit gate

- [ ] All 10–15 documents and chunks have recorded human review.
- [ ] Retrieval fixture and real-model smoke results are attached to `docs/verification/mvp2/phase-2.md`.
- [ ] Index rebuild from an empty cache succeeds twice with identical IDs/hashes.
- [ ] Offline fallback demo succeeds with Chroma intentionally unavailable.
- [ ] PR merged and tagged `mvp2-phase-2-done`.

---

## Phase MVP2-3 — Agent Capability, Structured Tools, OpenRouter Runtime, and Budgets

**Independent unit:** a provider-isolated, purpose-routed model runtime where models may return validated structured output or propose allowlisted tool calls, while application code owns authorization and execution.

**Entry criterion:** `mvp2-phase-2-done` is verified on `main`.

**Consumes:** completed contracts, profile read services, and `KnowledgeGateway`.

**Produces:** `ModelGateway`, route/capability registries, strict tool execution, budgets/telemetry, fake/offline gateways, and an evaluated initial route. It does not choose or execute a financial strategy.

### Package layout

```text
mvp2/runtime/
  protocols.py
  model_routes.py
  capabilities.py
  schemas.py
  tool_registry.py
  tool_executor.py
  context_packer.py
  budgets.py
  telemetry.py
  retry.py
  openrouter_gateway.py
  fake_gateway.py
  offline_gateway.py
config/mvp2/
  model_routes.json
  capabilities.json
  prohibited_models.json
tests/mvp2/fixtures/runtime/
tests/mvp2/test_runtime_*.py
```

### Tasks

#### A. Define narrow protocols and results

- [ ] Define `ModelGateway.generate_structured(request) -> StructuredModelResult` and `ModelGateway.request_tools(request) -> ToolProposalResult` protocols.
- [ ] Define typed errors: configuration, unavailable, timeout, rate-limited, authentication, insufficient-credit, schema-invalid, prohibited-model, budget-exceeded, tool-unauthorized, tool-argument-invalid, and tool-result-invalid.
- [ ] Define `AgentCapability` and `ModelRoute` contracts from the architecture.
- [ ] Include request ID, route ID, model slug, prompt version, schema version, reasoning level, fallback route, token budget, cost budget, timeout, and maximum tool calls.
- [ ] Keep financial values out of runtime contracts except opaque/reference-scoped context fields needed by the capability.

#### B. Implement purpose-based route registry

- [ ] Implement the four tiers: `deterministic`, `economy_structured`, `balanced_judgement`, and `high_reasoning_exception`.
- [ ] `deterministic` performs no model call.
- [ ] Configure one primary and at most one evaluated fallback per model-backed capability; do not fan out/vote at runtime.
- [ ] Store exact OpenRouter model slugs in deployment config, never scattered constants.
- [ ] Add a case-insensitive prohibited-model check that rejects names/slugs/aliases containing normalized `fable` or `5.6 sol` in primary, fallback, or environment override.
- [ ] Fail application startup if a configured route is prohibited, missing a budget, references an unknown schema, or uses an unevaluated model.
- [ ] Preserve MVP 1's `complete()` public adapter by delegating it to a compatibility route; baseline offline/numeric behavior must remain unchanged.
- [ ] Never silently substitute a different model slug because a provider is unavailable. Provider routing may select a provider for the same evaluated slug only.

#### C. Implement strict schemas and tool execution

- [ ] Use JSON Schema with `strict=true` where supported, `additionalProperties=false`, explicit required fields, bounded string/list sizes, and enum IDs.
- [ ] Validate model output locally even when the provider reports schema compliance.
- [ ] Define `ToolDefinition` with tool ID, version, description, input schema, output schema, read/write classification, capability IDs, handler, timeout, and maximum result size.
- [ ] The model returns a proposal only. `ToolExecutor` validates route capability, user/session scope, tool allowlist, schema, references, call count, timeout, and budget before calling the handler.
- [ ] Register only tools that exist at this phase: read-only profile/dimension/score/action lookup and reviewed-evidence retrieval.
- [ ] Do not register report, conversation, or scenario tools before their phases.
- [ ] Reject unknown tool IDs, extra arguments, unresolved IDs, oversized values, repeated call IDs, and tool result schema drift.
- [ ] Tool handlers return structured IDs/data, never pre-authorized arbitrary files, SQL, URLs, MCP calls, web search, or code execution.
- [ ] Record tool name, version, argument hash, result reference IDs, timing, and status; do not log arguments/results containing financial values.

#### D. Implement compact context packing

- [ ] Build context from referenced objects only; never send the complete profile/report/transactions by default.
- [ ] Use stable section order: capability instructions → allowed IDs/schema → compact referenced facts → evidence excerpts → user question.
- [ ] Deduplicate references/evidence by ID and cap evidence at four.
- [ ] Enforce per-section and total token estimates before the model call.
- [ ] Reject or deterministically truncate lowest-priority evidence before truncating authoritative facts.
- [ ] Never truncate JSON/schema definitions into invalid forms.
- [ ] Add context-pack hashes and token estimates to sanitized telemetry.

#### E. Implement OpenRouter adapter and resilience

- [ ] Use the existing OpenAI-compatible SDK against the OpenRouter base URL behind `OpenRouterGateway`; domain code never imports the SDK.
- [ ] Read API keys server-side from environment only; never expose them to Streamlit state, logs, fixtures, or exceptions.
- [ ] Apply connect/read/overall timeouts.
- [ ] Retry only 408, 429, and retryable 5xx/transport failures with random exponential backoff and jitter, maximum 3 attempts and a bounded total delay.
- [ ] Honor `Retry-After` when present and inside the total delay budget.
- [ ] Do not retry 400/401/403, insufficient credits, prohibited model, schema failure, validation failure, or budget failure.
- [ ] Track actual input/output tokens and provider cost metadata where available; otherwise calculate an explicitly estimated cost from the release-time pricing snapshot.
- [ ] Reject a response that exceeds configured output tokens, tool calls, or cost.
- [ ] Map failure to an offline/template fallback only where the route declares one; surface a disclosed `capability_status` otherwise.

#### F. Implement budgets and sanitized telemetry

- [ ] Enforce per-call input/output token, cost, latency, and tool-call limits.
- [ ] Enforce per-session request/token/cost and high-reasoning-call limits in Streamlit session state.
- [ ] Add a configurable release/demo daily cap; fail closed when unavailable rather than making unbounded calls.
- [ ] Default high-reasoning traffic ceiling to 5% of model-backed requests and zero for deterministic calculations.
- [ ] Emit sanitized structured telemetry: request/route/model/prompt/schema IDs, token counts, cost, latency, retries, tool IDs, fallback, and error code.
- [ ] Redact keys, messages, financial values, raw evidence, and tool arguments.

#### G. Build initial runtime evals

- [ ] Add at least 30 cases for structured output conformance, prohibited model config, allowed/forbidden tool choice, malformed arguments, extra fields, missing refs, timeout, rate limit, cost overflow, and offline fallback.
- [ ] Use `FakeGateway` scripted results in default tests.
- [ ] Add one `live_model` smoke case for the selected economy candidate with a strict request/token/cost limit.
- [ ] Record the exact selected slug/provider policy, prompt/schema versions, price snapshot date, and eval result.

### Required tests

- [ ] All valid schemas round-trip; every extra/missing/wrong-type field fails.
- [ ] A model proposal cannot execute an unlisted tool.
- [ ] Handler is not called when authorization/schema/reference/budget validation fails.
- [ ] Prohibited names fail regardless of case, whitespace, punctuation, alias, primary/fallback/environment source.
- [ ] No runtime model voting/fan-out occurs.
- [ ] Transient retry count/delay is bounded and non-transient failures do not retry.
- [ ] Offline gateway returns contract-valid fallback results.
- [ ] Context pack excludes raw transactions and unreferenced sections.
- [ ] Sanitized logs contain no fixture financial values or API-key patterns.
- [ ] MVP 1 `complete()` behavior and all earlier tests remain green.
- [ ] Live smoke stays under configured tokens/cost.

### Exit gate

- [ ] Threat review confirms no generic web/SQL/filesystem/code/MCP/write tool exists.
- [ ] Runtime config and live smoke results are attached to `docs/verification/mvp2/phase-3.md`.
- [ ] App starts and runs offline when OpenRouter is absent or disabled.
- [ ] PR merged and tagged `mvp2-phase-3-done`.

---

## Phase MVP2-4 — Constrained Adaptive Strategy

**Independent unit:** select one of three reviewed strategy IDs using deterministic context/retrieved evidence/confirmed preferences, then execute all allocation mechanics deterministically through the single roadmap authority.

**Entry criterion:** `mvp2-phase-3-done` is verified on `main`.

**Consumes:** profile/score/actions/preferences, `EvidenceBundle`, model runtime, and frozen MVP 1 `build_roadmap()` authority.

**Produces:** `StrategyPolicy`, policy-aware `Roadmap`, and `PlanValidation` with visible fallback.

### Package layout

```text
mvp2/strategy/
  contracts.py
  registry.py
  eligibility.py
  deterministic_selector.py
  model_selector.py
  service.py
  validation.py
config/mvp2/policies.json
tests/mvp2/fixtures/strategy/
tests/mvp2/test_strategy_*.py
```

### Tasks

#### A. Extend the one allocation authority safely

- [ ] Add a backward-compatible keyword-only `policy` argument to `utils.roadmap.build_roadmap()` or an equivalent single internal policy hook approved in code review.
- [ ] Calling the function without policy or with `baseline_balanced` must execute the exact frozen MVP 1 code path and output byte-identical structured values.
- [ ] Do not create a second allocator in `mvp2/strategy` or agents.
- [ ] Keep `_AllocationLedger` (or its reviewed successor) as the structural cap so distributed allocation cannot exceed allocatable surplus.
- [ ] Specialists continue to copy allocation amounts; they never inspect policy weights to recalculate money.

#### B. Implement versioned registry

Each `policies.json` entry contains ID, version, eligibility rule ID, action ordering, debt method, deterministic percentages/caps, hard exclusions, and fallback ID. Ship exactly:

1. `baseline_balanced`
2. `starter_buffer_then_avalanche`
3. `snowball_motivation`

Freeze v1 mechanics:

- [ ] `baseline_balanced`: exact MVP 1 waterfall, constants, action IDs, allocation, and debt method.
- [ ] `starter_buffer_then_avalanche` eligibility: valid profile; allocatable surplus > 0; at least one debt; emergency runway below `starter_target_months = min(1.0, configured emergency target)`.
- [ ] Its starter allocation is `min(60% of allocatable_surplus, max(0, starter_target_amount - current_savings))`, where `starter_target_amount = starter_target_months * average_monthly_expenses`.
- [ ] From the ledger remaining after starter allocation, allocate up to 80% to debt using avalanche order, capped by remaining debt balance; then fund goals by frozen goal priority/date order; direct final remainder to savings.
- [ ] It preserves required commitments and minimum buffer because both remain excluded before the policy ledger.
- [ ] `snowball_motivation` eligibility: explicit `debt_payoff_style=quick_wins` and at least two positive-balance debts.
- [ ] It preserves the **exact baseline category allocation amounts** and changes only debt target/payoff ordering from avalanche to snowball.
- [ ] Every policy hard-excludes negative cashflow, invalid/missing required inputs, named products, live law/rate/news use, and unconfirmed preference inference.
- [ ] Registry loading fails on duplicate/unknown IDs, bad percentages, unsupported debt method, missing fallback, cycle, or a fallback other than `baseline_balanced`.

#### C. Implement deterministic eligibility and selector

- [ ] Evaluate policy eligibility deterministically before any model call.
- [ ] If zero/one non-baseline policy is eligible, choose baseline/the sole policy without a model call unless a confirmed preference deterministically resolves otherwise.
- [ ] The deterministic offline selector resolves from confirmed preferences and fixed tie-break rules.
- [ ] The model selector receives compact decision context, at most four evidence excerpts, and allowed eligible policy descriptions.
- [ ] Its strict output is only `strategy_id`, evidence IDs, preference refs, rationale, and selector type—never weights, formulas, amounts, actions, or tool calls.
- [ ] Validate every returned reference. Invalid/ineligible/unknown output immediately uses baseline and records a fallback reason.

#### D. Execute and validate

- [ ] Implement one service call: `select_validate_build(...) -> (StrategyPolicy, Roadmap, PlanValidation)`.
- [ ] Resolve the selected registry entry and call the canonical roadmap authority.
- [ ] Validate policy eligibility again immediately before execution to prevent time-of-check/time-of-use drift.
- [ ] Validate: distributed allocation cap, negative-cashflow zero allocation, minimum commitments, buffer, protected categories, action/metric/finding/risk refs, evidence refs, preference refs, debt order, specialist equality, and policy mechanics.
- [ ] On selection/retrieval/model/policy validation failure, execute `baseline_balanced`, validate again, and disclose fallback code.
- [ ] If baseline validation fails, return a blocking error and do not render/export a plan.
- [ ] Wire this service into the canonical graph **before** roadmap/specialist nodes. Remove/rewrite the old direct roadmap edge; do not preserve two production paths.

#### E. Minimal strategy UI

- [ ] Show applied policy name, general-language rationale, confirmed preference refs, evidence citations, fallback status, and “Why this?” expander.
- [ ] Do not expose internal model chain-of-thought or imply the model calculated the plan.
- [ ] Show that total available money/hard constraints remain unchanged across eligible strategies.

### Required tests

- [ ] Registry schema and cycle validation fail closed.
- [ ] Every eligibility boundary has eligible/ineligible tests.
- [ ] Baseline outputs are byte-identical to MVP 1 across all frozen fixtures.
- [ ] Starter-buffer policy follows the exact 60%/80%-of-remainder/cap waterfall and never exceeds the ledger.
- [ ] Snowball changes order but not category allocation totals.
- [ ] Unconfirmed/skipped preferences have no effect.
- [ ] Invalid model output, unresolved evidence, outage, and ineligible policy use visible baseline fallback.
- [ ] Negative cashflow produces zero distributed allocation under every policy.
- [ ] Hypothesis property tests generate at least 200 valid profiles per policy and preserve all invariants.
- [ ] Specialists/report source objects equal the selected roadmap amounts.
- [ ] Canonical graph has one roadmap/allocation route.
- [ ] All prior tests remain green.

### Exit gate

- [ ] A financial-domain reviewer manually verifies one expected output for each policy and all boundary cases.
- [ ] Golden expected outputs for each non-baseline policy are committed only after review.
- [ ] Offline selector and model/vector outage demos both succeed.
- [ ] `docs/verification/mvp2/phase-4.md` is signed.
- [ ] PR merged and tagged `mvp2-phase-4-done`.

---

## Phase MVP2-5 — Novice Financial Profile and Detailed Audit Report

**Independent unit:** render one immutable analysis as a novice-friendly profile and a fully reproducible algorithm/rule/maths audit without changing any underlying value.

**Entry criterion:** `mvp2-phase-4-done` is verified on `main`.

**Consumes:** validated MVP 1 and MVP 2 profile, dimensions, score, actions, evidence, policy, roadmap, and validation objects.

**Produces:** immutable baseline report, `ReportPresentation` projections, and deterministic `MathExplanation` objects.

### Package layout

```text
mvp2/presentation/
  contracts.py
  baseline_report.py
  profile_builder.py
  projection.py
  formula_registry.py
  math_explanation.py
  reference_resolver.py
  render_markdown.py
  streamlit_views.py
tests/mvp2/fixtures/presentation/
tests/mvp2/test_presentation_*.py
```

### Tasks

#### A. Build one immutable baseline report

- [ ] Define the baseline report as canonical JSON of source object IDs/versions/values plus rendered-independent section data.
- [ ] Compute `baseline_report_hash` from canonical structured content; exclude view mode, generated prose, timestamps, and UI state.
- [ ] Do not mutate or replace MVP 1 `ReportPackage`; wrap/reference it and add MVP 2 sections.
- [ ] Store no second independent copy of calculated values. Projection objects use refs to source values.
- [ ] Validate every metric, dimension, score, goal, action, policy, evidence, calculation, and warning ref before rendering.
- [ ] Refuse to render/export when plan validation is invalid or a critical reference cannot resolve.

#### B. Implement deterministic formula registry

- [ ] Register formulas for every displayed MVP 1 metric, six resilience components/total, policy allocation step, debt payoff result, goal pace/shortfall, and supported scenario-independent projection.
- [ ] Every entry declares calculation ID/version, required inputs, formula text, calculation function ref, unit, period semantics, rounding rule, and allowed explanation template.
- [ ] Generate `MathExplanation` from the same captured calculation inputs/result, not by recomputing from displayed strings.
- [ ] Include substituted values, ordered arithmetic steps, exact pre-round result, displayed result, unit, period, input refs, and plain-language template.
- [ ] Handle division-by-zero and missing inputs as explicit unavailable explanations; never fabricate zero.
- [ ] Add an equality validator that independently evaluates/replays the registered deterministic calculation and compares result/rounding.

#### C. Implement Simple projection

- [ ] Use CRED only as inspiration for compact whole-position cards and progressive disclosure; copy no branding, icons, colors, score scale, wording, or claims.
- [ ] Show: score plus “not a credit/CIBIL score”; overall position; goal progress/set-goal action; up to four highest-priority dimension cards; one primary plus up to two next actions; essential warnings/data limitations; strategy/fallback badge; and “Why this?”/“Show the maths”/“Detailed” controls.
- [ ] Each dimension card shows precise financial term, controlled status, one-sentence meaning, goal effect, action, source period, and data confidence.
- [ ] Critical risks/data limitations cannot be suppressed by card limits.
- [ ] Use INR/currency from the profile and accessible formatting; do not hardcode `$`.

#### D. Implement Detailed projection

- [ ] Show all source metrics with period, currency, source refs, and sufficiency.
- [ ] Show score maxima, component points, formula version, exact formulas, substituted inputs, rounding rules, and missing refs.
- [ ] Show every dimension rule/status threshold that fired.
- [ ] Show goal-impact ordering/trade-offs and every action field.
- [ ] Show policy eligibility, registry version, deterministic allocation ledger, debt order, evidence refs, assumptions, limitations, validation/fallback status, and exact citations.
- [ ] Show algorithms/rules/logic/maths, not a longer unconstrained model opinion.

#### E. Render and export

- [ ] Render Simple and Detailed from the same baseline report hash.
- [ ] Switching view mode changes only section depth/order, never source value/status/action priority/conclusion.
- [ ] Extend Markdown/CSV export to include profile, score components, dimensions, actions, policy/evidence, assumptions, limitations, and educational boundary.
- [ ] Ensure exports label projections/scenarios separately from facts and never claim market prediction.
- [ ] Keep report generation fully offline.

### Required tests

- [ ] Same source objects always produce the same baseline hash.
- [ ] View toggling preserves hash and every value/status/action/reference.
- [ ] Source mutation attempts after report build cannot alter the report.
- [ ] Every formula explanation replays to the exact result, including boundary/rounding cases.
- [ ] Missing/zero-denominator maths returns unavailable, not invented arithmetic.
- [ ] Simple card/action limits hold without hiding critical warnings.
- [ ] Detailed view resolves every reference.
- [ ] No hardcoded dollar symbol appears for INR fixtures.
- [ ] No loose strength/weakness labels appear in user-facing content.
- [ ] Exports reconcile exactly with the rendered baseline.
- [ ] `AppTest` covers Simple/Detailed toggle, “Why this?”, “Show the maths,” offline export, and warning visibility.
- [ ] All prior goldens/tests remain green.

### Exit gate

- [ ] A finance novice reviews the Simple fixture and can identify position, goal, and primary action without assistance.
- [ ] A technical reviewer reproduces score and allocation from Detailed view.
- [ ] Accessibility and mobile-width smoke checks pass.
- [ ] `docs/verification/mvp2/phase-5.md` contains screenshots/hash/reconciliation evidence.
- [ ] PR merged and tagged `mvp2-phase-5-done`.

---

## Phase MVP2-6 — NLP Report Interaction and Suggested Prompts

**Independent unit:** users can ask varied natural-language questions about the immutable report, receive grounded explanations and exact maths, and discover relevant next questions through bounded read-only tools.

**Entry criterion:** `mvp2-phase-5-done` is verified on `main`.

**Consumes:** immutable baseline report/presentation, formula registry, reviewed evidence, and bounded runtime.

**Produces:** `ConversationResponse`, phase-owned report tools, deterministic/model-assisted intent routing, and `PromptSuggestion[]`. It cannot create scenarios yet.

### Package layout

```text
mvp2/conversation/
  contracts.py
  intents.py
  deterministic_router.py
  model_router.py
  tool_handlers.py
  answer_builder.py
  grounding_validator.py
  prompt_suggestions.py
  service.py
tests/mvp2/fixtures/conversation/
tests/mvp2/test_conversation_*.py
```

### Tasks

#### A. Define supported intent registry

Implement exactly these currently available intents:

```text
explain_report_section
explain_metric_or_calculation
explain_financial_dimension
explain_score_component
explain_goal_impact
explain_action_or_policy
retrieve_coaching_evidence
list_suggested_prompts
unsupported_live_or_product_request
```

- [ ] Do not add scenario intents until MVP2-7.
- [ ] Each intent declares required refs, allowed tools, minimum confidence, clarification fields, and fallback template.
- [ ] Deterministic patterns handle explicit section/metric/action IDs, “show the maths,” known report labels, and obvious unsupported current/law/product requests.
- [ ] Use a schema-constrained economy model only when deterministic routing is ambiguous.
- [ ] Below the reviewed confidence threshold, ask one precise clarification rather than guessing.
- [ ] Never infer/modify a financial preference from conversational wording.

#### B. Add read-only report tools atomically

Register these tools only after their handlers and tests exist:

```text
report.get_profile_summary
report.get_dimension
report.get_metric
report.get_calculation
report.get_math_explanation
report.get_action
report.get_goal_impact
knowledge.retrieve_reviewed_evidence
prompt.list_suggestions
```

- [ ] Every handler requires `baseline_report_hash` and checks it against current session baseline.
- [ ] Every handler returns only requested referenced fields and resolving IDs.
- [ ] No tool edits report/profile/preferences/roadmap/session, accesses raw transactions, calls web/SQL/filesystem/MCP, or executes code.
- [ ] Capability allowlists limit each intent to the minimum tools.
- [ ] Tool result sizes, calls, time, tokens, and cost use MVP2-3 budgets.

#### C. Build grounded answers

- [ ] Construct an answer only from returned tool objects/evidence and fixed educational templates.
- [ ] Require every factual/financial sentence to resolve to report, metric, calculation, finding, risk, action, policy, goal, or evidence refs.
- [ ] Use model prose only to simplify/organize grounded content; validate that protected numbers, units, statuses, priorities, and refs are preserved.
- [ ] If grounding validation fails, discard model prose and return a deterministic referenced template with fallback disclosure.
- [ ] For unsupported live law/news/market/FX/rate/product/ticker questions, return `later_capability` and name the missing governed capability without attempting web search.
- [ ] Conversation never changes the baseline report hash or any source object.

#### D. Implement layered maths explanation

When a user asks what a number/equation means:

- [ ] Fetch `MathExplanation` by calculation ref.
- [ ] Respond in this order: plain one-sentence meaning → formula → substituted values → arithmetic steps → result/unit/period → goal impact → linked action → assumptions/limitations.
- [ ] Permit novice follow-ups such as “simpler,” “why divide,” or “what does percent mean” using the same immutable calculation object.
- [ ] The model may simplify wording but cannot add/recompute a value or hide an unavailable input.
- [ ] Include “Detailed” anchor/ref so the user can inspect source data.

#### E. Implement suggested prompts

- [ ] Generate 2–4 candidate prompt IDs deterministically from active goals, highest-priority dimensions/actions, missing-data actions, policy, available evidence topics, and unasked calculations.
- [ ] Rank by goal impact → severity → user-visible novelty → stable prompt ID.
- [ ] Do not suggest a prompt whose capability is unavailable, whose source refs do not resolve, or that implies live search/current portfolio/product advice.
- [ ] Avoid duplicates and avoid repeating the immediately answered intent/ref pair.
- [ ] A cheap model may paraphrase display text only. Intent, source refs, capability, and reason remain deterministic.
- [ ] Provide deterministic text templates for offline mode.

#### F. Integrate chat UI

- [ ] Replace/retire the old keyword-only production chat path; retain no second answer pipeline.
- [ ] Bind chat to the current immutable baseline hash.
- [ ] Show resolving “Based on” links/expanders for report/evidence refs.
- [ ] Show fallback/unsupported status honestly.
- [ ] Display 2–4 clickable suggested prompts after initial report and each completed answer.
- [ ] Clear conversation and suggestions when a new baseline report hash is created; do not apply old refs to a new report.

### Required tests

- [ ] At least 60 routing fixtures cover paraphrases, typos, ambiguous questions, multiple intents, maths follow-ups, and unsupported live/product requests.
- [ ] Deterministic cases never spend a model call.
- [ ] Every answer resolves refs or returns clarification/later/blocked status.
- [ ] Numeric/status/action mutation in model prose is caught and replaced.
- [ ] Prompt injection cannot reveal system prompts, call unauthorized tools, change reports, or bypass unsupported boundaries.
- [ ] Maths answers equal formula-registry results exactly.
- [ ] Suggested prompts are 2–4, unique, resolvable, relevant, and capability-valid.
- [ ] Offline chat and prompt suggestions work.
- [ ] Baseline hash/source objects remain unchanged after arbitrary conversation sequences.
- [ ] `AppTest` covers typed question, clickable suggestion, clarification, maths expansion, unsupported request, and new-report reset.
- [ ] All prior tests remain green.

### Exit gate

- [ ] Human review of at least 25 novice questions confirms understandable, grounded answers.
- [ ] Security review confirms tools are read-only and capability-bounded.
- [ ] Conversation trace/token/cost results are attached to `docs/verification/mvp2/phase-6.md` without financial data.
- [ ] PR merged and tagged `mvp2-phase-6-done`.

---

## Phase MVP2-7 — Immutable Scenario Workspace and Full Streamlit Integration

**Independent unit:** users can create validated, session-scoped what-if scenarios, compare them with the unchanged baseline, discard them, and complete the full integrated MVP 2 journey online or offline.

**Entry criterion:** `mvp2-phase-6-done` is verified on `main`.

**Consumes:** the complete validated baseline pipeline and conversation/runtime capabilities.

**Produces:** `ScenarioRequest`, `ScenarioResult`, scenario tools/intents, baseline comparison, and the final integrated app journey.

### Package layout

```text
mvp2/scenarios/
  contracts.py
  validators.py
  overrides.py
  calculators.py
  runner.py
  comparison.py
  tool_handlers.py
  session_workspace.py
tests/mvp2/fixtures/scenarios/
tests/mvp2/test_scenario_*.py
```

### Tasks

#### A. Add scenario contracts and immutability

- [ ] Implement `ScenarioRequest` and `ScenarioResult` exactly as architecture contracts.
- [ ] Require scenario ID, type, baseline hash, explicit user-confirmed overrides, source, assumptions, and schema version.
- [ ] Deep-copy the canonical source profile, apply an allowlisted override patch, and rerun the same deterministic pipeline.
- [ ] Never mutate Streamlit baseline objects; store scenario objects under a separate session key keyed by scenario ID.
- [ ] Set/validate `baseline_unchanged=true` only after comparing pre/post canonical baseline hashes.
- [ ] Discard/reset deletes session scenario state only and leaves baseline/conversation source untouched.
- [ ] No database, identity, cross-session history, plan promotion, or persistent chat is introduced.

#### B. Implement supported scenario validators/calculators

Support only:

1. income/expense change;
2. monthly buffer change;
3. new debt;
4. generic home-purchase affordability;
5. generic stock-purchase liquidity/goal impact;
6. goal amount/date change.

For each type:

- [ ] Define required/optional inputs, units, numeric ranges, cross-field rules, and missing-input clarification.
- [ ] Reject unknown override fields and non-finite values.
- [ ] Require currency consistency with the profile; MVP 2 performs no FX conversion.
- [ ] Require explicit confirmation before running.

Specific formulas/boundaries:

- [ ] Income/expense: apply monthly amount delta/effective assumption, then recalculate snapshot onward; do not rewrite transaction history as observed fact.
- [ ] Buffer: non-negative amount in profile currency.
- [ ] New debt: positive balance; APR 0–100%; non-negative minimum; positive term; minimum cannot exceed balance without explicit warning/normalization rejection.
- [ ] Home: positive purchase price, `0 <= down_payment <= purchase_price`, annual rate 0–100%, term 1–600 months, non-negative user-supplied monthly ownership costs. Principal is price minus down payment. Monthly rate `r=annual_rate/12`; EMI is `P/n` when `r=0`, otherwise `P*r*(1+r)^n/((1+r)^n-1)`. Include down-payment effect on liquidity separately.
- [ ] Stock: positive purchase amount no greater than available user-confirmed liquid amount; optional assumed annual return is explicitly user supplied and bounded `-100%..100%`; calculate immediate liquidity/goal effect and labelled assumed-value projection only. No ticker, price lookup, selection, buy/sell advice, or prediction.
- [ ] Goal: positive amount, non-negative current amount not silently capped, and date/months in the future; rerun goal feasibility/allocation.

#### C. Run and compare scenarios

- [ ] Recalculate profile validation → snapshot → trends/findings/risks → dimensions/score/actions/context → evidence topics → eligible policy/fallback → deterministic roadmap → specialists/validation → presentation.
- [ ] Reuse the baseline corpus/model route versions unless the user explicitly reruns after a version change; record all versions.
- [ ] Compare metric, component score, dimension status, goal feasibility, action, allocation, warning, and assumption deltas.
- [ ] Label observed baseline, user-supplied assumption, deterministic scenario result, and model explanation distinctly.
- [ ] Never promote/replace baseline. Return a Later-capability message if asked to save/activate as a plan.

#### D. Add scenario intents and tools atomically

Register only after handlers/tests pass:

```text
create_generic_scenario
compare_scenario_to_baseline
list_scenario_assumptions
reset_or_discard_scenario

scenario.validate_request
scenario.run_copy_on_write
scenario.compare_to_baseline
```

- [ ] Router asks for missing required assumptions instead of guessing.
- [ ] Tool executor applies baseline-hash, schema, authorization, count, token/cost, and result-size checks.
- [ ] Model only extracts/clarifies user-supplied fields and explains deterministic results.

#### E. Complete the integrated Streamlit journey

Wire one canonical path in `app.py`:

```text
MVP 1 upload/questionnaire and corrections
-> confirmed profile/goals/constraints
-> optional MVP 2 preferences
-> deterministic profile and decision context
-> governed retrieval
-> policy selection and deterministic validated roadmap
-> novice/Detailed immutable report
-> grounded chat and suggested prompts
-> separate scenario workspace and comparison
-> baseline report/tracker export
```

- [ ] Cache only immutable assets/config/index/model clients; never cache user financial results across sessions.
- [ ] Recompute one canonical baseline when confirmed inputs/preferences change and invalidate dependent report/chat/scenarios.
- [ ] Use one composition root; tabs/components do not independently invoke/recalculate domain services.
- [ ] Show status for offline/model/vector fallback, validation failure, unsupported capability, and stale session refs.
- [ ] Preserve MVP 1 report/tracker downloads and add MVP 2 structured sections without changing baseline numbers.
- [ ] Add accessible loading/error/empty states and prevent double submission/tool execution.

### Required tests

- [ ] Every scenario type has valid, missing, boundary, invalid, and no-goal variants.
- [ ] EMI formula matches independently reviewed examples for zero/non-zero rates.
- [ ] Scenario result equals a direct deterministic rerun with identical override inputs.
- [ ] Baseline hash/values remain unchanged after run, compare, chat, reset, and repeated scenarios.
- [ ] Scenario IDs cannot access another baseline hash.
- [ ] No scenario calls current rates/news/law/market/FX/products.
- [ ] Missing assumptions yield clarification and zero execution.
- [ ] Property tests over at least 200 override sets preserve allocation/score/reference invariants.
- [ ] Full `AppTest` journey passes online-fake and offline modes.
- [ ] Multiple reruns do not duplicate model/tool calls or leak session state.
- [ ] All prior tests/goldens remain green.

### Exit gate

- [ ] Product reviewer completes home, debt, stock-liquidity, and goal scenarios beside an unchanged baseline.
- [ ] Integrated offline journey completes from upload/sample through export and scenario reset.
- [ ] `docs/verification/mvp2/phase-7.md` includes scenario hashes, comparison proof, and UI evidence.
- [ ] PR merged and tagged `mvp2-phase-7-done`.

---

## Phase MVP2-8 — Evaluation, Hardening, Rehearsal, and Release

**Independent unit:** prove the complete MVP 2 is correct, grounded, safe, cost-bounded, regression-free, and repeatably demoable. This phase adds no product capability.

**Entry criterion:** `mvp2-phase-7-done` is verified on `main`.

**Consumes:** complete integrated MVP 2.

**Produces:** frozen eval/golden corpus, promoted model/prompt/skill routes, release evidence, and final tag.

### Tasks

#### A. Freeze reviewed evaluation datasets

Create versioned JSONL datasets under `evals/mvp2/` with unique case IDs, input refs, expected structured outcome/rubric, risk class, and reviewer:

- [ ] at least 40 retrieval cases;
- [ ] at least 36 policy/eligibility/fallback cases;
- [ ] at least 60 intent-routing cases;
- [ ] at least 60 tool-selection/schema/authorization cases;
- [ ] at least 40 maths-explanation cases;
- [ ] at least 36 Goal Planner narrative cases covering single-goal, multi-goal, no-goal, conflicting-goal, missed-goal, negative-cashflow, fallback-policy, missing-data, and adversarial cases;
- [ ] at least 30 suggested-prompt cases;
- [ ] at least 30 grounding/citation cases;
- [ ] at least 30 prompt-injection/data-leakage/unsupported-capability cases;
- [ ] at least 24 scenario extraction/clarification cases;
- [ ] explicit healthy, negative-cashflow, no-debt, no-goal, multi-goal, missing-data, ambiguous, typo, conflicting, and adversarial coverage.

Do not upload real user financial data to an external eval service. Use synthetic/reviewed fixtures with no personal data. Local deterministic evals are authoritative; an external eval service is optional for sanitized language-quality experiments.

#### B. Implement deterministic graders first

- [ ] Schema validity: 100%.
- [ ] Unauthorized tool execution: 0; authorization blocking: 100%.
- [ ] Policy eligibility/ID/fallback correctness: 100%.
- [ ] Allocation/score/formula/reference invariants: 100%.
- [ ] Maths numeric/unit/period equality: 100%.
- [ ] Citation/reference resolution: 100%.
- [ ] Baseline immutability: 100%.
- [ ] Unsupported live/legal/product boundary: 100%.
- [ ] Prohibited-model route detection: 100%.
- [ ] Metadata/topic filter correctness: 100%; required evidence top-four recall: at least 95%, with every miss reviewed.
- [ ] Prompt suggestion capability/source-ref validity: 100%.

No model grader can override a deterministic failure.

#### C. Add human-calibrated qualitative graders

- [ ] Define rubrics for novice comprehension, relevance, concise completeness, faithful explanation, appropriate uncertainty, and helpful next prompts.
- [ ] Have two humans label a calibration subset; resolve disagreements and record rubric examples.
- [ ] Only then evaluate an optional stronger-model grader against human labels.
- [ ] Require at least 90% agreement on pass/fail before using the grader for iteration.
- [ ] Keep the stronger model offline-only for grading language quality; it never judges arithmetic, allocation, schema, authorization, or financial correctness.

#### D. Run the development-only Goal Planner council and judge

This task is wholly owned by MVP2-8 and consumes the completed integrated system plus frozen datasets from this phase. It creates no dependency for MVP2-1 through MVP2-7 and adds no production graph node.

- [ ] Add `evals/mvp2/goal_planner/` fixtures and a development-only harness that fails closed if council/judge mode is enabled in release configuration.
- [ ] Define a strict `GoalPlanNarrative` candidate schema and a strict `GoalPlannerJudgeResult` schema containing case ID, blinded candidate ID, rubric version, integer 1–5 scores, cited spans/reason codes, critical-error flags, confidence, and concise rationale.
- [ ] Give every candidate the identical frozen canonical `Roadmap`, goal order, allocations, actions, assumptions, constraints, references, context limit, and output schema.
- [ ] Compare two to four current allowed OpenRouter candidates; record exact slug, provider policy, prompt/skill/schema versions, reasoning level, token/cost limits, price date, and latency. Never include `Fable` or `5.6 Sol`.
- [ ] Blind candidate identities and randomize output order before judging. The judge receives no model name, provider, price, latency, or unneeded user/profile data.
- [ ] Run deterministic pre-gates first: 100% schema/reference validity; exact amount/unit/period/goal-order/allocation/action equality; complete constraint/assumption/policy/capability adherence; zero invented facts/actions/evidence; and zero omitted or contradicted critical warnings. Exclude any failing candidate from qualitative judging and promotion.
- [ ] Configure the offline judge through `high_reasoning_exception` with temperature zero or the lowest supported deterministic setting, fixed seed where supported, fixed rubric/prompt/schema, no tools, bounded context, and sanitized synthetic/reviewed data only.
- [ ] Score the anchored rubric: goal relevance/prioritization 25%; plan faithfulness 20%; actionability 15%; constraint/assumption communication 15%; grounded rationale 10%; novice clarity 10%; concise completeness 5%.
- [ ] Calibrate on cases labeled independently by two humans and require at least 90% judge/human pass-fail agreement before using judge scores for iteration.
- [ ] Repeat a calibration subset with swapped candidate order; record position-bias and score variance. Require human adjudication for material bias, low confidence, critical-error disagreement, ties, or scores within 0.15 of a promotion boundary.
- [ ] Require weighted mean `>=4.2/5`, every dimension mean `>=4.0/5`, and no case below `3/5` for goal relevance or plan faithfulness.
- [ ] Promote lexicographically: reject every deterministic failure; among qualitative passers choose the cheapest candidate within 0.15 weighted points of the highest score and within route budgets, otherwise choose the highest-scoring in-budget candidate.
- [ ] Configure exactly one Goal Planner production primary and at most one tested fallback. Prove a production request invokes one route once and cannot invoke the council or judge.
- [ ] Store candidate outputs, deterministic grades, judge grades, human calibration labels, bias checks, costs, latencies, selected route, rejected alternatives, and signed decision rationale under `docs/verification/mvp2/phase-8.md` or referenced immutable artifacts.
- [ ] Optionally run a separate post-orchestration qualitative evaluation over the same cases for cross-specialist coherence; it cannot replace or override the deterministic consistency validator.

#### E. Run the prompt/model/skill evaluation flywheel

For each model-backed capability:

- [ ] **Analyze:** inspect failures and label failure modes.
- [ ] **Measure:** run the frozen dataset and record quality, tokens, cost, latency, schema/tool errors, fallback, and stability.
- [ ] **Improve:** change one prompt/skill/context/route variable at a time, assign a new immutable version, and rerun all relevant/cumulative evals.
- [ ] Compare current evaluated candidates from GPT, Claude, Kimi, DeepSeek, or comparable OpenRouter models; never include `Fable` or `5.6 Sol`.
- [ ] Promote the cheapest candidate that clears every hard gate and qualitative threshold.
- [ ] Record one primary and one tested fallback only.
- [ ] Reject a cheaper candidate that misses a hard gate and reject a stronger candidate whose gain does not justify agreed cost/latency.
- [ ] Keep high-reasoning use within the configured exception ceiling.
- [ ] Store model slug/provider policy, prompt/skill/schema versions, reasoning level, catalogue/price date, dataset version, metrics, and decision rationale.

#### F. Token, cost, latency, and failure hardening

- [ ] Verify each route's context contains only referenced necessary sections and no duplicated evidence.
- [ ] Assert p95 input/output tokens and cost are under route budgets.
- [ ] Assert deterministic requests make zero model calls.
- [ ] Simulate timeout, 429, 5xx, malformed JSON, invalid tools, exhausted credits, and provider unavailable.
- [ ] Verify retries/fallback/disclosures and no duplicate tool execution.
- [ ] Verify sanitized telemetry and no financial/secret leakage.
- [ ] Measure offline and online-fake end-to-end latency; fix unbounded waits or repeated index/model initialization.

#### G. Full regression and corruption suite

- [ ] Run all MVP 1 tests/goldens unchanged.
- [ ] Run every completed MVP 2 unit/integration/property/golden/UI/eval test.
- [ ] Corrupt each registry/manifest/schema/hash/reference and prove startup or validation fails closed.
- [ ] Deliberately alter baseline allocation/score/status/action/evidence and prove a golden/eval fails.
- [ ] Test clean install/index build on the supported Python version.
- [ ] Test app with no API key, unavailable vector store, selected model unavailable, and all deterministic fallbacks.
- [ ] Run dependency and forbidden-import scans.
- [ ] Run secret/dependency vulnerability scanning configured for the repository and triage all findings.

#### H. Final demo rehearsal—run twice without correction

Use the same reviewed fixture with high-interest debt, low emergency runway, at least one goal, and an unknown category:

- [ ] Load/confirm data and correct the unknown category.
- [ ] Confirm/skip/reset preferences and show they are never inferred.
- [ ] Show Financial Resilience Score, component maths, exact financial dimensions, goal impact, and primary action.
- [ ] Show `baseline_balanced`, `starter_buffer_then_avalanche`, and eligible `snowball_motivation`; verify hard constraints and available money remain consistent.
- [ ] Resolve “Why this?” to preferences/findings/risks/actions/evidence.
- [ ] Toggle Simple/Detailed and prove baseline hash/values do not change.
- [ ] Ask for the debt-service maths and receive exact substituted steps.
- [ ] Use a suggested prompt and receive a grounded answer.
- [ ] Run home-purchase and stock-liquidity scenarios beside the unchanged baseline.
- [ ] Ask for current law/news/stock advice and receive the Later-capability boundary.
- [ ] Disable OpenRouter and Chroma, repeat the essential journey offline, and export report/tracker.
- [ ] Load negative cashflow and prove zero distributed allocation under every policy/scenario.
- [ ] Confirm no duplicated calls, stale refs, session leakage, unhandled error, manual code edit, or data correction occurred.
- [ ] Repeat the entire rehearsal from a fresh process/session.

### Final exit gate

- [ ] Every deterministic hard threshold is 100% green.
- [ ] Human qualitative thresholds are met and signed.
- [ ] Goal Planner council artifacts prove the promoted primary/fallback passed deterministic accuracy, relevance, bias, quality, token, cost, and latency gates; release configuration proves council/judge mode is impossible.
- [ ] Route token/cost/latency budgets are met.
- [ ] Full offline CI and bounded live release smoke are green.
- [ ] All MVP 1 and MVP 2 goldens pass unchanged.
- [ ] Two full demo rehearsals pass without intervention.
- [ ] Known limitations exactly match MVP 2 scope and are visible to users.
- [ ] `docs/verification/mvp2/phase-8.md` contains the final test/eval/model/cost/demo evidence and accepted commit SHA.
- [ ] PR merged to `main` and tagged `mvp2-phase-8-done` and `mvp2-release`.

MVP 2 is complete only after this gate. Live laws, news, market/FX data, forecasting, named products, portfolio analytics, actual CIBIL integration, persistence, and plan promotion remain blocked by [Architecture Plan - Later.md](Architecture%20Plan%20-%20Later.md).

---

## 4. Phase-to-Architecture Coverage Matrix

This matrix is a completeness check. Every MVP 2 architecture item has exactly one implementation owner.

| Architecture capability | Owning phase | Verification owner |
|---|---|---|
| MVP 1 Phase 11 handoff and byte-identical baseline | MVP2-0 | baseline manifest/regression suite |
| Financial dimensions, resilience score, actions, preferences, decision context | MVP2-1 | deterministic/golden/property tests |
| 10–15 reviewed documents, MiniLM, Chroma, metadata-first top-four retrieval, fallback | MVP2-2 | retrieval fixture + real-model smoke |
| Purpose routes, OpenRouter, strict schemas/tools, denylist, budgets, telemetry | MVP2-3 | runtime schema/security/live smoke |
| Three policies, constrained selection, one deterministic allocator, plan validation/fallback | MVP2-4 | policy goldens/properties/graph test |
| Immutable report, Simple/Detailed, precise financial terms, exact maths | MVP2-5 | hash/reconciliation/formula/UI tests |
| NLP report questions, grounded answers, maths breakdown, suggested prompts | MVP2-6 | routing/tool/grounding/adversarial tests |
| Copy-on-write scenarios, comparison, scenario tools, integrated Streamlit journey | MVP2-7 | scenario properties and end-to-end AppTest |
| Agent/prompt/skill evals, development-only Goal Planner council/judge, token/cost model selection, regression, demo | MVP2-8 | frozen deterministic grades, calibrated relevance scores, promotion record, and release evidence |

If an implementation task does not fit exactly one row, stop and classify it before coding. If it is live, persistent, regulated, portfolio-specific, bureau-sourced, or current-data dependent, move it to Later rather than inserting it into a phase.

---

## 5. Required OpenAI Cookbook References

Use these current official examples for patterns and testing methodology. The production app still calls multiple provider families through OpenRouter; OpenAI-specific API/model names in a notebook are examples, not hardcoded application defaults.

1. [Building resilient prompts using an evaluation flywheel](https://developers.openai.com/cookbook/examples/evaluation/building_resilient_prompts_using_an_evaluation_flywheel) — use analyze → measure → improve, version prompts, and integrate graders into CI.
2. [Eval Driven System Design — From Prototype to Production](https://developers.openai.com/cookbook/examples/partners/eval_driven_system_design/receipt_inspection) — use evals as the core engineering process for quality/cost decisions rather than impressionistic testing.
3. [Evals API Use-case — Structured Outputs Evaluation](https://developers.openai.com/cookbook/examples/evaluation/use-cases/structured-outputs-evaluation) — reference strict JSON schemas and automated structured-output evaluation. The page is archived, so use its method, not its model/API versions.
4. [Evals API Use-case — Tools Evaluation](https://developers.openai.com/cookbook/examples/evaluation/use-cases/tools-evaluation) — reference dataset/rubric/tool-argument evaluation. The page is archived; do not copy obsolete Assistants/model code.
5. [Multi-Tool Orchestration with RAG](https://developers.openai.com/cookbook/examples/responses_api/responses_api_tool_orchestration) — reference the separation between model tool selection, application tool execution, returned context, and final grounded response. MVP 2 uses narrower sequential/read-only tools and does not enable web search.
6. [Robust question answering with Chroma](https://developers.openai.com/cookbook/examples/vector_databases/chroma/hyde-with-chroma-and-openai) — reference corpus loading, metadata, retrieval, and measurable robustness; MVP 2 substitutes pinned open-source MiniLM embeddings and metadata-first filtering.
7. [How to handle rate limits](https://developers.openai.com/cookbook/examples/how_to_handle_rate_limits) — use bounded random exponential backoff with jitter and maximum attempts; do not retry permanent failures.

Before implementing a referenced API pattern, re-open the current page and official SDK documentation. Do not assume an archived notebook's model name, endpoint, beta flag, or parameter remains current.

---

## 6. Final Definition of Done

The implementation is accepted only when a fresh developer can:

1. clone the accepted commit;
2. create a clean environment and install locked dependencies;
3. verify/download the pinned local embedding asset and build the reviewed index;
4. run the complete offline test suite and phase verifier;
5. launch Streamlit without an API key;
6. complete the full MVP 1 + MVP 2 journey;
7. reproduce every score, action, allocation, formula, and scenario delta from structured evidence;
8. see explicit fallback/unsupported boundaries rather than invented current facts;
9. run bounded live model smoke/evals when credentials are provided;
10. obtain the same structured results from the accepted fixtures without modifying code or data.

No unchecked gate, deferred test, undocumented formula, unresolved reference, hidden fallback, or known earlier-stage regression is compatible with “done.”
