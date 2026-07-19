The diagram has the right product flow, but it currently mixes **data processing, financial computation, agent reasoning, evaluation and presentation** into one graph. That will create integration problems.

The cleanest design is:

> **Six contract-driven modules inside one modular monolith, with LangGraph coordinating them—not six separately deployed microservices.**

That gives you production-style boundaries without spending the hackathon debugging service discovery, CORS, queues and Docker networking.

# 1. Critical review of the current diagram

## What is already good

Your diagram correctly identifies:

* Multiple input modes: PDF, CSV, images and manual input
* Specialized financial capabilities
* Deterministic algorithm calls for debt and spending
* RAG and web-search needs
* Persistent user information
* Report generation
* Evaluation at important stages
* OAuth-based authentication

The product journey is broadly right.

## What must change

### 1. The Data Ingestion Agent is overloaded

It currently:

* Reads PDFs
* Extracts transactions
* Identifies income and expenses
* Finds investments and loans
* Reads credit-card usage
* Appears to extract goals
* Writes shared state

Split extraction from financial interpretation.

The ingestion component should only answer:

> “What facts are present in this document, where did they come from, and how confident are we?”

It should not decide whether the user is financially healthy or what their goals should be.

---

### 2. There are too many independent “State” objects

The green state bubbles around spend analysis, debt analysis, planning and orchestration will drift apart.

Use:

* One canonical, versioned financial profile
* One compact LangGraph workflow state
* Separate immutable outputs from every component

Agents should not own private copies of income, expenses, debts or goals.

---

### 3. Spend Analyzer and Debt Analyzer should not be agents

Most of their work is deterministic:

* Monthly aggregation
* Category totals
* Savings rate
* Loan amortization
* Avalanche versus snowball comparison
* Goal contribution calculation
* Feasibility checks

These should be Python tools with tests.

An agent may decide which simulation to run and explain the result, but it should not calculate the result.

---

### 4. Runtime “LLM as judge” model voting should be removed

The box that sends goal planning to multiple models and asks another model to judge them is expensive, slow and difficult to justify.

Use model comparison **offline in your eval suite**. Select the best model per task before deployment.

At runtime:

```text
Simple clarification → low-cost model
Complex goal planning → strong reasoning model
Narrative generation → mid-tier model
Mathematics → no model
```

---

### 5. RAG is currently only a vertical box

A production RAG system needs:

* Document acquisition
* Parsing
* Chunking
* Metadata
* Embeddings
* Hybrid retrieval
* Optional reranking
* Versioning
* Citation generation
* Expiry and effective dates
* Retrieval evaluation

Without those, agents will retrieve stale tax rules or irrelevant generic advice.

---

### 6. Agents should not directly call web search or MCPs

Every external call should pass through a **Tool Gateway** that enforces:

* Allowed domains
* Read-only versus write access
* Timeouts
* Token and request budgets
* Caching
* Source provenance
* User approval where necessary
* Schema validation

Otherwise every agent may search differently and produce conflicting advice.

---

### 7. Human review is missing after extraction

Before analysis, the user needs to review:

* Low-confidence fields
* Failed balance reconciliation
* Possible duplicate transactions
* Unknown transaction categories
* Missing loan interest rates
* Ambiguous transfers
* Credit-card payments that may double-count expenses

LangGraph interrupts are designed for pausing a graph, persisting state and resuming after user review. Production usage requires a persistent checkpointer. ([Docs by LangChain][1])

---

### 8. Evals should not sit inside the runtime workflow

Your blue “EVAL” labels should represent a separate quality plane.

An evaluation normally runs:

* During development
* In CI
* Before changing prompts or models
* Against sampled production traces

It should not block every real user request.

---

### 9. Clerk OAuth is authentication, not financial-data authorization

Clerk should authenticate the user and issue a session token. Your backend should validate that token and map the Clerk subject to an internal user ID. Clerk recommends authenticating the request or verifying the token on the backend. ([Clerk][2])

Do not store bank statements or financial profiles inside Clerk.

Importing from Google Drive, an account aggregator or a financial institution would require separate consent and connector authorization.

---

### 10. Report generation should not directly write arbitrary content into the database

The report should be generated from:

* A versioned financial snapshot
* A versioned plan
* A fixed evidence bundle
* Explicit assumptions
* User-approved corrections

That makes it reproducible.

# 2. Target architecture

