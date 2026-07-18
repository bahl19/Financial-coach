# Gap Analysis: Implementation Plan vs. Architecture Plan and Review.md

**Date:** 2026-07-18
**Scope reviewed:** [`Implementation Plan - MVP 1.md`](Implementation%20Plan%20-%20MVP%201.md) against [`Architecture Plan.md`](Architecture%20Plan.md) and [`Review.md`](Review.md)
**Review lens:** (a) strict sequential phasing — no phase may depend on a later phase; (b) coverage of `Review.md`'s Critical tier; (c) consistency between the two plan documents.

**Status: 12 gaps found — 3 blocking, 5 high, 4 medium. ALL RESOLVED 2026-07-18.** Two of the blocking gaps shared a single root cause (`Review.md` item 14 was triaged as Critical but never converted into a task), so fixing that one item resolved both.

## Resolution Summary

All 12 gaps are fixed in `Architecture Plan.md`, `Implementation Plan - MVP 1.md`, and `Architecture Plan - MVP 2.md`. The sections below are retained as the rationale record — read them to understand *why* a change was made, not as outstanding work.

**A scope decision was made during the fix that resolves B1 and B2 structurally rather than patching them:** the Strategy Policy Layer was **removed from MVP 1 entirely** and returned to MVP 2, per the instruction that MVP 1 be an independent, fully tested product with no mixed implementations. This aligns with `Review.md` item 25 and eliminates the optional Phase 6 whose existence was the *sole cause* of the forked phase chain (B1) and the ambiguous skipped-tag problem (B2). MVP 1 is now a strictly linear 12-phase chain, 0 → 11, with no optional or skippable phase.

| ID | Resolution |
|---|---|
| A1 | Bad gate item removed from Phase 1; replaced with a verifiable `allocatable_surplus` formula check. Invariant now lives only in Phase 3's gate and Component 4's acceptance checks. Fixed at source in `Architecture Plan.md` Component 3. |
| A2 | Phase 4 rewritten: 6 authoritative **structured** checks over `SpecialistResult` fields + 3 explicitly best-effort prose checks. The 5 undeliverable checks are gone. |
| A3 | Phase 0's dangling "from Phase 9" reference repointed to the new Phase 6 (Golden Fixture Freeze). |
| B1 | Resolved structurally — Phase 6 (Strategy Policy) removed. Rule 5 now states the chain is strictly linear with no optional phases. |
| B2 | Resolved structurally — no skippable phase remains, so no `phase6-skipped` tag convention is needed. |
| C1 | `SpecialistResult` contract added to `Architecture Plan.md` and Phase 0; the producing task added to Phase 3 for all five agents, with a gate item requiring `allocated_amount` be copied from `roadmap.allocation`. |
| C2 | New **Phase 6 — Golden Fixture Freeze** added after Coach Synthesis, with a mandatory manual-review step and a second-person sign-off on the negative-cashflow case. Golden *inputs* stay in Phase 0; *expected outputs* are frozen in Phase 6. |
| C3 | Property-based tests (`hypothesis`) added to Phase 9 with 5 named invariants; `hypothesis` added to Phase 0's dev dependencies. |
| C4 | **Decided: Option A.** The waterfall stays severity-independent. Documented as a deliberate divergence in `Architecture Plan.md` Component 4 and Phase 3; item 4's "control roadmap priority" half moved to the Important tier. |
| C5 | `detect_data_quality_issues()` added to Phase 1 / Component 2 with 5 cheap checks; `data_quality_flags` added to the `FinancialSnapshot` contract; Phase 2's data-quality finding type now has a real producer. |
| C6 | `agents/orchestrator.py` cleanup added to Phase 3's task list, with a `grep` gate item confirming the 30%/50% defaults are deleted rather than overridden. |
| D1 | `Architecture Plan.md`'s delivery table rebuilt to mirror the Implementation Plan's phase order exactly, with a Phase column. Reports moved after Coach Synthesis; golden fixtures moved to 10:30-11:30. |

