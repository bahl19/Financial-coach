# Unified Streamlit UI Implementation Plan

## 1. Purpose and decision

This document defines one Streamlit UI that remains coherent across MVP 1, MVP 2, and Later releases while keeping every completed release independently deployable.

The project does **not** currently have a complete UI implementation plan. UI requirements exist across the architecture and implementation plans, but they do not define one stable UI/backend boundary, feature-visibility rule, state-invalidation model, or staged migration from the current `app.py`.

The adopted design is:

- one stable Streamlit shell and information architecture;
- one versioned UI-facing application contract;
- stage-specific backend adapters and additive screen payloads;
- a capability registry containing only completed, validated features;
- no disabled tabs, placeholders, “coming soon” cards, or navigation for unimplemented features;
- immutable report baselines and copy-on-write exploration;
- release tags at MVP 1, MVP 2, and each approved Later capability boundary.

The UI-facing contract remains backward compatible. Backend domain contracts may evolve, but they must not be exposed directly to Streamlit.

## 2. Source-of-truth precedence

Implementation must honor the following order:

1. `intent.md` for product intent and user trust.
2. `Architecture Plan.md` and `Implementation Plan - MVP 1.md` for the immutable MVP 1 baseline.
3. `Architecture Plan - MVP 2.md` and `Implementation Plan - MVP 2.md` for additive MVP 2 capabilities.
4. `Architecture Plan - Later.md` for governed post-MVP capabilities.
5. This plan for UI composition, compatibility, visibility, and release boundaries.

This plan does not move MVP 2 or Later functionality into MVP 1 and does not alter the phase order in either implementation plan.

## 3. Current UI audit

The current `app.py` is a prototype, not a deployable MVP 1 UI boundary.

| Finding | Current evidence | Required correction |
|---|---|---|
| Retired orchestration path | `app.py` calls `OrchestratorAgent.run_full_report()`, which deliberately raises `NotImplementedError` | Invoke the canonical `finance_calc` → roadmap → graph composition root required by MVP 1 Phase 8 |
| Retired chat path | `app.py` calls `OrchestratorAgent.route_chat()`, which deliberately raises `NotImplementedError` | Route chat through the canonical graph/application service |
| UI performs finance calculations | `app.py` computes cash flow, expense averages, debt totals, category totals, and goal progress | Move all financial calculations and derived display values behind the application contract |
| Hard-coded currency | Money is rendered with `$` | Carry ISO currency and locale-aware display values from the view model; MVP 1 defaults must match the confirmed profile |
| No category-review workflow | Transactions are categorized and analyzed without user confirmation/correction | Add Upload → Review categories → Confirm profile gates |
| Incorrect overview source | Overview concatenates specialist narratives | Render the validated `CoachSummary` as the overview source of truth |
| Missing MVP 1 surfaces | No roadmap, assumptions/constraints, data-quality status, fallback disclosure, canonical scenario path, or required exports | Implement the complete MVP 1 screen sequence before adding MVP 2 UI |
| Unsafe invalidation | Changing income, debt, goals, or assumptions can leave an old report in session state | Centralize dependency-based invalidation and attach every result to an input revision/baseline hash |
| Eager monolithic tabs | One file owns input, execution, calculations, charts, and all tabs | Split a stable shell from screen renderers and render only the selected screen |
| Raw exception disclosure | Exception text is shown directly to the user | Log diagnostic detail and show a safe error code plus recovery action |
| Misleading model health | “Live” indicates client/key construction, not a verified provider/model response | Represent configured, available, degraded, and fallback states separately |

Until the MVP 1 UI gate below passes, the existing app must not be described as MVP 1 complete.

## 4. Stable information architecture

The top-level structure remains stable. Completed later capabilities enrich these screens before creating new top-level navigation.

### 4.1 Setup

MVP 1:

