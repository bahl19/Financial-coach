# Phase Prompts — MVP 1

Execution prompts for each phase of [`Implementation Plan - MVP 1.md`](Implementation%20Plan%20-%20MVP%201.md).

**These prompts deliberately contain no concrete task lists, function signatures, or acceptance criteria** — all of that lives in the Implementation Plan, and duplicating it guarantees the two documents drift apart. Each prompt supplies what the plan does *not*: the engineering approach, the design principles that apply to that phase's particular shape, and the failure modes to watch for.

**How to use:** paste the **Standing Context** below, then the single phase prompt you are executing. One phase per session — the gating discipline exists so a phase is finished and verified before the next begins, and a session that holds two phases will blur them.

---

## Standing Context

> You are implementing one phase of a gated delivery plan for a personal-finance coaching application (Python, Streamlit, pandas, LangGraph, optional LLM via OpenRouter).
>
> **Authoritative documents — read before writing code:**
> - `Implementation Plan - MVP 1.md` — your phase's exact tasks and exit gate. This is the contract for what "done" means.
> - `Architecture Plan.md` — contracts, component boundaries, and the reasoning behind them.
> - `gaps.md` — resolved design defects and *why* they were resolved. Do not reintroduce them.
>
> **Scope discipline:** implement your assigned phase only. Do not start the next phase, do not "while I'm here" refactor an earlier one, and do not stub anything for a later one. If you believe a task belongs in a different phase, say so and stop rather than silently relocating it.
>
> **The three architectural invariants. Every one of these encodes a real bug that was found and fixed in review — treat violating them as a build failure, not a style disagreement:**
>
> 1. **One financial truth.** Every metric, trend, finding, and risk is computed exactly once, by the deterministic core, and referenced by ID downstream. Nothing recomputes a percentage, a cash-flow aggregate, or a risk classification that already exists.
> 2. **One allocation truth.** `build_roadmap()` is the *only* code that decides how surplus is distributed. Everything else reads its output. No component derives its own share of surplus — that specific bug (three agents independently claiming 30%, 50%, and 100% of the same money) is the reason this plan exists.
> 3. **Deterministic core, probabilistic surface.** Python owns every number, rule, allocation, validation, and reported value. The LLM owns explanation and tone only. An LLM may never produce, alter, or validate a financial figure.
>
> **SOLID, as it applies to this codebase specifically:**
>

> **Coding standards:**
> - Type-hint every public function. Contracts are `TypedDict`/dataclass, never bare dicts.
> - **No magic numbers.** Every ratio, threshold, and rate is a named constant or a contract field. The literals `0.3` and `0.5` are how the original bug shipped.
> - Pure functions by default: same input, same output, no I/O, no hidden state, no mutation of arguments. Producers return new values; nothing mutates a structure it did not create.
> - Guard every division (zero income, zero expenses, zero months are all real inputs).
> - Decide the money rounding policy once, apply it everywhere, and state it in a docstring.
> - Unknown data is `None`, never `0` — a zero that means "missing" will silently become a number in a calculation.
> - Inject the LLM client rather than importing it at module scope, so offline mode and tests need no network and no monkeypatching.
> - Fail loudly on contract violations; fail gracefully on user-data problems. A malformed statement is a validation issue shown to the user; a malformed `Roadmap` is a bug that should raise.
>
> **Testing standards:**
> - Every public function gets a unit test. Every gate item in your phase gets a test that would fail if the behavior regressed.
> - Test behavior through public interfaces, not private helpers — tests coupled to internals block the refactors that invariants 1-3 demand.
> - A test that needs a network call or an API key is a design defect in the code under test.
> - Never weaken an assertion to make a test pass. If a property test fails, the property is right until proven otherwise.
>
> **Definition of done:** every exit-gate checkbox for your phase in `Implementation Plan - MVP 1.md` is genuinely verified — not assumed, not "should work." Report honestly: if a gate item cannot be checked, say which one and why, rather than ticking it. A phase is not done because the code is written; it is done because the gate is green.

---

## Phase 0 — Contracts & Fixtures

> **Objective:** establish the shared vocabulary every later phase depends on.
>
> **Design guidance.** This module is the project's stable dependency — the one thing everything imports and nothing imports from. Keep it a pure leaf: standard library and typing only. If you find yourself needing a calculation here, it belongs in a later phase.
>
> Prefer shapes that serialize cleanly to JSON, because your fixtures are both test data and the contracts' executable documentation. A contract you cannot round-trip through a file is a contract you cannot golden-test later.
>
> Validators return a list of issues rather than raising. The caller decides whether a problem is fatal — this keeps validation reusable between the UI (which wants to display issues) and tests (which want to assert on them). Make validators total: no input, however malformed, should produce a traceback instead of a result.
>
> Write fixtures for the failure cases first. A fixture set containing only valid data tests almost nothing.
>
> **Watch for:** contract fields that encode a *policy* rather than a *fact*. A field like "percentage of surplus to save" is a decision that belongs to the allocator, not a value that belongs in a profile — that shape is precisely what enabled the double-allocation bug.
>
> **Done when:** Phase 0's exit gate is green.