```text
                              ┌───────────────────────────┐
                              │  1. Web UI + Identity BFF │
                              │  Next.js + Clerk          │
                              └─────────────┬─────────────┘
                                            │
                                  Authenticated Case API
                                            │
                 ┌──────────────────────────┴──────────────────────────┐
                 │                                                     │
        Upload PDF/CSV/manual data                           View/review/update
                 │                                                     │
                 ▼                                                     │
     ┌───────────────────────────┐                                    │
     │ 2. Document Intelligence  │                                    │
     │ extraction + provenance   │                                    │
     └─────────────┬─────────────┘                                    │
                   │ ExtractionBundle                                  │
                   ▼                                                   │
          Human review interrupt ◄─────────────────────────────────────┘
                   │
                   ▼
     ┌───────────────────────────┐
     │ 3. Financial Core Engine  │
     │ calculations/simulations │
     └─────────────┬─────────────┘
                   │ FinancialSnapshot
                   ▼
     ┌───────────────────────────────────────────────────────────────┐
     │ 5. LangGraph Agent Orchestrator                              │
     │                                                               │
     │ Clarification Agent → Goal Planner → Strategy Agent → Review │
     └──────────────┬───────────────────────────────────┬────────────┘
                    │                                   │
                    │ tool calls                        │ evidence calls
                    ▼                                   ▼
          Financial Core tools              ┌────────────────────────┐
                                            │ 4. Knowledge + Tool    │
                                            │ Gateway                │
                                            │ RAG / web / MCP        │
                                            └────────────┬───────────┘
                                                         │ EvidenceBundle
                    ┌────────────────────────────────────┘
                    ▼
     ┌─────────────────────────────┐
     │ 6. Report + Tracker Service │
     │ PDF / HTML / CSV / roadmap  │
     └─────────────────────────────┘
```

## Cross-cutting infrastructure

```text
PostgreSQL:
users, cases, profiles, transactions, goals, analyses,
plans, corrections, audit logs and eval metadata

Object storage:
original PDFs, page images, extracted artifacts and reports

pgvector:
curated financial knowledge embeddings

LangGraph Postgres checkpointer:
workflow state, interrupts and resumability

Observability:
LangSmith or OpenTelemetry traces, model cost and latency

Evaluation plane:
datasets, graders, regression tests and scorecards
```

# 3. The six independent components

## Component 1 — Experience, Identity and API Gateway

### Responsibilities

* Next.js UI
* Clerk login and OAuth
* Session-token validation
* Case creation
* Upload screens
* Extraction-review UI
* Financial dashboard
* Goal and constraint editor
* Plan comparison
* Report display and download
* Workflow progress streaming

### Must not contain

* PDF parsing
* Financial calculations
* RAG logic
* Prompt construction
* Direct database queries from the browser

### Public endpoints

```text
POST /v1/cases
POST /v1/cases/{case_id}/documents
GET  /v1/cases/{case_id}
POST /v1/cases/{case_id}/extraction-review
POST /v1/cases/{case_id}/planning-runs
POST /v1/planning-runs/{run_id}/resume
GET  /v1/planning-runs/{run_id}
GET  /v1/reports/{report_id}
```

### Authentication context

```json
{
  "principal_id": "internal-user-123",
  "clerk_subject": "user_xxx",
  "tenant_id": "tenant-default",
  "scopes": [
    "case:read",
    "case:write"
  ]
}
```

Only the internal `principal_id` should appear in application tables.

---

## Component 2 — Document Intelligence and Review

This consumes uploaded documents and produces verified financial facts.

### Pipeline

```text
Validate file
→ malware/MIME/file-size checks
→ detect PDF versus image versus CSV
→ detect digital versus scanned PDF
→ classify document type
→ native text/table extraction
→ OCR fallback
→ document-specific normalization
→ reconciliation
→ confidence scoring
→ review queue
```

### Supported document types for the MVP

* Bank statement
* Credit-card statement
* Mutual-fund or CAS statement
* Loan statement
* Manual financial form

### Input contract

```json
{
  "schema_version": "1.0",
  "case_id": "case-001",
  "document_id": "doc-001",
  "object_uri": "private://uploads/doc-001.pdf",
  "sha256": "abc123",
  "mime_type": "application/pdf",
  "document_type_hint": "bank_statement",
  "currency_hint": "INR"
}
```

### Output contract: `ExtractionBundle`

