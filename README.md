# 💰 AI Financial Coach — Multi-Agent Financial Advisor

> Every rupee is computed deterministically. The LLM only narrates.

AI Financial Coach turns a bank statement (CSV/PDF), a handful of debts, and a few goals into a **prioritized, numbers-backed action plan** — not just another dashboard. A LangGraph pipeline of specialist agents each reasons over a grounded slice of the user's real numbers (spending, debt payoff, savings targets, budget fit, goal feasibility), and a single deterministic allocator decides where the surplus actually goes.

**🔗 Live app: [financialcoach.streamlit.app](https://financialcoach.streamlit.app/)**

Current state: **MVP 1 complete** (tag `phase11-done`) plus **MVP 2 Phase 0** (tag `mvp2-phase-0-done`, tooling + regression baseline only). See [What's deferred](#-whats-deferred) for everything that is planned but deliberately not built yet.

---

## 🧭 Core design decisions

1. **Compute/narrate split.** `utils/finance_calc.py` (the "tabular RAG" layer) produces *every* number — spending totals, payoff schedules, savings projections, budget deltas. Specialist agents hand those already-computed figures to an LLM purely for phrasing. No LLM output ever becomes a dollar amount.
2. **Single allocator.** `utils/roadmap.py` is the *only* place surplus money is allocated. Its `_AllocationLedger` waterfall runs: protected buffer → starter emergency buffer → high-APR debt acceleration → goals by priority → remainder to savings or investments. No agent can spend the same rupee twice.
3. **Consistency validation.** `utils/validation_structured.py` (authoritative) and `utils/validation_prose.py` (heuristic) cross-check every narrative against the numbers that produced it; a drifting narrative is replaced with that agent's deterministic fallback before display.
4. **Explainable orchestration.** A LangGraph `StateGraph` with explicit dependency edges (Savings waits on both Spending *and* the Roadmap) instead of one mega-prompt. Every node is testable in isolation.
5. **Offline-first.** With no `OPENROUTER_API_KEY`, every agent falls back to a rule-based templated narrative built from the same numbers. The full journey — including the report export — works with zero credentials.
6. **Region/currency aware.** Categorization keywords, benchmark rates (FD/PPF/SIP), and currency symbols are independently configurable. India/INR is the default.

---

## 🏗️ Current architecture

```
Upload CSV/PDF  ─┐
Load sample data ┴─> agents/data_agent.py      column aliasing (CSV) / pdfplumber+regex (PDF)
                     utils/ingestion.py        region keyword categorization + confidence
                       ↓  low-confidence rows surfaced in an editable review table
                     utils/contracts.py        validate_profile() gates the "Run analysis" button
                       ↓
                     utils/finance_calc.py     snapshot · health score · trends · findings · risks
                       ↓
                     agents/graph.py           LangGraph StateGraph
                       ├─ Stage A (parallel):  spending_agent   ·   build_roadmap  ← sole allocator
                       ├─ Stage B (fan-out):   budget · savings · debt · goal agents
                       ├─ Stage C:             validation (structured + prose, with fallback swap)
                       └─ Stage D:             utils/coach.py — ranked summary, max 3 priorities
                       ↓
                     Streamlit tabs · what-if scenarios · utils/reporting.py → Markdown + CSV tracker
```

### Agents

| Agent | Grounded on | Produces | Allocates? |
|---|---|---|---|
| 📥 Data Ingestion | Uploaded CSV/PDF | Clean, categorized transaction table | — |
| 🧾 Spending Analyzer | Categorized transactions | Category totals, monthly cash flow, trend flags | No |
| 💳 Debt Analyzer | Debts (balance, APR, min payment) | Avalanche vs. snowball simulation with real interest/timeline | Mirrors roadmap |
| 🏦 Savings Strategist | Income, expenses, savings, APY/CAGR | Emergency-fund target, 24-month projection | Mirrors roadmap |
| 📋 Budget Advisor | Income, actual split | Actual vs. 50/30/20 with per-bucket variance | No |
| 🎯 Goal Planner | Goals + surplus | Required monthly contribution and feasibility, **per goal** | Mirrors roadmap |
| 🧭 Roadmap Allocator | All of the above | The prioritized action list — **the only allocation authority** | **Yes** |

`agents/base.py` is a template method: build a grounded summary → ask the LLM → on `None`, use `_fallback_narrative()`. Every specialist returns the same `SpecialistResult` shape.

`agents/orchestrator.py` is no longer an agent — it is keyword routing (`match_routes`) plus `build_chat_reply()`, which stitches together narratives already in the graph result. **The chat tab makes no second LLM call**, so answers can never contradict the report.

### Modules

| Module | Role |
|---|---|
| `utils/contracts.py` | Leaf module. All `TypedDict` schemas, enums, `validate_profile()`. Imports nothing project-specific. |
| `utils/finance_calc.py` | All deterministic math, incl. `calculate_health_score` (30/30/25/15 weights). No LLM. |
| `utils/ingestion.py` | Tolerant boundary: region keyword tables, confidence scoring, 5 data-quality checks. |
| `utils/roadmap.py` | The allocation waterfall. LLM used for prose only. |
| `utils/validation*.py` | Structured (6 checks) + prose (3 checks) tiers, plus remediation. |
| `utils/coach.py` · `reporting.py` · `scenarios.py` | Ranking · formatting · immutable what-if comparison. |
| `utils/llm.py` | OpenRouter via the `openai` SDK. Returns `None` on any failure — never raises. |
| `utils/auth.py` | Logto OIDC through Streamlit's native `st.login()`/`st.user`. Fails closed. |
| `utils/app_state.py` | The only session-state reader/writer; invalidates stale analysis on any upstream edit. |
| `utils/theme.py` · `landing.py` · `currency.py` · `region.py` | Brand theming, landing page, INR/USD, India/generic benchmarks. |

### App flow

`app.py` is one linear Streamlit script (no `pages/`), gated by `st.stop()`:

**Landing page → sign-in → upload/sample → review categories → confirm details → 7 analysis tabs → 5 scenario tabs → download report.**

---

## 🚀 Quick start

```bash
git clone https://github.com/bahl19/Financial-coach.git
cd Financial-coach
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # optional — see below
streamlit run app.py
```

Open **http://localhost:8501**, click **"Load sample data"** for an instant demo, or upload your own CSV/PDF.

### LLM key (optional)

```
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_MODEL=anthropic/claude-sonnet-4.5
```

No key? Every agent uses its rule-based fallback narrative. Only the prose changes — never a number.

### Sign-in (Logto)

**Sign-in fails closed.** With no `[auth]` block configured, the app stops on an explanatory screen rather than serving itself to everyone. To run locally without configuring sign-in, set `FC_ALLOW_ANONYMOUS=true` in `.env`. **Never set that on a public deployment.**

To enable real sign-in: copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml` (gitignored) and fill in `client_secret` and `cookie_secret`. Keep the `client_kwargs = { prompt = "login" }` line — Streamlit otherwise sends `prompt=select_account`, which Logto rejects, and the Sign in button silently bounces back. Needs `Authlib>=1.3.2` (already in `requirements.txt`); an older virtualenv will raise at click time even though everything else looks configured.

**Deploying:** set the same `[auth]` block in Streamlit Community Cloud → *Settings* → *Secrets*, with `redirect_uri` pointing at your deployed URL's `/oauth2callback`.

---

## 🧪 Tests & checks

```bash
python -m pytest -q -m "not live_model and not real_embedding" --strict-markers
python -m ruff check .
python -m mypy utils agents          # add mvp2 once that package exists
python scripts/verify_mvp2_phase.py --phase 0
```

**445 tests** across 21 files. Notable coverage:

- `tests/test_app.py` — full sample journey driven by `streamlit.testing.v1.AppTest`, incl. the landing gate, auth gate, fail-closed behavior, and a test that the repo never ships a secrets file.
- `tests/test_golden.py` + `fixtures/golden/` — 3 end-to-end scenarios frozen as ID/severity/allocation projections (narratives deliberately excluded, so rewording doesn't break them).
- `tests/test_properties.py` — Hypothesis invariants.
- `tests/test_graph.py` — asserts the LangGraph result matches `run_pipeline_direct()`, so the graph can't silently drift from its documented sequential equivalent.
- `tests/mvp2/test_mvp1_regression.py` — the frozen MVP 1 baseline (manifest hashes, health scores, byte-reproducible reports) *plus negative tests that mutate a cent and assert the regression fails*.
- `tests/mvp2/test_dependency_boundaries.py` — AST import-boundary enforcement: no domain module may import `streamlit`/`openai`/`chromadb` outside the named adapters, nothing may import `app`, and the planned `mvp2.*` dependency graph is enforced ahead of the package existing. Planted-offender tests prove the scanners aren't vacuous.

CI (`.github/workflows/ci.yml`, Python 3.13) runs install → ruff → mypy → the offline suite with an empty API key → `git diff --check`.

---

## 📊 Data contract

**Transactions CSV** — `date`, `description`, `amount` (**expenses negative, income positive**). Column aliases accepted: `transaction date`/`posted date`, `memo`/`merchant`/`name`, `amt`/`value`. PDF statements are parsed with pdfplumber against a `dd/mm/yy · description · ₹|$|Rs amount` line pattern.

**Debts** — `{ "name": "Credit Card", "balance": 4200.0, "apr": 22.9, "min_payment": 120.0 }`
**Goals** — `{ "name": "Hawaii Vacation", "amount": 4000.0, "months": 10, "current": 200.0 }`

Both are edited inline in a data table during Step 3.

---

## 🛠️ Tech stack

Streamlit · LangGraph (`StateGraph`) · OpenRouter via the `openai` SDK (model-agnostic, optional) · pandas/numpy · pdfplumber · Plotly · `TypedDict` contracts · pytest + Hypothesis + `AppTest` + golden fixtures · ruff + mypy · Logto (OIDC).

---

## 🔭 What's deferred

Everything below is **planned and specified, but deliberately not implemented yet**. It is documented here so the current scope reads as a choice, not an omission. Full specs live in `Docs imp/`.

### MVP 2 — RAG-assisted constrained adaptive strategy

Phase MVP2-0 (tooling, regression baseline, CI, dependency-boundary enforcement) is **done**. The `mvp2/` package intentionally does not exist yet — the boundary tests already guard the shape it will take.

| Phase | Scope | Status |
|---|---|---|
| MVP2-1 | Financial Position Profile: 7 dimensions, 0–100 **Financial Resilience Score**, goal-aligned actions, user-confirmed preferences, `DecisionContext`. No retrieval, no model call. | Next up. A 2-hour priority cut (6 score-owning dimensions, no preference UI) is planned in `Implementation Plan - MVP 2 Priority.md`; the 7th dimension, preference UI, exhaustive boundary tests, and 200-example property runs remain deferred within it. |
| MVP2-2 | Reviewed 10–15 document corpus, open-source embeddings in local ChromaDB, deterministic topic/metadata filtering. **RAG supplies evidence, never numbers.** | Not started |
| MVP2-3 | Agent capability layer: schema-constrained tools, purpose-based OpenRouter model routes, per-route token/cost budgets. | Not started |
| MVP2-4 | Constrained adaptive strategy: a three-policy allowlist where the model may return only a `strategy_id`; a checked-in registry owns all executable behavior, with `baseline_balanced` fallback. | Not started |
| MVP2-5 | Dual-depth reporting — a Novice profile view and a Detailed audit view with exact maths explanations — resolving to the same immutable report version. | Not started |
| MVP2-6 | Grounded NLP interaction over the report + profile-derived suggested prompts. | Not started |
| MVP2-7 | Immutable session-scoped scenario workspace (copy-on-write overrides; the baseline report can never be mutated). | Not started |
| MVP2-8 | Offline prompt/skill/model eval gates, hardening, release rehearsal. | Not started |

### Later — production

Not started, and explicitly out of scope for the prototype timebox; each item adds operational and privacy obligations disproportionate to a demo.

- **L0 Persistent identity & audit** — managed auth is done (Logto, moved up early); internal principal/case IDs, consent & retention records, PostgreSQL versioned contracts, private object storage, tenant isolation, export/delete workflow, and immutable audit events are all still deferred. **Nothing currently stores per-user data.**
- **L1 Document reconciliation** — institution adapters, opening/closing balance reconciliation, internal-transfer pairing, duplicate/reversal handling, holdings & cost basis, row-level provenance.
- **L2 Governed rules** — versioned, jurisdiction-scoped tax/regulatory rules with effective dates and human approval.
- **L3 Structured market data** — licensed market/macro/rate/FX feeds with observation timestamps and source vintage.
- **L4 Portfolio analytics** — valuation, allocation, concentration, risk-adjusted return, fee drag, liquidity.
- **L5 Governed news** — allowlisted publishers producing expiring context alerts. **News may never allocate money.**
- **L6 Forecasting** — calibrated scenarios with prediction intervals, backtesting, and a deterministic baseline.
- **L7 Credit bureau** — consented, authorized bureau data shown *beside* — never blended into — the resilience score. The Coach must never imitate the CIBIL 300–900 scale or reconstruct a bureau score.
- **L8 Regulated product advice** — named loan/fund/stock guidance, gated on jurisdiction capability, suitability, disclosures, and licensed approval. Disabled by default.
- **L9–L12** — expanded dynamic allocation, production conversational gateway, model/prompt governance, resumable workflows and operations.

**The invariant across every deferred phase:** retrieval, news, forecasts, and models may influence *which* pre-approved deterministic policy runs and *how* it is explained. They may never define a policy, compute a number, or move money.

---

## ⚠️ Notes & known limitations

- Auto-categorization is keyword-based (`utils/ingestion.py`, region-layered) — uncommon merchants fall back to `Other` and are surfaced in the review table for correction.
- The Budget Advisor normalizes all-time spending to a monthly average before comparing to 50/30/20, so partial months don't skew the split.
- Debt payoff rolls freed-up minimum payments into the next target debt, matching how avalanche/snowball are conventionally defined.
- No persistence: reload the page and the session is gone. This is deliberate until L0.
- `budget_agent.py` hardcodes `₹` in its prompt/fallback rather than using `format_money` — a known USD-path wart.
- `UI/` holds the original design-tool export; only `UI/assets/app-demo.mp4` is consumed at runtime. `utils/landing.py` rebuilds the landing page in Streamlit primitives because `components.v1.html` iframes would break relative asset paths.
- Single-reviewer verification throughout (solo project) — disclosed rather than smoothed over, and carried forward in every phase's evidence document under `docs/verification/`.

---

## 👨‍💻 Built by

C8 | Hackathon Group 13 · [github.com/bahl19](https://github.com/bahl19)

> "Your income, spending, and debt — turned into a plan, not just a dashboard."