---

## Phase 1 — Ingestion, Financial Core & Data Quality

> **Objective:** turn untrusted input into a trustworthy snapshot.
>
> **Design guidance.** Ingestion is an anti-corruption layer. It is the *only* place tolerant of messy input; everything downstream is entitled to assume the contract holds. Keep the tolerant parsing boundary and the strict calculation core in separate modules so that tolerance never leaks inward.
>
> The financial core is pure arithmetic over validated data. It should have no knowledge of files, uploads, Streamlit, or the LLM. A good check: your calculation module's imports should contain no I/O library at all.
>
> Derive each metric once and compose from those derivations rather than recomputing from raw transactions in several places. Where two metrics differ subtly (a gross figure versus an allocatable one), name both explicitly and document the difference at the definition site — ambiguity between near-identical money concepts is a documented source of double-counting in this project.
>
> Data-quality detection is a set of small independent predicates over the transaction frame, each answering one question. Keep them separate and individually testable; resist growing them into a general anomaly framework, which is deliberately out of scope.
>
> **Watch for:** silently coercing missing values to zero; recomputing an aggregate you already computed; letting a debt minimum be counted both inside expenses and again as a separate commitment.
>
> **Done when:** Phase 1's exit gate is green.

---

## Phase 2 — Trend, Insight & Risk Engines

> **Objective:** compute every pattern and risk once, as structured objects with stable identities.
>
> **Design guidance.** This is the phase where open/closed principle earns its keep. Model each finding and each risk as an independent rule: a small pure function that inspects the snapshot and trends and either produces one structured object or produces nothing. Register the rules in a list. Adding the twelfth rule should mean writing a function and appending it — never editing a growing conditional.
>
> Define every identifier as a constant in one place. IDs are referenced by the roadmap, the specialists, the validator, the coach summary, the report, and the golden fixtures; a typo'd string literal scattered across six modules is a defect that only surfaces at demo time.
>
> Confidence must come from a documented rule, not a judgment call. Put the formula in one function with a docstring explaining it, so a reviewer can disagree with the formula rather than reverse-engineer it from call sites.
>
> Where a legacy structure is retained for compatibility, derive it from the new objects — never let both be computed independently, or they will disagree.
>
> **Watch for:** rules that quietly reach back to raw transactions instead of using the snapshot and trends; findings asserted with more certainty than the data supports; a rule that needs an LLM to decide — if it does, it isn't a deterministic finding and belongs out of scope.
>
> **Done when:** Phase 2's exit gate is green.

---

## Phase 3 — Roadmap, Structured Specialists & Graph

> **Objective:** allocate surplus exactly once, then have every specialist narrate that allocation rather than invent its own.
>
> **This is the highest-risk phase in the plan.** It carries the most gate items because it is where the original defect lived.
>
> **Design guidance.** Model the allocator as a waterfall over a running remaining-budget value: each step may consume from what is left and nothing else. Done this way, "cannot allocate more than available" is *structurally impossible* rather than *checked afterwards* — the strongest form of the invariant. Consider a small ledger abstraction that refuses an over-allocation at the point of the call, so a future step cannot break the invariant without failing immediately and locally.
>
> For the specialists, use a base class that owns the result shape and the fallback path, with subclasses supplying only domain-specific content. This is Liskov in practice: orchestration code holds a collection of agents and must never branch on which one it has.
>
> Apply interface segregation strictly here. An agent that receives only its allocated figure *cannot* recompute a different one. An agent that receives the whole profile can, and under future maintenance eventually will. The narrow interface is the durable fix; the gate check is only the safety net.
>
> Keep graph nodes as thin adapters over pure functions. All logic lives in functions testable without instantiating a graph; the node is a few lines of wiring. This keeps the fallback path in the plan (direct function calls, no graph) genuinely available rather than a second implementation.
>
> When you delete the old allocation defaults, delete them — do not leave them unused, commented, or defaulted-around. Dead code encoding a fixed bug is an invitation to restore it.
>
> **Watch for:** any arithmetic on a surplus value inside an agent; a specialist result assembled by string-formatting rather than by copying structured values; graph nodes that grow business logic; "temporarily" keeping the old orchestration path alongside the new one.
>
> **Done when:** Phase 3's exit gate is green — including the grep check, which exists because this specific bug is worth mechanical verification.