```json
{
  "schema_version": "1.0",
  "extraction_id": "ext-001",
  "case_id": "case-001",
  "document_id": "doc-001",
  "document_type": "bank_statement",
  "document_type_confidence": 0.98,
  "statement_period": {
    "start": "2026-01-01",
    "end": "2026-06-30"
  },
  "accounts": [
    {
      "account_id": "account-001",
      "type": "savings",
      "masked_number": "XXXX1234",
      "currency": "INR"
    }
  ],
  "transactions": [
    {
      "transaction_id": "txn-001",
      "date": "2026-06-03",
      "raw_description": "UPI SWIGGY BANGALORE",
      "normalized_merchant": "Swiggy",
      "amount": 740,
      "direction": "debit",
      "category": "food_delivery",
      "classification_source": "rule",
      "confidence": 0.96,
      "source_ref": {
        "page": 2,
        "bounding_box": [112, 401, 918, 432]
      }
    }
  ],
  "review_items": [
    {
      "review_id": "review-001",
      "type": "ambiguous_transaction",
      "entity_id": "txn-014",
      "blocking": false,
      "suggested_values": [
        "internal_transfer",
        "income_other"
      ]
    }
  ],
  "quality": {
    "rows_extracted": 124,
    "reconciliation_status": "passed",
    "average_confidence": 0.94
  }
}
```

### Hard boundary

This component may extract an explicitly stated goal such as:

> “₹20 lakh for education by 2030.”

It must not infer whether that goal should be prioritized.

---

## Component 3 — Financial Core and Simulation Engine

This is a normal Python domain library, not an agent.

### Responsibilities

* Monthly cash-flow aggregation
* Expense categorization rollups
* Essential versus discretionary classification
* Savings rate
* Debt-service ratio
* Emergency-fund coverage
* Irregular-income baseline
* Duplicate and transfer handling
* Goal feasibility
* Debt avalanche simulation
* Debt snowball simulation
* Cash allocation
* Constraint validation
* What-if scenarios

### Input contract: `CanonicalFinancialProfile`

```json
{
  "schema_version": "1.0",
  "case_id": "case-001",
  "profile_version": 3,
  "currency": "INR",
  "transactions": [],
  "assets": [
    {
      "asset_id": "asset-001",
      "type": "cash",
      "current_value": 250000,
      "liquidity": "high"
    }
  ],
  "debts": [
    {
      "debt_id": "debt-001",
      "type": "personal_loan",
      "balance": 300000,
      "annual_interest_rate": 13.5,
      "minimum_monthly_payment": 12000
    }
  ],
  "goals": [
    {
      "goal_id": "goal-001",
      "name": "Emergency fund",
      "target_amount": 600000,
      "target_date": "2027-06-01",
      "priority": "high"
    }
  ],
  "assumptions": []
}
```

### Output contract: `FinancialSnapshot`

```json
{
  "schema_version": "1.0",
  "analysis_id": "analysis-001",
  "profile_version": 3,
  "period": {
    "start": "2026-01-01",
    "end": "2026-06-30"
  },
  "metrics": {
    "baseline_monthly_income": 180000,
    "average_monthly_expenses": 128000,
    "monthly_surplus": 52000,
    "savings_rate_percent": 28.89,
    "debt_service_ratio_percent": 20,
    "emergency_fund_months": 2.1
  },
  "risk_flags": [
    {
      "code": "EMERGENCY_FUND_BELOW_MINIMUM",
      "severity": "high",
      "metric_refs": [
        "emergency_fund_months"
      ]
    }
  ],
  "goal_results": [
    {
      "goal_id": "goal-001",
      "funding_gap": 350000,
      "required_monthly_contribution": 29167,
      "feasibility": "achievable"
    }
  ],
  "debt_comparison": {
    "avalanche": {
      "months": 28,
      "total_interest": 94300
    },
    "snowball": {
      "months": 30,
      "total_interest": 102700
    }
  },
  "invariants": {
    "allocations_within_surplus": true,
    "all_minimum_debt_payments_met": true,
    "calculation_checks_passed": true
  }
}
```

### Tool interfaces

```text
calculate_financial_snapshot(profile)
simulate_goal(goal, constraints, profile)
compare_debt_strategies(debts, extra_payment)
simulate_budget_change(category_adjustments)
validate_plan(plan, snapshot)
```

Every tool must be pure or idempotent and independently testable.

---