**Additional cleanup made while fixing the above:** `savings_surplus_ratio` and `extra_debt_surplus_ratio` were **removed** from `PlanningAssumptions` rather than retained for backward compatibility. They were the exact mechanism by which Savings and Debt each independently claimed a share of surplus; leaving them in the contract would invite the double-allocation bug to return through a future code path.

**Net schedule effect:** the fixes add ~2-3 hours; removing the strategy-policy layer saves ~2. The rebaselined estimate is **~20-25 hours**, reflected in both plans' delivery tables.

---

---

## Summary Table

| ID | Gap | Category | Severity | Fix lands in |
|---|---|---|---|---|
| A1 | Phase 1 gate item is unverifiable in Phase 1 (no plan exists yet) | Forward dependency | **Blocking** | Impl. Phase 1 + 3; Arch. Component 3 |
| A2 | Phase 4 validator needs structured specialist output that no phase builds | Forward dependency | **Blocking** | Impl. Phase 3; Arch. Multi-Agent Orchestration |
| A3 | Phase 0 forward-references golden fixtures to a phase that doesn't own them | Forward dependency | Medium | Impl. Phase 0 + new phase |
| B1 | Optional Phase 6 forks the phase chain; no rule covers it; tracker has no Skipped state | Broken chain | High | Impl. Rules + Tracker |
| B2 | `phase6-done` tag may never exist, but later phases reference it | Broken chain | Medium | Impl. Rules |
| C1 | Structured specialist output (`Review.md` item 14) absent from both docs | Missing work | **Blocking** | Impl. Phase 3; Arch. contracts |
| C2 | Golden fixtures store inputs only — no expected outputs (`Review.md` item 27) | Missing work | High | Impl. new phase |
| C3 | Property-based tests (`Review.md` item 26) absent from both docs | Missing work | High | Impl. Phase 9 |
| C4 | Severity/urgency never feeds roadmap priority (`Review.md` item 4) | Missing work / conflict | High | Arch. Component 4; Impl. Phase 3 |
| C5 | Phase 2's "data-quality problems" finding type has no input producer | Missing work | High | Impl. Phase 1 |
| C6 | Removing `_enrich_context()` allocation defaults is gated but never tasked | Missing work | Medium | Impl. Phase 3 |
| D1 | Architecture Plan timeline builds Reports 7 hours before its input exists | Doc inconsistency | Medium | Arch. Remaining-Hours table |

---

## Category A — Forward Dependencies

These directly violate the requirement that a phase must be completable and verifiable without any work from a later phase.

### A1 — Phase 1 exit gate cannot be checked in Phase 1

**Severity:** Blocking
**Location:** `Implementation Plan - MVP 1.md:71`; source of the error at `Architecture Plan.md:693`

**The gap.** Phase 1's exit gate contains:

> - [ ] A plan cannot allocate more than `allocatable_surplus`

Phase 1 builds ingestion and `calculate_financial_snapshot()`. There is no "plan" in Phase 1 — `build_roadmap()` and the `Roadmap.allocation` dict are not built until **Phase 3** (`Implementation Plan - MVP 1.md:110`). A verifier signing off Phase 1 has literally nothing to test against this checkbox, so it will either be waved through (defeating the gate discipline) or block Phase 1 indefinitely.

**Root cause.** This item was inherited verbatim from `Architecture Plan.md`'s Component 3 acceptance checks (`Architecture Plan.md:693`), where it was written before the Component-3 / Component-4 split was mapped onto sequential phases. It is a Component 4 concern living in a Component 3 list.

**Why it matters beyond bookkeeping.** The allocation-never-exceeds-surplus invariant is the *single most important* correctness property in this codebase — it's the double-allocation bug's regression test. Leaving it in a phase that can't verify it risks it being checked off carelessly and never actually tested.

