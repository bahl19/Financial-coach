# 💰 AI Financial Coach — Multi-Agent Financial Advisor

> Powered by OpenRouter · Multi-agent orchestration over your real income, spending, and debt

AI Financial Coach is a multi-agent system that ingests a user's income, transactions, and debts (via CSV/PDF upload) and dispatches specialist agents that each reason over a grounded slice of the user's real numbers — spending patterns, debt payoff math, savings targets, budget fit, and goal feasibility — synthesized into one live, interactive dashboard.

**🔗 Live app: [financialcoach.streamlit.app](https://financialcoach.streamlit.app/)**

---

## 🤖 Agent Architecture

| Agent | Grounded On | Role |
|-------|-------------|------|
| 📥 Data Ingestion | Uploaded CSV/PDF statement | Parses raw transaction lines into a clean table and auto-categorizes every entry |
| 🧾 Spending Analyzer | Categorized transactions | Top spending categories, monthly cash flow, month-over-month trend flags |
| 💳 Debt Analyzer | User-entered debts (balance, APR, min payment) | Simulates avalanche vs. snowball payoff, recommends a strategy with real interest/timeline numbers |
| 🏦 Savings Strategist | Income, expenses, current savings | Emergency fund target, monthly savings split, 24-month growth projection |
| 📋 Budget Advisor | Income, actual spending split | Compares actual spend to a 50/30/20 budget, flags specific over/under-spend by bucket |
| 🎯 Goal Planner | User-defined goals + surplus | Required monthly contribution and feasibility per goal |
| 🧭 Orchestrator | All of the above | Runs the full report, and routes free-text chat questions to the relevant specialist(s) |

Every agent computes its numbers **deterministically first** — the tabular RAG layer in `utils/finance_calc.py` — then hands those grounded figures to an LLM to turn into a natural-language recommendation. If no LLM key is configured, every agent falls back to a rule-based templated narrative, so the app is fully demoable offline.

---

## 🚀 Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/bahl19/Financial-coach.git
cd Financial-coach
```

### 2. Install dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Set up your API key
Create a `.env` file in the root folder (or copy `.env.example`):
```
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_MODEL=anthropic/claude-sonnet-4.5
```
No key? The app still runs fully offline with rule-based fallback narratives.

### 4. Run the app
```bash
streamlit run app.py
```

### 5. Load your data
Open **http://localhost:8501** (or the [live app](https://financialcoach.streamlit.app/)), click **"Load sample data"** for an instant demo, or upload your own CSV/PDF statement.

---

## 🏗️ Project Structure

```
FINANCIAL-COACH/
├── app.py                     # Streamlit dashboard + chat UI
├── agents/
│   ├── orchestrator.py         # Runs the full report; routes chat queries to specialists
│   ├── data_agent.py            # CSV/PDF statement ingestion
│   ├── spending_agent.py         # Spending Analyzer
│   ├── debt_agent.py              # Debt Analyzer (avalanche/snowball simulation)
│   ├── savings_agent.py            # Savings Strategist
│   ├── budget_agent.py              # Budget Advisor (50/30/20)
│   ├── goal_agent.py                 # Goal Planner
│   └── base.py                        # Shared LLM-call helper
├── utils/
│   ├── finance_calc.py         # Deterministic tabular calculations (the RAG layer)
│   └── llm.py                   # OpenRouter client wrapper with offline fallback
├── data/
│   └── sample_transactions.csv  # Bundled 3-month demo dataset
├── requirements.txt            # Dependencies
└── .env.example                # API key template (not committed)
```

---

## 🧠 How It Works

```
Transactions CSV/PDF + Debts + Goals
    ↓
Data Ingestion Agent     →  Clean, categorized transaction table
    ↓
Spending Analyzer Agent   →  Category totals, cash flow, trend flags
Debt Analyzer Agent        →  Avalanche vs. snowball payoff simulation      }  dispatched by
Savings Strategist Agent    →  Emergency fund target, growth projection     }  the Orchestrator
Budget Advisor Agent         →  Actual vs. 50/30/20 recommended split
Goal Planner Agent            →  Required monthly contribution per goal
    ↓
Streamlit Dashboard            →  Live charts, per-agent narratives, chat interface
```

Each specialist agent computes its figures directly from the transactions dataframe, then asks the LLM to turn those grounded numbers into a natural-language recommendation. If the LLM call fails or no API key is set, the agent falls back to a deterministic templated narrative built from the same numbers — nothing in the app depends on a live model connection to function.

The **chat tab** routes free-text questions ("Should I pay off my credit card or save more?") to the relevant specialist agent(s) by keyword match, then returns their narrative directly.

---

## 🛠️ Tech Stack

- **Frontend/App** — Streamlit
- **LLM Routing** — OpenRouter (any model slug — Claude, GPT, Llama, etc. via `OPENROUTER_MODEL`)
- **Data Processing** — pandas
- **Charts** — Plotly
- **Statement Parsing** — pdfplumber (PDF), pandas (CSV)
- **Agent Pattern** — One orchestrator dispatching independent specialist agents, each grounded in a computed slice of the data before calling the LLM

---

## 📊 Data Contract

### Transactions CSV
| Column | Type | Notes |
|---|---|---|
| `date` | date | Any pandas-parseable format |
| `description` | text | Merchant/memo line, used for auto-categorization |
| `amount` | number | **Expenses negative, income/deposits positive** |

### Debts
```json
{ "name": "Credit Card", "balance": 4200.0, "apr": 22.9, "min_payment": 120.0 }
```

### Goals
```json
{ "name": "Hawaii Vacation", "amount": 4000.0, "months": 10, "current": 200.0 }
```

Both are edited directly in the sidebar via an inline data table — no separate form is needed.

---

## 📋 Requirements

```
streamlit
pandas
numpy
plotly
openai
python-dotenv
pdfplumber
```

---

## ⚠️ Notes

- Auto-categorization is keyword-based (`utils/finance_calc.py: CATEGORY_KEYWORDS`) — uncommon merchant names fall back to `Other` (or `Income` for positive amounts).
- The Budget Advisor normalizes all-time spending to a monthly average before comparing it against the recommended 50/30/20 split, so partial months in the data don't skew the comparison.
- Debt payoff simulation rolls freed-up minimum payments from paid-off debts into the next target debt, matching how avalanche/snowball calculators are conventionally defined.

---

## 👨‍💻 Built By

C8 | Hackathon Group 13
GitHub: [github.com/bahl19](https://github.com/bahl19)

---

> "Your income, spending, and debt — turned into a plan, not just a dashboard."