---

## Phase 4 — Consistency Validator

> **Objective:** make it mechanically impossible for a narrative that contradicts the numbers to reach a user.
>
> **Design guidance.** Each check is an independent pure function returning violations — same registry pattern as the engines, same benefit. Never let a check mutate what it inspects; validation returns a verdict, and remediation is a separate step.
>
> Keep the two reliability tiers in **separate modules**, not merely separate functions. Structured checks over typed fields are guarantees. Prose checks over generated text are heuristics that will miss cases. Blurring them in one file invites someone later to treat a heuristic as a guarantee — the distinction is load-bearing and should be visible in the file layout.
>
> The fallback narrative generator is a pure function of the structured objects. It must be able to produce a complete, honest, useful narrative with no LLM available at all — it is the safety net for both validation failure and offline operation, so treat it as a first-class output rather than a degraded one.
>
> Write each test by *deliberately constructing the violation* the check exists to catch. A validator that has only ever seen valid input is untested.
>
> **Watch for:** a check that reimplements a calculation to compare against (it should compare against the stored value); catching a violation and continuing silently; prose heuristics tightened until they produce false failures on legitimate text.
>
> **Done when:** Phase 4's exit gate is green.

---

## Phase 5 — Coach Synthesis

> **Objective:** one prioritized summary, assembled from existing structured objects.
>
> **Design guidance.** This is selection and ranking, not generation. Every element the summary emits must be an identifier that already exists. If you find yourself needing a value that no upstream object provides, the correct response is to stop — that value is being invented, which is exactly what this layer must not do.
>
> Represent the section order as data rather than as a sequence of string concatenations. Ordering that lives in a data structure can be tested, reordered, and rendered differently by different consumers; ordering baked into concatenation cannot.
>
> Ranking and bucketing rules should be pure functions over the structured fields, so "why is this the top priority?" is answerable by reading one function.
>
> **Watch for:** summary text containing a number that appears nowhere upstream; the cap on priorities being treated as advisory; drifting into suppression or trade-off logic, which is deliberately deferred.
>
> **Done when:** Phase 5's exit gate is green.

---

## Phase 6 — Golden Fixture Freeze

> **Objective:** lock in verified-correct outputs so every later phase has a regression net.
>
> **Design guidance.** Serialization must be deterministic before anything is frozen — stable key ordering and a fixed float representation. Without that, ordinary re-runs produce diff noise and the suite gets ignored, which is worse than not having it.
>
> Build the comparison helper to ignore prose fields *explicitly and by name*, so the exclusion is a visible, reviewable decision rather than a silently loose assertion.
>
> **The manual review is the substance of this phase, not a formality.** Freezing unreviewed output does not create a regression net; it permanently enshrines whatever is wrong at this moment and gives false confidence forever after. Read every number and ask whether it is right — not whether it is what the code produced. The second-person sign-off on the negative-cashflow case exists because that scenario is where a plausible-looking wrong answer does the most user harm.
>
> Prove the net actually catches things: perturb a value, watch the suite fail, revert. An untested regression test is not a regression test.
>
> **Watch for:** adjusting an expected value to match code output instead of investigating the discrepancy — that inverts the entire point of the phase.
>
> **Done when:** Phase 6's exit gate is green.

---

## Phase 7 — Reports & Tracker

> **Objective:** render existing values. Compute nothing.
>
> **Design guidance.** This is a formatter. The strongest design signal available: if you need a number that is not already in your inputs, you have found an upstream bug — report it, do not compute it here. A single arithmetic operation in a rendering module is how "the report says something different from the app" begins.
>
> Separate content assembly (choosing what to include, in what order) from formatting (turning it into markdown or a frame). Assembly is testable without string comparison; mixing them forces every test to assert on formatted text, which is brittle.
>
> Where a value is semantically different from its neighbours — a reserved amount that is not a transfer, sitting beside amounts that are — make that distinction visible in the output. A reader who sums a column and gets a wrong total has been misled by the layout.
>
> **Watch for:** any arithmetic in this module; re-deriving a percentage for display; a total that includes a non-distributed amount.
>
> **Done when:** Phase 7's exit gate is green.

---

## Phase 8 — Streamlit Integration

> **Objective:** wire the finished pipeline into the UI without duplicating any of it.
>
> **Design guidance.** `app.py` is a thin controller: gather input, call public functions, render returned contracts. Any financial logic that appears here is logic that will diverge from the module that also owns it.
>
> Route session-state access through one small accessor module rather than scattering direct key reads and writes across the file. Streamlit reruns constantly, and scattered mutable-state access is where rerun bugs breed. Keep domain components pure — the UI writes state; the pipeline returns values.
>
> Rendering must be idempotent: the same state renders the same screen on every rerun, with no accumulation.
>
> When the validator has substituted a fallback, surface it. A silent substitution is a correctness signal thrown away, and disclosure is a product feature here rather than an admission.
>
> **Watch for:** a second orchestration path for chat or tabs (there must be exactly one); recalculating for display convenience; business logic migrating into callbacks.
>
> **Done when:** Phase 8's exit gate is green.