1. Upload CSV or select sample data.
2. Validate columns and display data-quality findings.
3. Review and correct transaction categories.
4. Confirm income, savings, debts, goals, constraints, assumptions, geography, and currency.
5. Run analysis only after validation succeeds.

MVP 2 additions:

- optional preference questions required by the decision policy;
- clear indication of which optional answers are missing;
- no forced re-entry of confirmed MVP 1 facts.

Later additions:

- authenticated profile and connected-account controls;
- reconciliation review queues;
- consent, freshness, provenance, and connection status.

### 4.2 Overview

MVP 1:

- validated Coach Summary;
- current financial health and key facts;
- prioritized goal-supporting actions;
- warnings, assumptions, confidence/fallback status, and data-quality status.

MVP 2 additions:

- Financial Resilience Profile and score;
- financial dimensions such as liquidity, debt serviceability, savings consistency, protection adequacy, diversification, and goal readiness;
- each finding expressed as fact → financial implication → goal impact → action;
- Simple presentation by default, with Detailed presentation using the same underlying result.

Later additions:

- governed current-context changes that materially affect existing actions;
- portfolio and credit summaries only after their complete capabilities are enabled.

### 4.3 Plan

MVP 1:

- deterministic roadmap and ordered actions;
- goal linkage, constraints, assumptions, and tracker progress;
- specialist detail as supporting explanation, not competing summaries.

MVP 2 additions:

- policy decisions and evidence panels;
- score-dimension improvement actions;
- citations and mathematical explanation in Detailed mode.

Later additions:

- governed live-law, market, FX, forecast, portfolio, credit, product, and allocation actions only when their individual release gates pass.

### 4.4 Explore

MVP 1:

- report-grounded questions;
- assumption preview and explicit rerun without mutating the accepted report.

MVP 2 additions:

- suggested prompts based on the confirmed profile, portfolio facts available in the report, and common scenario intents;
- natural-language scenario planning;
- plain-language breakdown of formulas and calculations;
- deterministic topic retrieval over the reviewed coaching corpus;
- evidence, freshness, uncertainty, and abstention disclosures.

Later additions:

- current laws, news, market data, FX, forecasts, product comparisons, and dynamic allocation exploration after their governed data/tools are enabled.

### 4.5 Report

MVP 1:

- downloadable report and tracker generated from the same validated graph result shown on screen;
- offline output with assumptions, constraints, data-quality, and fallback disclosures.

MVP 2 additions:

- Simple and Detailed views of the same immutable analysis;
- evidence and explanation annexes;
- no recomputation when presentation mode changes.

Later additions:

- report history, saved scenarios, reconciliation history, and current-context refresh history after persistence and identity are complete.

### 4.6 Optional Later navigation

New top-level screens may be registered only when their complete capability is useful enough to justify a distinct workflow:

- Portfolio;
- Credit Profile;
- Connections and History.

Current Context, laws, news, FX, forecasts, and product guidance should normally enrich Overview, Plan, and Explore instead of multiplying top-level tabs.

## 5. UI/backend contract

### 5.1 Contract boundary

Streamlit calls one application facade. It must not call agents, calculation modules, retrieval services, provider clients, or persistence repositories directly.

```text
Streamlit shell
    -> ApplicationFacade.execute(command, session_context)
    -> domain/orchestration services
    -> presentation adapter
    -> UiEnvelope
    -> selected Streamlit screen renderer
```

The facade owns orchestration and translation. The UI owns interaction, layout, accessibility, and display only.

### 5.2 Stable response envelope

The following top-level fields remain stable from MVP 1 onward:

```json
{
  "contract_version": "1.0",
  "app_revision": "release identifier",
  "session_revision": 12,
  "release_stage": "mvp1",
  "baseline_ref": {
    "baseline_id": "nullable before analysis",
    "input_hash": "confirmed-input hash",
    "analysis_version": "pipeline version"
  },
  "capabilities": [],
  "navigation": [],
  "screen_payloads": {},
  "notices": [],
  "error": null
}
```

