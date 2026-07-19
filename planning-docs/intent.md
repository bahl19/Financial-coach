#Intent of the Finance Coach app
We are building a web-app Finance coach.

The document proposes document-based analysis of income, spending and debt, followed by savings strategies, budget advice and optimized debt-payoff plans.

Your proposed workflow is directionally correct, but it needs to be narrowed for an 18-hour prototype.

**Recommended user journey**
1. Upload bank statement, mutual-fund statement, SIP summary or loan statement.
2. Alternatively, complete a basic financial questionnaire.
3. Extract and normalize transactions and holdings.
4. Ask the user to review uncertain classifications.
5. Calculate income, fixed expenses, discretionary expenses, debt and investments.
6. Ask for goals and constraints; allow skipping.
7. Calculate financial-health metrics.
8. Generate a prioritized roadmap.
9. Let the user adjust assumptions.
10. Export a report and monthly tracker.

**Concepts based on:**
1. Coding maturity and production-level design and product functionality (if less features, with high perfection)
2. Edge cases, real use-cases
3. Use of concepts of multi-agent with Skills+Tools, relevant free MCPs, RAGs + Embeddings, Langchain, Langgraph
4. Use of already existing high-grade open source models from Hugging face
5. No forced use of concepts/tools where not required and a simple algorithm or Open source tool would work great.
6. Cost aware design and Input Token usage 
7. Cost aware model selections for multi-agents
8. References from Learnings from OpenAI cookbook