## Component 4 — Knowledge, RAG and Tool Gateway

This is the only component allowed to access:

* The vector store
* External web search
* MCP servers
* Current reference information
* Curated financial documents

### Responsibilities

* Corpus ingestion
* Chunking and metadata
* Embedding generation
* Hybrid retrieval
* Optional reranking
* Citation construction
* Allowed-source filtering
* Freshness checks
* Web result normalization
* MCP authentication and policy enforcement
* Cost and call limits

### Input contract: `EvidenceRequest`

```json
{
  "schema_version": "1.0",
  "case_id": "case-001",
  "topics": [
    "emergency_fund",
    "high_interest_debt"
  ],
  "jurisdiction": "IN",
  "as_of": "2026-07-18",
  "audience": "individual_consumer",
  "max_chunks": 4,
  "allowed_publishers": [
    "RBI",
    "SEBI",
    "AMFI",
    "PFRDA",
    "IRDAI",
    "Income Tax Department"
  ],
  "freshness": "versioned"
}
```

### Output contract: `EvidenceBundle`

```json
{
  "schema_version": "1.0",
  "evidence_bundle_id": "evidence-001",
  "evidence": [
    {
      "evidence_id": "ev-001",
      "topic": "emergency_fund",
      "publisher": "RBI",
      "title": "Financial Awareness Material",
      "chunk_id": "rbi-fame-12",
      "text": "Relevant extracted guidance...",
      "published_at": "2017-03-10",
      "effective_from": null,
      "effective_to": null,
      "retrieved_at": "2026-07-18T10:30:00Z",
      "source_type": "official_guidance",
      "retrieval_score": 0.91
    }
  ],
  "warnings": []
}
```

### RAG source documents

For an Indian financial coach, seed the corpus from:

* RBI financial-literacy and Financial Awareness Messages material
* SEBI Investor financial-planning and securities-market education
* AMFI Investor Corner for mutual-fund concepts
* PFRDA subscriber education and retirement-planning material
* IRDAI policyholder education
* Income Tax Department pages for tax-related information
* NCFE financial-education material

RBI publishes institution-neutral literacy material covering budgeting, saving, responsible borrowing, credit discipline, regulated entities and consumer protection. SEBI offers financial-planning and investment education; AMFI maintains mutual-fund education; PFRDA covers retirement and pension education; IRDAI maintains policyholder resources; and tax content should come from the official Income Tax portal. ([Reserve Bank of India][3])

### Required metadata

```text
publisher
jurisdiction
document_type
topic
published_at
effective_from
effective_to
last_verified_at
source_hash
language
section
risk_tags
```

### Static versus live information

Store in RAG:

* Budgeting principles
* General debt strategies
* Consumer-protection guidance
* Educational information
* Stable product definitions

Use web/API tools for:

* Current tax rules
* Current policy limits
* Current interest rates
* Current scheme rules
* Current market data

Every live result must include an “as of” timestamp.

---

## Component 5 — LangGraph Multi-Agent Planning Runtime

This component coordinates the workflow. It should not parse PDFs, calculate EMI schedules or perform direct web searches.

LangGraph subgraphs are particularly suited to independent development because a team can implement a subgraph behind a fixed input/output schema while the parent graph remains unaware of its internals. ([Docs by LangChain][4])

## Parent graph

```text
START
  ↓
load_case
  ↓
check_extraction_status
  ├── review required → interrupt_for_extraction_review
  └── confirmed
  ↓
calculate_financial_snapshot
  ↓
completeness_gate
  ├── critical information missing → Clarification Agent
  └── sufficient
  ↓
select_relevant_skills
  ↓
retrieve_evidence
  ↓
run_goal_planner
  ↓
run_strategy_synthesizer
  ↓
deterministic_plan_validation
  ├── failed → repair_strategy
  └── passed
  ↓
review_agent
  ↓
interrupt_for_user_approval
  ↓
finalize_plan
  ↓
END
```

## Agent 1 — Clarification Agent

Purpose:

* Ask only questions that materially affect calculations
* Explain why each question is needed
* Permit skipping optional questions

Tools:

```text
get_missing_fields
get_low_confidence_items
save_user_answer
mark_field_unknown
```

Output:

```json
{
  "questions": [
    {
      "question_id": "q-001",
      "field": "debt-001.interest_rate",
      "question": "What is the annual interest rate on this loan?",
      "reason": "Required to compare payoff strategies.",
      "blocking": true,
      "skippable": true
    }
  ]
}
```