Rules:

- `contract_version` changes major version only for a breaking change.
- New optional fields and new versioned payload types are additive.
- Every screen payload has `payload_type`, `payload_version`, `baseline_id`, and typed data.
- A navigation item must never reference a missing or invalid screen payload.
- Unknown optional payloads are ignored safely; an unknown required payload fails closed with a user-safe error.
- Money carries amount, ISO currency, and a formatted display value. Streamlit must not prepend a currency symbol itself.
- Ratios, scores, chart series, priorities, confidence, provenance, freshness, and explanations are computed before rendering.

### 5.3 Capability manifest

A capability exists in the manifest only after its implementation, tests, documentation, failure behavior, and release gate are complete.

```json
{
  "capability_id": "mvp1.report",
  "capability_version": "1.0",
  "screens": ["report"],
  "commands": ["export_report"],
  "availability": "ready"
}
```

Allowed availability values apply only to implemented capabilities:

- `ready`: usable now;
- `needs_input`: implemented but waiting for user input or confirmation;
- `degraded`: usable with an explicitly disclosed fallback or stale source;
- `blocked`: implemented but unavailable because a runtime prerequisite failed.

There is no `not_implemented` state. Unimplemented capabilities are absent, and their labels, controls, prompts, routes, and placeholders must not be rendered.

### 5.4 Command envelope

All UI writes use versioned commands:

```json
{
  "command_type": "confirm_profile",
  "command_version": "1.0",
  "expected_session_revision": 11,
  "baseline_id": null,
  "payload": {}
}
```

The application facade returns a new `UiEnvelope`. Revision mismatch, invalid state transition, and stale baseline use must fail safely instead of overwriting newer state.

Initial MVP 1 commands:

- `load_transactions`;
- `use_sample_data`;
- `apply_category_corrections`;
- `confirm_profile`;
- `run_analysis`;
- `preview_assumption_change`;
- `accept_assumption_and_rerun`;
- `ask_report_question`;
- `export_report`;
- `export_tracker`.

MVP 2 and Later commands are added only with their owning capability. Existing command semantics must not be changed silently.

### 5.5 Domain evolution strategy

The backend contract should evolve, but the UI-facing envelope should remain compatible:

| Layer | Evolution rule |
|---|---|
| Domain/calculation models | May evolve when architecture phases require it; remain deterministic and tested |
| Agent/graph state | May gain stage-specific nodes and evidence; never exposed directly to Streamlit |
| Application commands | Additive and versioned; old versions remain supported through the active release window |
| Presentation payloads | Additive discriminated payload types with explicit versions |
| Stable UI shell | Reads capabilities and payloads; no stage-specific imports |
| Screen renderers | One renderer per payload type/version; compatibility fixtures required |

Do not create one giant backend object containing speculative fields for all future stages. Add typed payloads when their implementation phase begins.

## 6. Session state and invalidation

Use one typed session container stored in `st.session_state`. Widgets must not become the source of truth.

Required state identifiers:

- `session_revision`;
- `input_revision`;
- `confirmed_input_hash`;
- `baseline_id`;
- `active_screen`;
- `view_mode`;
- references to report, conversation, and scenario results owned by the application layer.

Invalidation is centralized and tested:

| Change | Must invalidate | Must preserve |
|---|---|---|
| Transaction file or category correction | Confirmed profile, baseline analysis, report, tracker, chat, scenarios | UI preferences that remain valid |
| Income, debt, savings, geography, currency, constraints, or assumptions | Baseline analysis, report, tracker, chat, scenarios | Validated transaction data |
| Goal change | Roadmap, priorities, report, tracker, chat, scenarios | Confirmed financial facts |
| MVP 2 preference change | Dependent policy/evidence decisions, roadmap, report, chat, scenarios | MVP 1 financial facts |
| Simple/Detailed mode | Nothing financial | Entire immutable baseline |
| Chat question | Nothing in baseline | Report and other conversations |
| Scenario creation/edit | Only that scenario result | Accepted baseline and other scenarios |
| Later live-context refresh | New context snapshot and dependent preview | Accepted baseline until explicit rerun |

