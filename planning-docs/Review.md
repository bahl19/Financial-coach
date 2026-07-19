1. Add a deterministic Insight Engine

Introduce a new deterministic layer between FinancialSnapshot and build_roadmap():

FinancialProfile
    -> FinancialSnapshot
    -> Insight Engine
    -> Findings
    -> build_roadmap()
    -> Specialist narratives
    -> Coach summary

The Insight Engine should generate structured findings once so that agents do not independently rediscover or reinterpret the same patterns.

It should identify:

* income changes
* expense changes
* category trends
* cashflow deterioration or improvement
* unusual spending
* spending substitutions
* debt risks
* emergency-fund risks
* goal feasibility issues
* positive behavioural changes
* data-quality problems

The Insight Engine must be deterministic. The LLM may explain findings but must not create financial findings that do not exist in the structured output.

2. Add a Finding contract

Create a canonical Finding contract containing fields such as:

{
    "finding_id": "FINDING_INCOME_DROP",
    "type": "income_trend",
    "title": "Income declined sharply",
    "severity": "critical",
    "confidence": 1.0,
    "fact_or_inference": "fact",
    "metric_refs": ["monthly_income_trend", "monthly_surplus"],
    "evidence": [],
    "impact": "Current spending is no longer supported by income.",
    "recommended_response": "Stabilize cashflow before accelerating debt or savings.",
}

Every roadmap action and specialist narrative should reference one or more finding_id values.

Agents should not invent new findings in prose.

3. Distinguish facts, inferences, and hypotheses

The system currently risks presenting inferred behaviour as fact.

For example:

* Fact: Dining increased by 95%.
* Fact: Groceries decreased by 58%.
* Inference: The user may be replacing home cooking with dining out.
* Hypothesis: A lifestyle or work-pattern change may have caused the shift.

Every insight should clearly identify whether it is:

* a confirmed fact
* a deterministic inference
* an LLM-generated hypothesis

Inferences and hypotheses must include confidence values and supporting evidence references.

The product must never present an inference as a confirmed fact.

4. Add severity and urgency

Every finding, risk, and recommendation should include severity and urgency.

Suggested values:

Severity:
critical
high
medium
low
positive
Urgency:
immediate
this_month
next_90_days
long_term

This should control both roadmap priority and UI presentation.

The current flat list format makes critical cashflow problems appear equal to long-term retirement optimization.

5. Add confidence scores

Every non-trivial insight should carry a confidence score.

Examples:

* income declined 67%: confidence 1.0
* dining increased 95%: confidence 1.0
* dining may have replaced groceries: confidence 0.65
* shopping is unusually high relative to income: confidence based on defined thresholds

Confidence should be calculated deterministically where possible.

The LLM must not invent confidence values without a defined rule.

6. Add a Trend Engine

The current FinancialSnapshot is too static.

Introduce deterministic reusable trend calculations for:

* monthly income
* monthly expenses
* monthly surplus
* category spending
* debt balances
* savings balances
* spending volatility
* recurring expenses
* spending velocity
* burn rate
* emergency-fund runway

Create a Trend contract such as:

{
    "trend_id": "TREND_DINING_3M",
    "metric": "dining_spend",
    "period": "3_months",
    "start_value": 187.00,
    "end_value": 364.60,
    "absolute_change": 177.60,
    "percent_change": 94.97,
    "direction": "increasing",
    "classification": "sharp_increase",
}

All percentages quoted by narratives must come from these deterministic trend objects.

7. Add a dedicated Risk Engine or structured risk derivation

Risk flags should be richer than simple codes.

Each risk should include:

{
    "risk_id": "RISK_NEGATIVE_CASHFLOW",
    "category": "cashflow",
    "severity": "critical",
    "likelihood": "high",
    "impact": "Savings will decline if the pattern continues.",
    "metric_refs": ["monthly_surplus", "cash_runway_months"],
    "finding_refs": ["FINDING_INCOME_DROP"],
    "mitigation_refs": ["ACTION_REDUCE_DISCRETIONARY_SPEND"],
}

Risks should cover:

* negative cashflow
* insufficient emergency fund
* high-interest debt
* high debt-service burden
* income concentration
* income volatility
* overspending
* goal failure
* insufficient savings
* cash runway
* recurring expense concentration

8. Add recommendation and action IDs

Every roadmap action should have a stable ID.

Example:

{
    "action_id": "ACTION_STABILIZE_CASHFLOW",
    "priority": 1,
    "severity": "critical",
    "urgency": "immediate",
    "title": "Restore positive monthly cashflow",
    "monthly_amount": 498.00,
    "finding_refs": ["FINDING_INCOME_DROP", "FINDING_NEGATIVE_CASHFLOW"],
    "risk_refs": ["RISK_NEGATIVE_CASHFLOW"],
    "metric_refs": ["monthly_surplus"],
    "dependencies": [],
}

This will make recommendations traceable across the roadmap, specialist tabs, reports, chat, and monthly tracker.

9. Add action dependencies and blocking conditions

The roadmap should support dependencies and conditions.

Examples:

* investing is blocked while monthly cashflow is negative
* accelerated debt payment is blocked until debt minimums and minimum buffer are protected
* long-term goals may be deferred while emergency-fund coverage is below the starter threshold
* retirement contributions may be limited to employer-match levels during a cashflow crisis

Add fields such as:

"depends_on": [],
"blocked_by": [],
"activation_condition": "",
"completion_condition": "",

This prevents the product from simultaneously saying:

* the user is in an income crisis
* the user should increase discretionary spending
* the user should invest surplus that does not actually exist

10. Add a deterministic consistency validator

After roadmap construction and specialist narrative generation, run a consistency-validation stage.

It should verify:

* no narrative quotes a dollar amount different from roadmap.allocation
* no action exceeds available monthly surplus
* no agent creates an unapproved recommendation
* no agent contradicts roadmap priority
* no investment recommendation appears when allocation is zero
* no debt acceleration is suggested when extra debt allocation is zero
* no goal contribution is suggested beyond the goal’s allocated amount
* no specialist uses a different income, expenses, or surplus value
* all quoted percentages resolve to snapshot or trend metrics
* all finding, risk, evidence, and action references resolve

If the output fails validation, use a deterministic fallback narrative generated directly from the structured objects.

11. Add a top-level Coach or CFO synthesis layer

explain_roadmap() alone may not be sufficient.

Introduce a top-level Coach or CFO synthesis component whose responsibility is not to calculate or allocate money, but to:

* identify the overall financial state
* rank the top risks
* identify the top positive behaviours
* select the three most important actions
* explain trade-offs
* create the executive summary
* suppress irrelevant long-term advice during a short-term crisis

The Coach must consume:

* FinancialSnapshot
* trends
* findings
* risks
* roadmap actions
* specialist commentary

It must not create new numbers or change action priorities.

12. Improve the Coach Summary structure

The final summary should use a predictable hierarchy such as:

Overall Financial Health
What Changed
Critical Risks
Important Patterns
Positive Changes
Your Priorities
Actions This Week
Actions This Month
Next 90 Days
Long-Term Actions
Assumptions and Data Limitations

The summary should not concatenate separate agent outputs into one long report.

It should remove duplication and present only the most decision-relevant information.

13. Ensure all recommendations are explainable

Every recommendation should be able to answer:

* Why is this recommended?
* Which facts support it?
* Which findings and risks triggered it?
* How was the amount calculated?
* What is the expected benefit?
* What trade-off does it create?
* What happens if the user ignores it?
* When should the recommendation stop or change?

The report and UI should support a “Why this?” view using stored references rather than asking the LLM to reconstruct reasoning.

14. Prevent independent specialist reasoning from changing the plan

Specialist agents may provide domain-specific explanation, but they must not:

* calculate new surplus
* calculate their own contribution percentage
* reorder priorities
* add a monetary action
* recommend an amount different from the roadmap
* silently assume missing inputs
* present unsupported behavioural explanations as fact

Their output should be structured around:

Allocated amount
Why it was allocated
Expected effect
Trade-offs
What to monitor

15. Reduce duplicated calculations

Ensure the following are calculated exactly once per graph invocation:

* monthly income
* average expenses
* monthly surplus
* category totals
* budget split
* debt minimums
* debt payoff results
* savings capacity
* goal feasibility
* trend percentages
* roadmap allocations

Specialists and reports must consume stored outputs rather than recomputing them.

16. Fix potential semantic confusion around surplus and allocation

Define clearly:

gross_surplus
= confirmed monthly income - average monthly expenses
required_commitments
= debt minimums and other mandatory obligations not already included in expenses
minimum_buffer
= user-configured amount protected from allocation
allocatable_surplus
= max(0, gross_surplus - required commitments - minimum buffer)
roadmap allocation
= amounts distributed from allocatable_surplus

The plans currently risk ambiguity about whether debt minimums and buffer are already included in expenses or deducted again.

This must be explicitly defined and tested to prevent double-counting.

17. Clarify the role of buffer_reserved

Determine whether buffer_reserved is:

* part of the allocation
* money intentionally left unallocated
* an expense
* a balance requirement
* or a planning constraint

Do not include it in the allocation total unless it represents an actual monthly transfer.

If it is simply money that must remain available, model it separately from action allocations.

18. Handle negative cashflow explicitly

When monthly surplus is negative:

* allocatable_surplus must be zero
* debt acceleration must be zero
* discretionary savings contribution must be zero
* goal contributions must normally be zero
* the roadmap should become a cashflow-recovery plan
* recommendations should focus on expense reduction, income recovery, debt-minimum protection, and runway

Do not allow specialist agents to produce positive extra-payment or investment amounts during a deficit.

19. Add data reconciliation and period consistency

The existing contradictory summaries suggest different agents may be using different periods.

The system should explicitly define:

* analysis period
* latest complete month
* partial-month handling
* average calculation period
* income source
* confirmed income versus transaction-derived income
* one-time transactions
* transfers
* refunds
* debt payments
* internal account movements

Every metric must include its period and source.

Example:

{
    "value": 3100.0,
    "period": "2026-07",
    "source": "user_confirmed",
    "is_partial_period": False,
}

20. Distinguish spending from transfers and debt payments

Debt payments, transfers to savings, credit-card payments, refunds, and internal account transfers should not automatically be treated as ordinary consumption expenses.

Create or enforce transaction types such as:

* income
* expense
* debt_payment
* transfer
* savings_transfer
* investment_transfer
* refund
* unknown

Otherwise spending totals, category totals, and monthly surplus may be materially wrong.

21. Add recurring-transaction detection

Identify recurring transactions such as:

* rent
* subscriptions
* loan payments
* insurance
* salary
* utilities

Each recurring item should include confidence and cadence.

This improves:

* baseline expense estimation
* future cashflow
* anomaly detection
* cancellation opportunities
* runway estimates

22. Add anomaly and data-quality handling

The engine should detect:

* duplicate transactions
* missing months
* partial months
* unusually large transactions
* refunds
* inconsistent signs
* implausible dates
* invalid currencies
* missing income
* category uncertainty
* insufficient history

The Coach Summary must disclose when confidence is limited due to poor or incomplete data.

23. Add currency and locale safety

Do not hardcode:

* USD
* US retirement products
* 401(k)
* Roth IRA
* US contribution limits
* high-yield savings account terminology

Recommendations must depend on the selected country, currency, and supported product rules.

For MVP, avoid jurisdiction-specific recommendations unless the jurisdiction and relevant rules are explicitly configured.

24. Prevent unsupported regulated advice

The product should clearly separate:

* financial education
* budgeting guidance
* debt-paydown modelling
* generic savings guidance

from:

* investment product recommendations
* tax advice
* legal advice
* regulated financial advice

Do not recommend specific investment products or jurisdiction-specific contribution limits unless backed by an approved and current rules source.

25. Reassess the strategy-policy layer

The strategy-policy layer may be useful, but it may be too complex for MVP 1 compared with the more important missing Insight Engine.

Prioritize in this order:

1. canonical contracts
2. deterministic snapshot
3. trends and findings
4. deterministic roadmap
5. specialist narration
6. consistency validation
7. reporting and UI
8. optional strategy-policy layer

If delivery time is constrained, defer the LLM-selected strategy policy before deferring deterministic insight generation or validation.

26. Add stronger tests

Add tests for:

* negative cashflow
* zero income
* partial months
* missing months
* duplicate transactions
* refunds and transfers
* debt payments excluded from ordinary spending where appropriate
* one debt
* multiple debts
* zero debts
* zero goals
* competing goals
* high-priority goals
* emergency-fund shortfall
* allocation never exceeding allocatable surplus
* no specialist amount differing from roadmap allocation
* no jurisdiction-specific advice without jurisdiction context
* exact metric and action references
* deterministic graph versus direct-function equivalence
* fact versus inference labelling
* confidence boundaries
* severity ordering
* fallback narrative consistency
* reports matching source objects exactly

Also add property-based tests for allocation invariants and payoff schedules.

27. Add golden regression fixtures

Create fixed financial profiles representing:

* stable high surplus
* income collapse and deficit
* high-interest debt crisis
* no debt and low emergency fund
* multiple competing goals
* incomplete data
* irregular income
* partial transaction history

Store the expected:

* snapshot
* trends
* findings
* risks
* roadmap allocation
* top priorities

Narrative wording may vary, but no amount, priority, severity, or factual claim may drift.

28. Update the LangGraph topology

Recommended topology:

Profile validation
    ->
Transaction normalization and reconciliation
    ->
Financial snapshot
    ->
Trend Engine
    ->
Insight and Risk Engine
    ->
Optional strategy-policy selection
    ->
Deterministic build_roadmap()
    ->
Specialist narrative nodes
    ->
Consistency validator
    ->
Coach/CFO synthesis
    ->
Report, tracker, specialist tabs, and chat

The graph should carry structured state forward.

Nodes should add named outputs rather than replacing shared state.

29. Keep deterministic and probabilistic responsibilities separate

Deterministic Python should own:

* financial calculations
* trends
* findings based on rules
* risks based on rules
* roadmap allocation
* validation
* report numbers
* tracker numbers

The LLM should own only:

* explanation
* tone
* concise coaching language
* optional low-confidence hypotheses clearly labelled as hypotheses
* follow-up conversational responses grounded in structured objects

30. Update both plans and the codebase

Apply these observations to:

* Architecture Plan.md
* Implementation Plan - MVP 1.md
* contracts
* graph topology
* agent responsibilities
* test gates
* implementation phases

Do not only add these as commentary.

Convert them into:

* explicit contracts
* public functions
* graph dependencies
* acceptance criteria
* regression tests
* phase gates

Finally, provide a prioritised change list divided into:

Critical before MVP
Important for MVP quality
Production hardening
Future enhancements

Do not implement features merely because they sound advanced.

Prefer the simplest architecture that guarantees:

* one financial truth
* one allocation truth
* traceable findings
* consistent narratives
* clear priorities
* deterministic validation
* trustworthy explanations

This version is ready to paste directly into the coding agent.