## Agent 2 — Goal Planner

Purpose:

* Order goals
* Identify dependencies
* Suggest deadline or amount adjustments
* Respect explicit user priorities
* Produce candidate allocations

Tools:

```text
simulate_goal
calculate_required_contribution
calculate_emergency_fund_target
validate_goal_dependencies
retrieve_evidence
```

The Goal Planner does not calculate values itself.

## Agent 3 — Strategy Synthesizer

Purpose:

* Combine budgeting, savings and debt results
* Compare valid strategies
* Preserve user constraints
* Generate a phased roadmap

Skills loaded selectively:

```text
budget-adjustment
emergency-fund
debt-payoff
goal-prioritization
cashflow-stabilization
```

This is better than separate “Budget Advisor” and “Savings Strategist” agents that may contradict one another.

## Agent 4 — Review and Safety Agent

Purpose:

* Detect unsupported claims
* Check assumption disclosure
* Verify that every recommendation has:

  * A calculator result
  * User-provided evidence
  * Or an approved RAG/web citation
* Reject specific security/product recommendations outside scope
* Ensure educational-advice language

### LangGraph state

```json
{
  "thread_id": "thread-001",
  "case_id": "case-001",
  "profile_version": 3,
  "extraction_id": "ext-001",
  "analysis_id": "analysis-001",
  "pending_review_ids": [],
  "missing_fields": [],
  "goal_ids": [
    "goal-001",
    "goal-002"
  ],
  "constraint_set": {
    "minimum_sip": 10000,
    "maximum_monthly_allocation": 52000
  },
  "evidence_bundle_id": "evidence-001",
  "candidate_plan_ids": [],
  "final_plan_id": null,
  "errors": [],
  "model_budget": {
    "maximum_model_calls": 5,
    "maximum_web_calls": 2,
    "maximum_retrieved_chunks": 4
  }
}
```

Do not put:

* Raw PDF bytes
* Hundreds of transactions
* Entire retrieved documents
* Full prompts from previous nodes

into graph state.

LangGraph checkpointing can persist state by thread, support interrupts and resume from failed steps. ([Docs by LangChain][5])

### Output contract: `PlanPackage`

```json
{
  "schema_version": "1.0",
  "plan_id": "plan-001",
  "case_id": "case-001",
  "profile_version": 3,
  "analysis_id": "analysis-001",
  "plan_version": 1,
  "status": "awaiting_user_approval",
  "allocations": [
    {
      "goal_id": "goal-001",
      "monthly_amount": 30000,
      "start_month": "2026-08",
      "duration_months": 4,
      "priority": 1
    }
  ],
  "actions": [
    {
      "action_id": "action-001",
      "time_horizon": "immediate",
      "description": "Build a minimum emergency buffer.",
      "calculation_refs": [
        "analysis-001:emergency_fund_months"
      ],
      "evidence_ids": [
        "ev-001"
      ]
    }
  ],
  "constraints": {
    "satisfied": true,
    "violations": []
  },
  "assumptions": [],
  "confidence": {
    "overall": 0.88,
    "reasons": [
      "All required debt fields were provided.",
      "Six months of statement data were available."
    ]
  }
}
```

---

## Component 6 — Report, Tracker and Export Service

### Responsibilities

* Convert approved plan into HTML
* Render PDF
* Generate monthly tracker CSV
* Generate report manifest
* Include calculation explanations
* Include source references
* Include assumptions and limitations
* Version reports
* Preserve reproducibility

### Input contract

```json
{
  "schema_version": "1.0",
  "case_id": "case-001",
  "report_request_id": "rr-001",
  "profile_version": 3,
  "analysis_id": "analysis-001",
  "plan_id": "plan-001",
  "evidence_bundle_id": "evidence-001",
  "format": [
    "html",
    "pdf",
    "csv_tracker"
  ]
}
```

### Output contract: `ReportArtifact`

```json
{
  "schema_version": "1.0",
  "report_id": "report-001",
  "report_version": 1,
  "status": "generated",
  "artifacts": {
    "html_uri": "private://reports/report-001.html",
    "pdf_uri": "private://reports/report-001.pdf",
    "tracker_uri": "private://reports/report-001.csv"
  },
  "manifest": {
    "profile_version": 3,
    "analysis_id": "analysis-001",
    "plan_id": "plan-001",
    "evidence_ids": [
      "ev-001"
    ],
    "generated_at": "2026-07-18T10:45:00Z",
    "content_hash": "xyz789"
  }
}
```