---

## Phase 9 — Validation, Property Tests & Regression

> **Objective:** prove the invariants hold across inputs nobody thought to write by hand.
>
> **Design guidance.** Example-based tests confirm the cases you imagined; property-based tests find the ones you did not. Generate profiles across the full legal input space — zero income, zero debts, a single debt at zero interest, exactly-zero surplus, boundary values — and assert the invariants that must hold universally.
>
> Treat a property failure as information, not an obstacle. When one fails, shrink the counterexample, understand it, and fix the code. Narrowing a generator or relaxing an assertion to get green converts a real finding into a hidden defect.
>
> When you fix something found here, add the failing case as a permanent example test alongside the property. The property proves the general rule; the example documents the specific bug and keeps it fixed.
>
> **Watch for:** generators constrained until they only produce comfortable inputs; new features slipping in under the banner of fixing tests; edge-case handling that catches an exception and returns a plausible number instead of surfacing the problem.
>
> **Done when:** Phase 9's exit gate is green.

---

## Phase 10 — UX & Narrative Polish

> **Objective:** improve clarity. Change no behavior.
>
> **Design guidance.** The defining constraint: **if a test changes, you are not polishing.** Presentation improvements do not alter calculations, allocations, orderings, or contracts. A behavioral change discovered to be necessary here belongs to its owning phase, with that phase's gate re-verified.
>
> Prioritize the screens where a misreading has consequences — anywhere a user might act on a number. Clarity about uncertainty and data limitations is worth more than visual refinement.
>
> Keep the de-scope order in the plan in mind and drop from the bottom under time pressure, rather than leaving several things half-finished.
>
> **Watch for:** "small" copy changes that alter meaning; polish that removes a disclosure; refactors smuggled in as formatting.
>
> **Done when:** Phase 10's exit gate is green, and the full suite passes unchanged.

---

## Phase 11 — Demo Rehearsal & Release Gate

> **Objective:** prove MVP 1 works, twice, without touching the code.
>
> **Design guidance.** This is verification, not development. **Write no code during this phase.** The two clean runs with no edits between them are the actual test — a run that required a fix is a failed run, and the fix belongs in the owning phase with that phase's gate re-verified before rehearsal restarts.
>
> Run the checklist as written, in order, as a user would. Do not shortcut through internals or skip a step you are confident about; confidence is what this gate exists to test.
>
> Record what you observed rather than what you expected. A step that "worked but looked odd" is a finding, not a pass.
>
> **This gate is the boundary between MVP 1 and MVP 2.** MVP 1 is an independently shippable product; MVP 2 work does not begin — not scaffolding, not contracts, not a branch — until every box here is genuinely green.
>
> **Done when:** all thirteen checks pass on two consecutive clean runs.

---

## Anti-Patterns to Reject in Review

Each of these is a real defect found in this codebase or its plans, not a hypothetical:

| Anti-pattern | Why it is rejected |
|---|---|
| A component computing its own share of a shared resource | The original bug. Three agents claimed 30%, 50%, and 100% of the same surplus with nothing reconciling them. |
| The same aggregate computed in two modules | They will diverge. One of them is already wrong under some input. |
| A magic ratio or threshold inline | Invisible to the UI, untestable, unreviewable. Every constant is named or contract-supplied. |
| An LLM producing, adjusting, or checking a number | Violates the deterministic-core boundary. Models explain; they do not calculate or adjudicate. |
| A finding asserted in prose without a resolving ID | Unverifiable by the validator, and indistinguishable from a fabrication. |
| Zero substituted for missing data | A missing value silently becomes a real number in arithmetic downstream. |
| Validation catching a violation and continuing | Silent failure is worse than a visible fallback — the user acts on the wrong number either way, but nobody finds out. |
| A growing `if/elif` chain of rules | Blocks open/closed extension and makes each rule untestable in isolation. |
| Business logic inside a graph node or UI callback | Untestable without the framework, and invisible to the module that supposedly owns it. |
| A test weakened to pass | Converts a real finding into a hidden defect, with the added cost of false confidence. |
| Dead code preserving a fixed bug | Someone will restore it. Delete it. |
| MVP 2 scaffolding inside MVP 1 | MVP 1 must be independently shippable. Stubs and flags are how the boundary erodes. |