**Fix.**
1. Delete the item from Phase 1's gate.
2. Confirm the equivalent already exists in Phase 3's gate — it does, and in stronger form (`Implementation Plan - MVP 1.md:130`): "`sum(roadmap.allocation.values())` … never exceeds `allocatable_surplus`". No new gate item needed.
3. Fix at source: in `Architecture Plan.md:693`, move that bullet out of Component 3's acceptance checks and into Component 4's (where an equivalent bullet already exists).
4. Replace it in Phase 1 with what Phase 1 *can* verify: `allocatable_surplus` is never negative, and equals `max(0, gross_surplus − required_commitments − minimum_monthly_buffer)` for every Phase 0 fixture.

---

### A2 — Phase 4's validator depends on structured output that Phase 3 never builds

**Severity:** Blocking
**Location:** `Implementation Plan - MVP 1.md:150-160` (validator checks) vs. `:109-121` (Phase 3 tasks); `Architecture Plan.md:150-151`, `:104`

**The gap.** Phase 4 specifies `validate_consistency()` with ten checks. Phase 3 refactors the specialist agents' **inputs** (they now read `roadmap_result.allocation` instead of computing their own share) but says nothing about their **output shape**. The agents therefore still return what they return today: a free-text `narrative` string plus loose supporting tables — see `agents/spending_agent.py:33`, `agents/debt_agent.py:55`, `agents/savings_agent.py:44-51`, and `Architecture Plan.md:104` ("Every node still returns narrative text and its own supporting tables").

Deterministically validating claims made in free-flowing LLM prose is not possible for most of these checks. Breaking them down:

| # | Check | Implementable against free text? | Notes |
|---|---|---|---|
| 1 | No narrative quotes a dollar amount ≠ `roadmap.allocation` | ⚠️ Partially | Regex-extract `$X,XXX` patterns, compare against an allowlist of permitted values. Fragile (misses "twelve hundred", "1.2k") but workable. |
| 2 | No action's `monthly_amount` exceeds `allocatable_surplus` | ✅ Yes | Operates on the structured `Roadmap`, not prose. |
| 3 | No agent creates an unapproved recommendation | ❌ **No** | Requires understanding what the prose *recommends*. Not decidable without an LLM judge. |
| 4 | No agent contradicts roadmap priority ordering | ❌ **No** | Same — requires semantic comparison of prose against an ordering. |
| 5 | No investment/extra-savings recommendation when allocation is 0 | ❌ **No** | Keyword matching ("invest", "contribute") produces both false positives and trivial evasions. |
| 6 | No debt-acceleration narrative when `debt_extra_payment` is 0 | ❌ **No** | Same as #5. |
| 7 | No goal-contribution narrative exceeds allocated amount | ⚠️ Partially | Same regex limitation as #1. |
| 8 | No specialist uses a different income/expense/surplus value | ⚠️ Partially | Same regex limitation as #1. |
| 9 | All quoted percentages resolve to a `Trend` or metric | ⚠️ Partially | Regex-extract `NN%`, compare against trend values. |
| 10 | All `finding_refs`/`risk_refs`/`evidence_ids` resolve | ❌ **No** | Specialists don't emit refs at all today — there is nothing to resolve. |