The LLM may polish explanatory prose. It must not regenerate numeric values.

# 4. Shared contract rules

Every component should use the same envelope:

```json
{
  "schema_version": "1.0",
  "request_id": "req-001",
  "case_id": "case-001",
  "producer": "financial-core",
  "produced_at": "2026-07-18T10:30:00Z",
  "data": {},
  "warnings": [],
  "errors": []
}
```

## Mandatory rules

1. **All IDs originate upstream.**
   Downstream components reuse IDs.

2. **All outputs are immutable and versioned.**

3. **No free-form agent boundary.**
   Every agent returns schema-constrained JSON.

4. **No agent writes directly to the database.**
   Persistence happens through repositories/application services.

5. **Every extracted value includes provenance.**

6. **Every recommendation includes calculation references or evidence IDs.**

7. **Unknown values remain null.**
   Models must not invent them.

8. **Every write endpoint accepts an idempotency key.**

9. **Enums are frozen.**

```text
severity:
low | medium | high | critical

confidence_status:
verified | likely | uncertain | unknown

plan_status:
draft | awaiting_user_input | awaiting_user_approval |
approved | superseded | failed
```

10. **Schema changes require a version bump.**

OpenAI’s Structured Outputs examples emphasize using defined JSON schemas to bridge probabilistic model output with deterministic application workflows. ([GitHub][6])

# 5. Persistent storage design

## PostgreSQL

Suggested logical schemas:

```text
identity:
user_mapping
consents
sessions_metadata

cases:
cases
case_members
case_status

finance:
accounts
transactions
assets
debts
goals
profile_versions
user_corrections

analysis:
financial_snapshots
simulations
risk_flags

planning:
graph_runs
plans
plan_versions
plan_actions
approvals

knowledge:
sources
documents
chunks
source_versions

reporting:
reports
report_artifacts

quality:
eval_datasets
eval_runs
eval_results
model_usage

audit:
audit_events
security_events
```

## Object storage

Use S3-compatible storage or MinIO locally:

```text
/uploads/{tenant_id}/{case_id}/{document_id}
/extraction/{document_id}/pages/
/reports/{case_id}/{report_id}/
```

## Vector storage

For the hackathon, use PostgreSQL with `pgvector` instead of operating a separate vector database.

Do not put user transaction history in the RAG index.

## LangGraph persistence

Use a Postgres checkpointer keyed by:

```text
tenant_id
case_id
thread_id
```

## Optional Redis

Only add Redis for:

* Job status
* Short-lived caching
* Rate limiting

Do not add it unless needed.

# 6. OAuth and consent

## Clerk

Use Clerk for:

* Login
* Social OAuth
* Session management
* User identity

Backend flow:

```text
Browser gets Clerk session
→ sends token to BFF/API
→ API validates token
→ reads token subject
→ maps subject to internal principal_id
→ applies tenant and case authorization
```

## Separate consent records

```json
{
  "consent_id": "consent-001",
  "principal_id": "internal-user-123",
  "purpose": "financial_analysis",
  "data_categories": [
    "bank_statements",
    "loans",
    "investments"
  ],
  "granted_at": "2026-07-18T10:00:00Z",
  "revoked_at": null,
  "retention_days": 30
}
```

## Security essentials

* Encrypt storage
* Mask account numbers and PAN
* Never log PDF contents
* Delete temporary page images
* Add tenant ID to every query
* Treat PDF text as untrusted data
* Block prompt instructions found inside statements
* Keep provider keys server-side
* Record all user corrections
* Let users delete cases and uploaded data

# 7. MCP recommendations

Use MCP only through Component 4.

## Useful MCPs

### Filesystem MCP

Use it during development for:

* Reading the curated knowledge corpus
* Loading report templates
* Accessing fixtures

Mount only an approved read-only directory.

### Fetch MCP

Use it for controlled corpus-refresh jobs:

* Fetch only RBI, SEBI, AMFI, PFRDA, IRDAI and Income Tax sources
* Do not give it arbitrary internet access from the planning agents

### Postgres MCP or custom read-only financial-data MCP

Useful for demonstrating agent-accessible structured resources.

Expose only approved views such as:

```text
financial_snapshot_view
goal_summary_view
plan_history_view
```

Do not expose unrestricted SQL.

### Drive connector MCP

Optional for:

* Importing a statement selected by the user
* Exporting the final report

This requires separate user consent and token handling.

The official MCP server collection warns that its reference servers are educational implementations rather than production-ready systems, so you should evaluate and harden their security before using them with financial data. ([GitHub][7])

## MCP policy contract

```json
{
  "tool_name": "official_document_fetch",
  "access": "read_only",
  "allowed_domains": [
    "rbi.org.in",
    "investor.sebi.gov.in",
    "amfiindia.com",
    "pfrda.org.in",
    "irdai.gov.in",
    "incometax.gov.in"
  ],
  "timeout_seconds": 10,
  "maximum_results": 5,
  "requires_user_approval": false,
  "cache_ttl_seconds": 86400
}
```

# 8. Evaluation architecture

Use a completely separate `evals/` package.

OpenAI Evals supports schema-defined data sources and multiple grader types, including deterministic checks and model-based grading. The Cookbook recommends an evaluation flywheel of analyzing failures, measuring them with datasets and graders, and making targeted improvements. ([OpenAI Platform][8])

## Data Ingestion Eval

Dataset:

* Digital bank statements
* Scanned bank statements
* Wrapped transaction rows
* Refunds
* Duplicate entries
* Swapped debit/credit columns
* Multiple date formats

Metrics:

```text
document classification accuracy
field exact-match accuracy
transaction row precision/recall
date accuracy
amount accuracy
reconciliation pass rate
source-provenance coverage
low-confidence detection recall
latency
cost
```

Use deterministic graders.

---

## Financial Core Eval

Use unit and property-based tests.

Required invariants:

```text
opening + credits - debits = closing
allocated monthly amount <= available surplus
minimum debt payments are always covered
debt balance never becomes negative
goal contribution cannot be negative
snowball and avalanche totals reconcile
changing narrative cannot alter numbers
```

No LLM judge.

---

## RAG Eval

Dataset of questions with expected source sections.

Metrics:

```text
Recall@3
MRR
publisher correctness
jurisdiction correctness
effective-date validity
citation resolution rate
unsupported claim rate
retrieved-token count
```

---

## Goal Planner Eval

Scenarios:

* Multiple conflicting goals
* Negative cash flow
* Emergency fund absent
* High-interest debt
* Irregular income
* Non-negotiable SIP
* Impossible target date
* User changes priority

Metrics:

```text
constraint satisfaction
feasibility correctness
required-contribution correctness
priority alignment
assumption disclosure
unsupported recommendation rate
```

All numeric metrics should be deterministic.

---

## Strategy Eval

Use a mixture:

### Deterministic graders

* No constraint violation
* No invented values
* All action amounts total correctly
* Required citations exist
* No prohibited product recommendations

### Model grader

Only for:

* Explanation clarity
* Personalization
* Actionability
* Whether trade-offs are understandable

Do not let the model grader override failed calculations.

---

## Report Eval

Check:

* All report values match the snapshot
* Every evidence ID resolves
* All assumptions are shown
* Report version is reproducible
* CSV tracker totals agree with roadmap
* PDF renders without clipping

# 9. Model and token policy

## Model usage

```text
PDF parsing:
open-source parser/OCR first

Ambiguous field extraction:
small multimodal or text model

Transaction classification:
rules → embeddings → small classifier → LLM fallback

Clarification:
low-cost model

Goal planning:
strong reasoning model

Strategy explanation:
mid-tier model

Safety review:
rules first, low-cost model second

Calculations:
Python only
```

## Open-source Hugging Face models

Reasonable uses:

```text
Embeddings:
BAAI/bge-small-en-v1.5
or intfloat/e5-small-v2

Transaction classification:
a compact DeBERTa classifier or your own small fine-tuned model

OCR/layout fallback:
PaddleOCR, DocTR or LayoutLMv3 where genuinely required
```

## Token controls

* Never send all transactions to an agent
* Send monthly summaries and exceptions
* Retrieve no more than three or four chunks
* Batch ambiguous transactions
* Cache normalized merchants
* Cache embeddings
* Keep static prompt prefixes identical for caching
* Limit each run with a model budget

The OpenAI Cookbook contains dedicated examples for structured outputs, evaluation workflows and prompt caching, all directly relevant to this architecture. ([GitHub][6])