Every report, chat answer, export, and scenario must carry its `baseline_id`. A stale result must not be rendered as current.

## 7. Streamlit implementation structure

Create the following modules during the owning MVP 1 UI phase; do not create empty MVP 2 or Later stubs:

```text
app.py                         # composition and launch only
ui/
  contracts.py                # UI envelope, commands, payload protocols
  application_facade.py       # only backend entry point used by Streamlit
  capability_registry.py      # completed capabilities only
  session.py                  # typed session access and revisions
  invalidation.py             # dependency invalidation rules
  navigation.py               # capability-driven navigation
  formatting.py               # non-financial presentation formatting
  components/
    status.py
    evidence.py
    money.py
    errors.py
  screens/
    setup.py
    overview.py
    plan.py
    explore.py
    report.py
```

Implementation rules:

- `app.py` selects one screen; it does not eagerly execute every tab.
- Use dynamic navigation built from the manifest, such as a sidebar or top-level radio control.
- Screen modules render typed view models and emit commands only.
- Screen modules contain no financial formulas, categorization, aggregation, scoring, forecasting, or agent routing.
- Cache immutable resources with `st.cache_resource` and safe pure data with `st.cache_data`; never globally cache user-specific mutable results.
- Do not expose secrets, prompts, provider payloads, stack traces, or internal exceptions.
- Use forms for multi-field confirmation so reruns do not submit partial profile state.
- Expensive work runs only on explicit user actions.
- Use stable widget keys based on screen, capability, entity identifier, and version.

## 8. Phase-wise UI implementation

These phases follow the existing implementation plans. They do not authorize starting MVP 2 before the MVP 1 release gate passes.

### UI Phase 1 — MVP 1 contract and shell

Owning work: MVP 1 Phase 7 report contracts and Phase 8 UI integration.

Checklist:

- [ ] Define and test `UiEnvelope`, command, capability, notice, error, and screen payload types.
- [ ] Implement the application facade over the canonical MVP 1 composition root.
- [ ] Remove Streamlit's dependency on `OrchestratorAgent` and direct domain modules.
- [ ] Create typed session revisions, baseline references, and centralized invalidation.
- [ ] Create capability-driven navigation containing only MVP 1 screens.
- [ ] Implement safe error mapping and runtime availability/fallback notices.
- [ ] Add contract fixtures for empty, needs-input, ready, degraded, and blocked MVP 1 states.

Exit gate:

- [ ] Streamlit imports only the UI application facade and UI contracts.
- [ ] No renderer performs financial calculations or direct agent/provider calls.
- [ ] Contract and invalidation tests pass.
- [ ] No MVP 2 or Later capability, label, route, or placeholder exists in the MVP 1 artifact.

### UI Phase 2 — MVP 1 complete user journey

Owning work: MVP 1 Phase 8.

Checklist:

- [ ] Implement Setup upload/sample, validation, category review, and profile confirmation.
- [ ] Prevent analysis until required validation and confirmations pass.
- [ ] Implement Overview from the validated Coach Summary.
- [ ] Implement Plan from the deterministic roadmap and specialist support data.
- [ ] Implement Explore for report-grounded chat and copy-on-write assumption preview/rerun.
- [ ] Implement Report preview and validated report/tracker downloads.
- [ ] Render currency, geography, assumptions, constraints, data quality, provenance, and fallback status correctly.
- [ ] Ensure every displayed result and export matches the active baseline.

Exit gate:

- [ ] The complete MVP 1 golden path works in offline and configured-model modes.
- [ ] Category corrections and profile changes visibly affect a newly generated report.
- [ ] The Overview equals the Coach Summary source of truth.
- [ ] Scenario/chat activity cannot mutate the accepted report silently.
- [ ] Exports are generated from the same graph result shown in the UI.