**Four checks (3, 4, 5, 6, 10 — five, counting #10) are not implementable as written.** Attempting them anyway leads to one of three bad outcomes: silently dropping them, implementing brittle keyword heuristics that generate false failures during the demo, or reaching for an LLM judge — which `Architecture Plan.md` explicitly forbids ("Remove runtime multi-model judging. A second model should not validate money calculations").

**Root cause.** Shared with C1: `Review.md` item 14 prescribes exactly the structured specialist output that would make these checks trivial, and `Architecture Plan.md:898` lists item 14 in the **Critical before MVP** tier — but no task in any phase implements it. The triage entry was written; the corresponding work was not.

**Fix.** Add to **Phase 3**'s task list (not Phase 4 — the producing side must exist before the consuming side):

Each specialist agent's `run()` returns a structured result alongside its narrative:

```python
{
    "agent": "Debt Analyzer",
    "narrative": "...",                       # free text, for display only
    "allocated_amount": 720.0,                # copied from roadmap.allocation, never computed
    "why_allocated": "ACTION_ACCELERATE_DEBT",# action_id, not prose
    "expected_effect": "...",
    "tradeoffs": "...",
    "what_to_monitor": "...",
    "finding_refs": ["FINDING_HIGH_APR_DEBT"],
    "trend_refs": ["TREND_DEBT_BALANCE_3M"],
    "recommends_action_ids": ["ACTION_ACCELERATE_DEBT"],
}
```

Then rewrite Phase 4's checks 3, 4, 5, 6, and 10 to operate on these structured fields:

* #3 becomes: every entry in `recommends_action_ids` exists in `roadmap.actions`.
* #4 becomes: the order of `recommends_action_ids` is consistent with those actions' `priority` values.
* #5/#6 become: if `allocation[x] == 0`, then no specialist's `allocated_amount` for `x` is `> 0` and no `recommends_action_ids` entry maps to an action allocating `x`.
* #10 becomes: every `finding_refs`/`trend_refs`/`risk_refs` entry resolves against this invocation's objects.

Checks 1, 7, 8, 9 stay as regex-over-prose *defense in depth* — with the structured `allocated_amount` field as the authoritative comparison, prose scanning becomes a secondary safety net rather than the primary mechanism.

Also update `Architecture Plan.md:104` — "Every node still returns narrative text and its own supporting tables" is now incomplete and should describe the structured shape.

---

### A3 — Phase 0 forward-references a golden-fixture phase that doesn't exist

**Severity:** Medium
**Location:** `Implementation Plan - MVP 1.md:40`

**The gap.** Phase 0's fixture task ends: "*(these last two are also this phase's start on the golden-fixture set from Phase 9)*". But Phase 9 (`:265-276`) is a validation/regression pass that never mentions golden fixtures, and never authors expected outputs. Meanwhile Phase 11 gate items 11 and 12 (`:309-310`) say "Load the negative-cashflow **golden fixture**" as though a fixture with known-expected results exists.

So the chain is: Phase 0 defers to Phase 9 → Phase 9 doesn't own it → Phase 11 assumes it's done. Nobody builds it. See C2 for the substantive version of this gap.

**Fix.** Remove the dangling "from Phase 9" reference in Phase 0 and point it at the new golden-fixture phase created for C2.

---

## Category B — Broken Phase Chain

### B1 — The optional Phase 6 forks the chain, and no rule covers the fork

**Severity:** High
**Location:** `Implementation Plan - MVP 1.md:9-12` (Rules), `:24` (Tracker), `:224` (Phase 7 entry), `:243` (Phase 8 entry)

**The gap.** Rule 2 states: "The exit gate must be 100% checked — not 'mostly' — before the next phase opens." That rule assumes a single linear chain. But:

* Phase 6 is explicitly optional (`:193`, `:197`: "skip this phase entirely and go straight to Phase 7").
* Phase 7's entry criterion is "**Phase 5** marked done" (`:224`) — it skips Phase 6 entirely.
* Phase 8's entry criterion is "Phases 0–5 **and 7**" (`:243`) — an irregular, hand-enumerated list.

So the real dependency graph is `5 → {6 optional} → 7 → 8`, where 7 depends on 5, not 6. This is *correct engineering* but it contradicts the document's own stated rule, and a team following Rule 2 literally would be confused about whether they're allowed to start Phase 7 with Phase 6 untouched.

**Additional problem:** the Phase Status Tracker (`:16-29`) has only a free-text Status column with "Not started" defaults. There is no defined **Skipped** state, so a skipped Phase 6 is indistinguishable from a forgotten one — exactly the ambiguity the gating discipline exists to prevent.

**Fix.**
1. Amend the Rules section to define two valid completion paths explicitly:
   * **Full path:** 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11
   * **Reduced path (time-constrained):** 0 → 1 → 2 → 3 → 4 → 5 → 7 → 8 → 9 → 10 → 11 (Phase 6 marked **Skipped**)