# 10. Repository design

```text
finpilot/
├── apps/
│   ├── web/                    # Component 1
│   └── api/
│
├── packages/
│   ├── contracts/              # shared, frozen schemas
│   ├── document_intelligence/  # Component 2
│   ├── financial_core/         # Component 3
│   ├── knowledge_gateway/      # Component 4
│   ├── coach_graph/            # Component 5
│   └── reporting/              # Component 6
│
├── evals/
│   ├── ingestion/
│   ├── retrieval/
│   ├── financial_core/
│   ├── goal_planner/
│   ├── strategy/
│   └── end_to_end/
│
├── fixtures/
│   ├── extraction_bundle.json
│   ├── financial_snapshot.json
│   ├── evidence_bundle.json
│   ├── plan_package.json
│   └── report_artifact.json
│
├── knowledge/
├── migrations/
├── infra/
└── docker-compose.yml
```

Each package must expose:

```text
schemas.py
service.py
interfaces.py
errors.py
tests/
fixtures/
```

# 11. Integration discipline

## Freeze these before coding

* Schema versions
* Field names
* ID ownership
* Enums
* Error codes
* Null behavior
* Confidence rules
* Currency handling
* Date format
* Report manifest
* LangGraph state

## UI development

The UI person uses fixture JSON immediately.

```text
USE_MOCK_INGESTION=true
USE_MOCK_ANALYTICS=true
USE_MOCK_PLANNING=true
```

During integration, only environment flags change. UI components should not be rewritten.

## Contract tests

Each module must pass:

```text
valid fixture accepted
missing required field rejected
unknown optional field tolerated or rejected consistently
schema version validated
upstream IDs preserved
output validates against JSON Schema
```

## Suggested 3–4 hour integration block

### First hour

* Start application and database
* Run all contract tests
* Connect UI → ingestion → review
* Fix only schema mismatches

### Second hour

* Connect financial core
* Connect LangGraph and Postgres checkpointer
* Test interruption and resume

### Third hour

* Connect RAG/tool gateway
* Generate the plan and report
* Test one what-if update

### Fourth hour

* Test invalid PDF
* Test missing debt rate
* Test RAG outage
* Test model timeout
* Run final demo twice
* Freeze code

# Final architecture decision

Keep these as agents:

```text
Clarification Agent
Goal Planner Agent
Strategy Synthesizer Agent
Review/Safety Agent
```

Keep these as deterministic tools:

```text
PDF/table parsing
transaction normalization
spend analysis
financial metrics
debt analysis
goal simulations
constraint validation
report rendering
```

Keep these behind one gateway:

```text
RAG
web search
MCP
current regulatory information
```

And keep this outside runtime:

```text
model comparison
LLM-as-judge
regression evaluation
prompt optimization
```

The most important architectural sentence for your judges is:

> **LangGraph coordinates ambiguity, decisions and human review; deterministic services handle money; RAG supplies governed evidence; and every boundary is enforced by versioned structured contracts.**

[1]: https://docs.langchain.com/oss/python/langchain/human-in-the-loop?utm_source=chatgpt.com "Human-in-the-loop - Docs by LangChain"
[2]: https://clerk.com/docs/reference/backend/verify-token?utm_source=chatgpt.com "verifyToken() - clerkClient | Clerk Docs"
[3]: https://www.rbi.org.in/commonperson/English/Scripts/PressReleases.aspx?Id=2123&utm_source=chatgpt.com "Reserve Bank of India"
[4]: https://docs.langchain.com/oss/python/langgraph/use-subgraphs?utm_source=chatgpt.com "Subgraphs - Docs by LangChain"
[5]: https://docs.langchain.com/oss/javascript/langgraph/persistence?utm_source=chatgpt.com "Persistence - Docs by LangChain"
[6]: https://github.com/openai/openai-cookbook/blob/main/examples/Structured_Outputs_Intro.ipynb?utm_source=chatgpt.com "openai-cookbook/examples/Structured_Outputs_Intro.ipynb at main · openai/openai-cookbook · GitHub"
[7]: https://github.com/modelcontextprotocol/servers?utm_source=chatgpt.com "GitHub - modelcontextprotocol/servers: Model Context Protocol Servers · GitHub"
[8]: https://platform.openai.com/docs/api-reference/evals/deleteRun?lang=python&utm_source=chatgpt.com "Evals | OpenAI API Reference"