### UI Phase 3 — MVP 1 regression, accessibility, and release

Owning work: MVP 1 Phases 9–11.

Checklist:

- [ ] Add Streamlit `AppTest` coverage for the golden path and all state transitions.
- [ ] Add capability-absence tests for MVP 2 and Later labels.
- [ ] Add stale revision, stale baseline, invalid upload, provider failure, and export-failure tests.
- [ ] Add tests for rerun behavior, stable widget keys, duplicate-submit prevention, and session isolation.
- [ ] Verify readable mobile/desktop layout, keyboard navigation, labels, contrast, and non-color status cues.
- [ ] Verify no sensitive values appear in logs, errors, or downloadable diagnostics.
- [ ] Run all MVP 1 regression and release gates from the implementation plan.

Release boundary: **MVP 1 deployable**. If time stops here, this artifact is complete and contains no partial MVP 2 UI.

### UI Phase 4 — MVP 2 additive profile and policy surfaces

Owning work: MVP 2 Phases 1–5. Backend phases continue sequentially; the stable MVP 1 UI remains deployable during the work.

Checklist:

- [ ] Add preference commands and Setup payloads only after MVP 2 Phase 1 passes.
- [ ] Preserve confirmed MVP 1 facts when optional preference input changes.
- [ ] Register evidence components only after corpus validation, retrieval, citation, and abstention gates pass.
- [ ] Register policy-decision explanation components only after deterministic policy gates pass.
- [ ] Add the Financial Resilience Profile, score, financial dimensions, goal impacts, and actions after scoring/diagnostic gates pass.
- [ ] Implement Simple and Detailed renderers over the same immutable baseline.
- [ ] Ensure changing presentation mode performs no analysis, retrieval, scoring, or LLM call.
- [ ] Add evidence, formula, provenance, confidence, freshness, and limitation panels to Detailed mode.

Exit gate:

- [ ] All new screen payloads are additive and versioned.
- [ ] MVP 1 contract fixtures still render correctly.
- [ ] No incomplete chat/scenario or Later control is visible.
- [ ] MVP 1 regression suite remains green.

### UI Phase 5 — MVP 2 grounded interaction and scenarios

Owning work: MVP 2 Phases 6–8.

Checklist:

- [ ] Upgrade Explore to grounded report Q&A using structured intent and tool-call results.
- [ ] Add profile- and report-aware suggested prompts with deterministic eligibility rules.
- [ ] Add plain-language formula breakdown linked to the actual calculation inputs and outputs.
- [ ] Display evidence citations, source dates, confidence, retrieval status, and abstention reasons.
- [ ] Implement natural-language scenario creation as copy-on-write state.
- [ ] Display a clear baseline-versus-scenario comparison.
- [ ] Require explicit acceptance and full rerun before a scenario can become a new baseline.
- [ ] Add token-aware context and model-route diagnostics to internal observability, not the user report.
- [ ] Complete AppTest, contract compatibility, adversarial, regression, and release tests.

Release boundary: **MVP 2 deployable**. If time stops here, MVP 2 is complete and no Later capability is advertised.

### UI Phase 6 — Later capability slices

Owning work: the priority order and gates in `Architecture Plan - Later.md`.

Each Later feature is a separate additive release slice. A slice must include its data contract, service/tool integration, provenance/freshness behavior, UI payload, renderer, failure state, tests, documentation, and rollback plan before registration.

Checklist for every slice:

- [ ] Complete the owning Later backend/data/governance gate.
- [ ] Define an additive command and/or payload version.
- [ ] Define authorization, consent, freshness, provenance, and degraded behavior.
- [ ] Implement the renderer without changing existing payload semantics.
- [ ] Add capability-presence and capability-absence tests.
- [ ] Run the entire MVP 1 and MVP 2 regression suites.
- [ ] Register the capability only after all checks pass.
- [ ] Tag and deploy the independently rollbackable release.