2. Add a rule: "Phase 6 is the only phase that may be skipped. Every other phase is mandatory and strictly sequential. A skipped phase must be explicitly marked **Skipped** with a date and decision-maker — never left as 'Not started'."
3. Add `Skipped` as a documented Status value in the tracker, with a `Decision` column noting who made the call and when.

---

### B2 — `phase6-done` tag may never exist, but later phases and gates reference it

**Severity:** Medium
**Location:** `Implementation Plan - MVP 1.md:218` (tag), `:228`, `:248`, `:270`, `:285`, `:306`

**The gap.** Rule 3 requires tagging each phase's commit `phaseN-done`. If Phase 6 is skipped, `phase6-done` never exists — but Phases 7, 8, 9, 10 and Phase 11's gate item 8 all contain conditional "(if Phase 6 shipped)" language. Anyone auditing progress by git tags (`git tag -l 'phase*-done'`) sees a hole at 6 and cannot tell whether it was skipped deliberately or dropped accidentally.

**Fix.** Add to Rule 3: "If Phase 6 is skipped, tag the Phase 5 completion commit `phase6-skipped` instead, so the tag sequence is auditable with no ambiguous gaps."

---

## Category C — Missing Work No Phase Owns

### C1 — Structured specialist output (`Review.md` item 14) is triaged Critical but never tasked

**Severity:** Blocking
**Location:** `Review.md:299-318`; triaged at `Architecture Plan.md:898`; absent from all phases

**The gap.** `Review.md` item 14 says specialist output "should be structured around: Allocated amount / Why it was allocated / Expected effect / Trade-offs / What to monitor". `Architecture Plan.md:898` places item 14 in the **Critical before MVP** tier. Grepping both plan documents for `Allocated amount`, `What to monitor`, `Expected effect`, or `structured around` returns **zero matches**.

What *was* implemented from item 14 is only its first half — the prohibitions (don't calculate surplus, don't compute your own percentage), enforced by Phase 3's input refactor. The second half — the prescribed output *shape* — was dropped silently.

**Consequence.** This is the root cause of A2. Without structured output, the consistency validator (an entire phase, Phase 4) is built on prose parsing and half its checks are undeliverable. It also blocks `Review.md` item 13 (explainability: "Why is this recommended? Which findings and risks triggered it?") — that view needs stored structured references, not reconstructed prose.

**Fix.** As detailed in A2: add the structured return shape to Phase 3's task list for all five specialist agents, and add a Phase 3 gate item:

> - [ ] Every specialist returns `allocated_amount`, `why_allocated`, `expected_effect`, `tradeoffs`, `what_to_monitor`, `finding_refs`, `trend_refs`, and `recommends_action_ids` as structured fields; `allocated_amount` is copied from `roadmap.allocation`, never computed locally

Add the corresponding `SpecialistResult` contract to Phase 0's contract list and to `Architecture Plan.md`'s Canonical Contracts section.

---

### C2 — Golden fixtures have no expected outputs

**Severity:** High
**Location:** `Review.md:549-571` (item 27); `Implementation Plan - MVP 1.md:40`, `:309-310`; `Architecture Plan.md:858`

**The gap.** `Review.md` item 27 is explicit that golden fixtures must store the **expected** `snapshot`, `trends`, `findings`, `risks`, `roadmap allocation`, and `top priorities`, with the rule: "Narrative wording may vary, but no amount, priority, severity, or factual claim may drift."

The Implementation Plan only commits **input profiles** in Phase 0 (`:40`). No phase ever authors the expected outputs. This is not an oversight that can be fixed in Phase 0 either — the expected `snapshot` can't be authored before Phase 1 exists, expected `trends`/`findings`/`risks` before Phase 2, or expected `allocation`/`top_priorities` before Phases 3 and 5. **The expectations can only be frozen after Phase 5.**

Phase 11 gate items 11-12 then use these as if they exist, and `Architecture Plan.md:858` schedules "golden fixtures" in the final 17:00-20:00 block — too late to catch a regression introduced at hour 6.

**Fix.** Insert a new phase between the current Phase 5 (Coach Synthesis) and Phase 6, or immediately after Phase 7:

> **Phase 5.5 — Golden Fixture Freeze**
> **Entry:** Phase 5 done (snapshot, trends, findings, risks, roadmap, coach summary all produced).
> **Tasks:** For each of the Phase 0 input profiles (minimum: stable-high-surplus, negative-cashflow, income-drop-plus-rising-dining), run the full pipeline, manually review every output for correctness, then freeze expected `snapshot.metrics`, `Trend[]`, `Finding[]` (id + severity + urgency + confidence + fact_or_inference), `Risk[]`, `roadmap.allocation`, and `coach_summary.top_priorities` into `fixtures/golden/*.expected.json`. Add a regression test asserting exact equality on all numeric and enum fields, ignoring narrative prose.
> **Gate:** All three golden fixtures pass; a deliberate one-cent change to any allocation fails the test.

Note the manual-review step is essential — freezing unreviewed output just enshrines whatever bug exists at that moment.

---

### C3 — Property-based tests are absent

**Severity:** High
**Location:** `Review.md:547`; absent from both plan documents

**The gap.** `Review.md` item 26 closes with: "Also add property-based tests for allocation invariants and payoff schedules." Neither plan document mentions property-based testing anywhere (zero grep matches for `property-based`/`property based`).

This matters more than a typical missing test type: the allocation waterfall and the avalanche/snowball payoff simulation are exactly the kind of code where example-based tests pass while an edge case (zero income, a single debt with 0% APR, a goal with `months=0`, surplus of exactly `0.00`) silently breaks an invariant. The invariants are already precisely stated and are trivially expressible as properties.

**Fix.** Add to Phase 9's task list:

> - Property-based tests (`hypothesis`) over randomly generated valid `FinancialProfile`s asserting: (a) `sum(distributed allocation) <= allocatable_surplus` always; (b) `allocatable_surplus >= 0` always; (c) no debt balance goes negative in any payoff schedule; (d) payoff month count is monotonically non-increasing as `extra_payment` increases; (e) `gross_surplus <= 0` implies every distributed allocation is `0`.

Add `hypothesis` to `requirements.txt` (dev dependency) in Phase 0 alongside the other test scaffolding.

---

### C4 — Severity and urgency never influence roadmap priority

**Severity:** High — this is an unreconciled contradiction, not just an omission
**Location:** `Review.md:73-93` (item 4); `Architecture Plan.md` Component 4 prioritization rules; `Implementation Plan - MVP 1.md:110`

**The gap.** `Review.md` item 4 states plainly: severity and urgency "should control **both roadmap priority** and UI presentation", and explains why — "The current flat list format makes critical cashflow problems appear equal to long-term retirement optimization."

The plans implement only half of this. `Finding` and `Risk` objects carry `severity`/`urgency` (Phase 2), and `Roadmap.actions[]` carries `severity`/`urgency` fields, and the Coach Summary buckets actions by urgency (Phase 5). But `build_roadmap()`'s priority ordering is a **fixed six-step waterfall** (`Implementation Plan - MVP 1.md:110`) that never consults the severity or urgency of the findings/risks passed into it. An action's `severity` field is therefore *descriptive metadata attached after the fact*, not an input to ordering.

Whether this is a real defect depends on an unresolved design question: **is the fixed waterfall intentionally severity-independent?** There's a legitimate argument that it is — a deterministic, always-the-same ordering (minimums → buffer → high-interest debt → goals → savings) is more predictable and auditable than one that reshuffles based on computed severity, and the strategy-policy layer (Phase 6) already exists to vary emphasis. But if that's the intent, the plans should say so explicitly and note the deliberate divergence from `Review.md` item 4, rather than leaving severity looking like it drives ordering when it doesn't.