## 9. Later priority-to-UI map

| Later capability | Preferred UI location | Registration condition |
|---|---|---|
| Identity, persistence, consent, audit | Setup plus Connections and History when warranted | Authentication, tenant isolation, consent, retention, migration, and audit gates pass |
| Comprehensive reconciliation | Setup review queue and Report data-quality section | Deterministic matching, duplicate handling, correction audit, and regression gates pass |
| Live laws and regulatory context | Overview change notice, Plan evidence, Explore Q&A | Approved sources, jurisdiction/as-of controls, citations, freshness, conflict handling, and abstention pass |
| Market news and event context | Overview material-change notice and Explore | Entity relevance, source quality, event-time handling, deduplication, and non-advisory controls pass |
| Live market data and FX | Overview facts, Plan assumptions, Explore | Licensed/approved source, timestamp, currency basis, stale fallback, and reconciliation pass |
| Forecasting | Plan and scenario comparison | Backtesting, calibration, uncertainty intervals, monitoring, and no-certainty-language gates pass |
| Portfolio analytics | Overview summary, Plan detail, optional Portfolio screen | Holdings normalization, benchmark/risk metric correctness, evidence, and suitability boundaries pass |
| Credit profile/bureau integration | Overview summary and optional Credit Profile screen | Consent, identity match, bureau terms, explainability, dispute path, and security gates pass |
| Product advice/comparison | Plan and Explore | Product data governance, suitability, fee/risk comparison, conflicts disclosure, and jurisdiction gates pass |
| Dynamic allocation | Plan and scenarios | Suitability, constraints, deterministic guardrails, auditability, and explicit acceptance pass |
| Durable conversation memory | Explore and History | Scoped memory, consent, retention/deletion, provenance, and baseline isolation pass |
| Production observability/evals | Internal operations only | Privacy-safe telemetry, traceability, evaluation thresholds, cost/token budgets, and incident controls pass |

## 10. Verification matrix

Every deployable boundary must pass:

- unit tests for contracts, formatting, navigation, invalidation, and render helpers;
- application-facade integration tests against deterministic fixtures;
- Streamlit `AppTest` journeys for each registered capability;
- backward-compatibility tests using retained MVP 1 and MVP 2 envelopes;
- absence tests proving future features are not rendered;
- baseline immutability and session-isolation tests;
- offline, degraded-provider, stale-source, and malformed-response tests;
- report/UI equality tests for important metrics, actions, evidence, and disclosures;
- full earlier-stage regression suites;
- manual smoke test from clean session to export on the deployment artifact.

No UI phase is complete when its code merely renders. Complete means its contract, state transitions, failure behavior, accessibility, tests, regression gate, and deployment smoke test are validated.

## 11. Deployment and rollback

- Build and deploy only from a validated release tag.
- Keep the latest validated MVP 1 artifact available until MVP 2 passes its full release gate.
- Keep the latest validated MVP 2 artifact available while Later slices are developed.
- Do not use runtime flags to make incomplete future features appear complete.
- A feature registry may select among capabilities that are fully implemented in the deployed artifact; it must not conceal unfinished code as a substitute for a release gate.
- Database or persistence changes introduced Later require backward-compatible migrations and a tested rollback path before UI registration.
- Rollback restores the last validated artifact and contract version without corrupting saved baselines.

## 12. Definition of a unified UI

“Unified” means the user keeps the same product structure, interaction vocabulary, baseline rules, and visual hierarchy as capabilities mature. It does **not** mean shipping future placeholders in MVP 1 or forcing all future backend fields into the first contract.

The final compatibility rule is:

> Keep the UI envelope and core navigation stable; evolve backend services and screen payloads additively; register and display only capabilities that are implemented, validated, and safe for the active release.