**Fix — decide and document one of:**
* **Option A (recommended):** Keep the waterfall severity-independent. Add an explicit note to `Architecture Plan.md`'s Component 4 prioritization rules: "This ordering is deliberately fixed and does not vary with finding/risk severity — severity and urgency control *presentation* (Coach Summary bucketing, UI emphasis) and *policy selection*, not the deterministic allocation order. This is a considered divergence from `Review.md` item 4's 'control roadmap priority' phrasing, chosen for auditability." Move the "control roadmap priority" half of item 4 to the Important tier in the triage.
* **Option B:** Make severity a tie-breaker *within* a waterfall step (e.g., among feasible high-priority goals, fund the one tied to a `critical` finding first) — a small, bounded change that honors item 4 without making the whole order dynamic. Add a Phase 3 task and gate item.

Either way this must be recorded — right now the two documents disagree and nobody is instructed to notice.

---

### C5 — Phase 2's "data-quality problems" finding type has no input producer

**Severity:** High
**Location:** `Implementation Plan - MVP 1.md:86` (Phase 2 finding types) vs. `:59` (Phase 1 ingestion tasks)

**The gap.** Phase 2 lists 8 finding types, the eighth being "**data-quality problems**", and its gate requires "All 8 finding types compute correctly" (`:94`). But `derive_findings(snapshot, trends)` receives only a `FinancialSnapshot` and `Trend[]`. Nothing upstream detects data-quality issues: Phase 1's ingestion tasks (`:59`) cover `load_transactions`, `categorize_with_confidence`, `tag_transaction_types`, `build_review_items`, and `questionnaire_to_profile_fields` — no duplicate detection, no missing-month detection, no partial-month flagging, no implausible-date checks.

`Architecture Plan.md` compounds this by deferring the anomaly/data-quality engine to "Important"/"Production" tiers while keeping "data-quality problems" inside the Critical-tier Insight Engine scope. The finding type is Critical; every mechanism that would populate it is deferred.

**Consequence.** Phase 2's gate cannot be honestly checked. A team will either fake the finding (emit a constant "data looks fine"), or discover mid-phase that they need to build detection work that was never scoped and blow the timeline.

**Fix.** Add a minimal, cheap detection pass to **Phase 1**'s ingestion tasks — these are all a few lines each over a DataFrame and don't require the deferred anomaly engine:

> - `detect_data_quality_issues(transactions) -> list[dict]` producing flags for: exact duplicate rows (same date+description+amount), missing months in the date range, a partial trailing month (last month's data ends before month-end), fewer than 2 complete months of history, and zero income transactions. Store on `FinancialSnapshot` as `data_quality_flags`.

Then Phase 2's `derive_findings()` reads `snapshot.data_quality_flags` and converts them into `Finding` objects with `severity: "medium"`, `urgency: "immediate"`, `fact_or_inference: "fact"`, `confidence: 1.0`.

Add a Phase 1 gate item: "A fixture with a duplicated transaction and a missing month produces the corresponding `data_quality_flags`."

Also add the corresponding `data_quality_flags` field to the `FinancialSnapshot` contract in Phase 0 and in `Architecture Plan.md`'s contract section.

---

### C6 — Removing the old allocation defaults is gated but never tasked

**Severity:** Medium
**Location:** `Implementation Plan - MVP 1.md:137` (gate) vs. `:117-120` (tasks)

**The gap.** Phase 3's gate says the old defaults are "**removed, not just overridden**" — specifically `agents/orchestrator.py:34`'s `extra_debt_payment = monthly_surplus * 0.3` and `agents/savings_agent.py:22`'s `surplus * 0.5`. But Phase 3's task list only covers refactoring the four agent files (`savings_agent.py`, `budget_agent.py`, `debt_agent.py`, `goal_agent.py`). **No task mentions `agents/orchestrator.py` at all.**

That file's `_enrich_context()` (`agents/orchestrator.py:30-35`) is where the 30% default is injected into the shared context, and `run_full_report()`/`route_chat()` (`:37-62`) are the current fan-out mechanism the LangGraph graph replaces. Leaving them in place means the old dict-comprehension orchestration path survives alongside the new graph — two code paths, one of which still contains the bug.

**Fix.** Add to Phase 3's task list:

> - Refactor `agents/orchestrator.py`: delete `_enrich_context()`'s `extra_debt_payment` default (`:34`) and its `monthly_surplus` recomputation (`:33`) — both are now supplied by `build_roadmap()`. Either delete `run_full_report()` entirely in favor of the graph invocation, or reduce it to a thin wrapper that calls the graph. Preserve `ROUTES` keyword mapping for `route_chat`, which Phase 8 rewires.

Add a gate item: "`grep -n '\* 0\.3\|\* 0\.5' agents/` returns no allocation-related matches."

---

## Category D — Cross-Document Inconsistency

### D1 — Architecture Plan's timeline builds Reports before its inputs exist

**Severity:** Medium
**Location:** `Architecture Plan.md:850` vs. `Implementation Plan - MVP 1.md:222-224`

**The gap.** `Architecture Plan.md:850` schedules:

> | 0:45-3:00 | Build components 2 and 6 in parallel | Ingestion, Reporting |

Component 6 is Reports and tracker. But the report signature is now `build_report(profile, snapshot, roadmap, coach_summary)` — and `coach_summary` doesn't exist until Coach Synthesis, scheduled at `Architecture Plan.md:853` (6:30-8:00) and implemented in Implementation Plan Phase 5. Reports cannot be built at 0:45.

The Implementation Plan gets this right (Reports is Phase 7, entry = Phase 5 done). The Architecture Plan's timeline row is stale — left over from before Coach Synthesis was added as a report input.

**Additional inconsistency in the same table:** `Architecture Plan.md:858` schedules "golden fixtures" in the 17:00-20:00 block, which conflicts with C2's recommendation to freeze them right after Phase 5 (~8:00) so they can catch regressions during integration rather than after it.

**Fix.**
1. Move Component 6 (Reporting) out of the 0:45-3:00 row and into a slot after Coach Synthesis, matching Implementation Plan Phase 7. The 0:45-3:00 row becomes Ingestion only, freeing that owner to assist with Component 3.
2. Move golden-fixture freezing from the 17:00-20:00 row into a new slot immediately after the consistency-validator/Coach-synthesis row, per C2.
3. Re-verify the whole table against the Implementation Plan's phase order — the two documents should describe the same sequence in different units (hours vs. gated phases), and currently do not.

---

## Recommended Fix Order

Fix in this order, because C1 unblocks A2, and A2 is the largest single piece of undeliverable work:

1. **C1 + A2** (same root cause) — add the `SpecialistResult` structured contract to Phase 0, the producing task to Phase 3, and rewrite Phase 4's checks 3/4/5/6/10 against structured fields. *This is the only gap that makes an entire existing phase undeliverable as written.*
2. **C5** — add data-quality detection to Phase 1, so Phase 2's gate becomes checkable.
3. **A1** — move the allocation gate item from Phase 1 to Phase 3 (and fix `Architecture Plan.md:693`).
4. **C2 + A3** — add the Golden Fixture Freeze phase after Phase 5; repoint Phase 0's dangling reference.
5. **B1 + B2** — define the two valid phase paths, add the `Skipped` status and the `phase6-skipped` tag rule.
6. **C4** — make the severity-vs-priority decision (recommend Option A) and document it in both plans.
7. **C6** — add the `orchestrator.py` cleanup task to Phase 3.
8. **C3** — add property-based tests to Phase 9 and `hypothesis` to Phase 0's dev dependencies.
9. **D1** — realign the Architecture Plan's Remaining-Hours table with the corrected phase order.

**Net effect on the schedule.** These fixes add roughly 2-3 hours of work: structured specialist output (~1h, it's mostly mechanical), data-quality detection (~30m), the Golden Fixture Freeze phase (~1h including the manual review), and property-based tests (~30m). The rest are documentation corrections costing nothing but attention. Against the already-rebaselined 20-24 hour estimate in `Architecture Plan.md:840`, this pushes the realistic total toward **22-27 hours** — which strengthens the existing recommendation to cut the Phase 6 strategy-policy layer first if the actual budget is nearer 18 hours.
