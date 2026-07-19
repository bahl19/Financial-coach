"""Phase 8 tests: app.py (Streamlit integration).

Each test maps to a Phase 8 exit-gate item in `Implementation Plan - MVP 1.md`.
Uses `streamlit.testing.v1.AppTest` (a headless Streamlit test harness)
wherever a widget interaction is drivable. `AppTest` in this Streamlit
version has no query interface for `st.data_editor`/`st.form_submit_button`
(no `.data_editor`/`.form_submit_button` attribute exists on the harness),
so the two gate items that depend on editing a data_editor - category
correction and the scenario-preview form - are verified instead by calling
the underlying pure functions those widgets feed
(`utils.ingestion.apply_category_corrections`, `utils.scenarios.*`)
directly, which is what actually produces the output in question.
"""

import pandas as pd
from streamlit.testing.v1 import AppTest

from agents import graph as g
from agents.orchestrator import build_chat_reply
from utils import finance_calc as fc
from utils import ingestion


def _load_sample_and_analyze(at: AppTest, monthly_income: float = 75000.0) -> AppTest:
    at.run()
    at.sidebar.button(key="load_sample_button").click().run()
    at.number_input(key="monthly_income_input").set_value(monthly_income).run()
    at.button(key="analyze_button").click().run()
    return at


# --------------------------------------------------------------------------
# Gate: "One full end-to-end sample path works offline"
# --------------------------------------------------------------------------

def test_full_sample_path_works_offline_with_no_exception():
    from utils.llm import is_live
    assert not is_live(), "this test asserts the offline path; an OPENROUTER_API_KEY is set in this environment"

    at = AppTest.from_file("app.py", default_timeout=30)
    _load_sample_and_analyze(at)
    assert not at.exception
    # 7 analysis tabs (Overview..Chat) + 5 Scenario Comparison sub-tabs -
    # at.tabs collects tabs globally across the whole script, not scoped to
    # one st.tabs() call, so this checks both groups' labels are present
    # rather than a single flat count.
    tab_labels = [t.label for t in at.tabs]
    for label in (
        "\U0001f4ca Overview", "\U0001f9fe Spending", "\U0001f4b3 Debt Payoff", "\U0001f3e6 Savings",
        "\U0001f4cb Budget", "\U0001f3af Goals", "\U0001f4ac Ask the Coach",
    ):
        assert label in tab_labels
    for label in (
        "Plan assumptions", "Idle savings vs. investing", "Cut discretionary spending",
        "Prepay debt vs. invest", "FD / PPF / SIP for a goal",
    ):
        assert label in tab_labels


# --------------------------------------------------------------------------
# Gate: "App does not run analysis before required inputs validate"
# --------------------------------------------------------------------------

def test_analyze_button_disabled_until_monthly_income_is_set():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    at.sidebar.button(key="load_sample_button").click().run()
    assert not at.exception
    # The bundled sample data has income transactions, so Step 3's income
    # field is pre-filled from the most recent one (see
    # app.py::_suggest_monthly_income) rather than defaulting to 0 - the
    # button is enabled immediately, which is the point of the pre-fill.
    assert not at.button(key="analyze_button").disabled

    # Explicitly zeroing income (the case the pre-fill can't rescue - no
    # income transaction, or the user clears the field) must still gate.
    at.number_input(key="monthly_income_input").set_value(0.0).run()
    assert at.button(key="analyze_button").disabled
    assert len(at.tabs) == 0
    assert not any(h.value == "Step 4 - Analysis" for h in at.header)


def test_analyze_button_enables_once_income_is_confirmed_and_analysis_runs():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    at.sidebar.button(key="load_sample_button").click().run()
    at.number_input(key="monthly_income_input").set_value(75000.0).run()
    assert not at.button(key="analyze_button").disabled
    at.button(key="analyze_button").click().run()
    assert not at.exception
    assert any(h.value == "Step 4 - Analysis" for h in at.header)


def test_monthly_income_is_prefilled_from_the_most_recent_income_transaction():
    """Closes a real usability gap: Step 3 used to default income to 0 and
    ask the user to type a number from scratch that could silently disagree
    with the just-uploaded statement. It now suggests the most recent
    Income-category transaction's amount as a starting point instead."""
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    at.sidebar.button(key="load_sample_button").click().run()
    assert not at.exception
    assert at.number_input(key="monthly_income_input").value == 75000.0


# --------------------------------------------------------------------------
# Gate: "Editing a review category changes the resulting spending/budget
# output" - data_editor is not drivable through AppTest, so this verifies
# the pure function app.py calls with the data_editor's return value.
# --------------------------------------------------------------------------

def test_editing_a_review_category_changes_spending_by_category_output():
    raw = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-05", "2026-01-10"]),
        "description": ["Some Obscure Merchant XYZ", "Whole Foods"],
        "amount": [-75.0, -100.0],
    })
    tagged = ingestion.tag_transaction_types(ingestion.categorize_with_confidence(raw))
    review_items = ingestion.build_review_items(tagged)
    assert len(review_items) == 1
    assert review_items[0]["suggested_category"] == "Other"

    before = fc.spending_by_category(tagged)
    corrected = ingestion.apply_category_corrections(tagged, {review_items[0]["transaction_index"]: "Dining"})
    after = fc.spending_by_category(corrected)

    assert set(before["category"]) == {"Other", "Groceries"}
    assert set(after["category"]) == {"Dining", "Groceries"}
    # the correction must also propagate into transaction_type, not just category
    assert corrected.loc[review_items[0]["transaction_index"], "transaction_type"] == "expense"
    assert corrected.loc[review_items[0]["transaction_index"], "needs_review"] == False  # noqa: E712
    assert corrected.loc[review_items[0]["transaction_index"], "category_confidence"] == 1.0


# --------------------------------------------------------------------------
# Currency/region selectors: independent settings added alongside the
# original INR-only, India-only defaults - "india"/"INR" must remain the
# unchanged default, and switching either must actually take effect.
# --------------------------------------------------------------------------

def test_currency_selector_changes_the_rendered_money_symbol():
    at = _load_sample_and_analyze(AppTest.from_file("app.py", default_timeout=30))
    assert not at.exception
    overview_metrics = {m.label: m.value for m in at.metric}
    assert overview_metrics["Gross surplus"].startswith("₹")  # default currency is INR

    # Switching currency changes assumptions, which invalidates the last
    # analysis (utils/app_state.py's set_profile_fields) - re-confirm, same
    # as a real user would after changing any Step 3 input.
    at.selectbox(key="currency_select").select("USD").run()
    at.button(key="analyze_button").click().run()
    assert not at.exception
    overview_metrics = {m.label: m.value for m in at.metric}
    assert overview_metrics["Gross surplus"].startswith("$")
    assert "₹" not in overview_metrics["Gross surplus"]


def test_region_selector_changes_categorization_of_india_vendor_transactions():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    at.sidebar.button(key="load_sample_button").click().run()
    assert not at.exception

    india_default_df = at.session_state["categorized_df"]
    swiggy_row = india_default_df[india_default_df["description"] == "Swiggy Order"].iloc[0]
    assert swiggy_row["category"] == "Dining"  # india is the default region

    at.selectbox(key="region_select").select("generic").run()
    assert not at.exception
    generic_df = at.session_state["categorized_df"]
    swiggy_row_generic = generic_df[generic_df["description"] == "Swiggy Order"].iloc[0]
    assert swiggy_row_generic["category"] == "Other"
    # needs_review is False here, not True: rendering the review editor for
    # the first time (triggered by these rows newly needing review) round-
    # trips through apply_category_corrections() even unedited, which always
    # finalizes at confidence 1.0 - the same behavior
    # test_editing_a_review_category_changes_spending_by_category_output
    # exercises directly. The real proof region took effect is the category
    # itself flipping to "Other".


# --------------------------------------------------------------------------
# Gate: "Download buttons work in offline mode (no OpenRouter key)"
# --------------------------------------------------------------------------

def test_download_buttons_present_and_enabled_offline():
    at = _load_sample_and_analyze(AppTest.from_file("app.py", default_timeout=30))
    assert not at.exception
    labels = [d.label for d in at.download_button]
    assert "\U0001f4c4 Download report (Markdown)" in labels
    assert "\U0001f4ca Download tracker (CSV)" in labels
    assert not any(d.disabled for d in at.download_button)


# --------------------------------------------------------------------------
# Gate: "Specialist tabs and chat work with the generated profile context"
# and "... are served through the same LangGraph nodes as the overview
# (consistent output across tabs)"
# --------------------------------------------------------------------------

def test_specialist_tabs_render_real_content_from_the_graph_result():
    at = _load_sample_and_analyze(AppTest.from_file("app.py", default_timeout=30))
    spending_md = "\n".join(m.value for m in at.tabs[1].markdown)
    debt_md = "\n".join(m.value for m in at.tabs[2].markdown)
    savings_md = "\n".join(m.value for m in at.tabs[3].markdown)
    budget_md = "\n".join(m.value for m in at.tabs[4].markdown)
    assert spending_md and debt_md and savings_md and budget_md


def test_chat_reply_is_byte_identical_to_the_matched_specialist_narrative():
    """Proves there is exactly one orchestration path: a debt-routed chat
    query must return the *same* narrative object the Debt Payoff tab
    already rendered from this run's one `run_graph()` call, not a second
    LLM/agent invocation."""
    at = _load_sample_and_analyze(AppTest.from_file("app.py", default_timeout=30))
    graph_result = at.session_state["graph_result"]

    at.chat_input[0].set_value("Should I pay off my credit card debt?").run()
    assert not at.exception
    chat_md = [m.value for m in at.tabs[6].markdown]
    assert graph_result["debt_result"]["narrative"] in chat_md


def test_build_chat_reply_reuses_graph_result_narratives_directly():
    from utils.contracts import default_assumptions

    transactions = [
        {
            "date": "2026-01-01", "description": "Employer Payroll", "amount": 5000.0, "category": "Income",
            "category_confidence": 1.0, "needs_review": False, "transaction_type": "income",
        },
        {
            "date": "2026-01-05", "description": "Landlord LLC", "amount": -1500.0, "category": "Rent/Mortgage",
            "category_confidence": 1.0, "needs_review": False, "transaction_type": "expense",
        },
    ]
    profile = {
        "schema_version": "1.0", "transactions": transactions, "monthly_income": 5000.0, "current_savings": 1000.0,
        "debts": [{"name": "Card", "balance": 1000.0, "apr": 25.0, "min_payment": 50.0}], "goals": [],
        "constraints": {"minimum_monthly_buffer": 100.0, "protected_categories": []},
        "assumptions": default_assumptions(),
    }
    transactions_df = fc._transactions_to_frame(profile["transactions"])
    flags = ingestion.detect_data_quality_issues(transactions_df)
    snapshot = fc.calculate_financial_snapshot(profile, data_quality_flags=flags)
    trends = fc.compute_trends(profile, snapshot)
    findings = fc.derive_findings(snapshot, trends)
    risks = fc.derive_risks(snapshot, findings)
    graph_result = g.run_graph(profile, snapshot, findings, risks, trends)

    reply = build_chat_reply("What should I do about my debt?", graph_result)
    assert reply == graph_result["debt_result"]["narrative"]


# --------------------------------------------------------------------------
# Gate: "Overview tab renders the Coach Summary, not a concatenation of
# five agent outputs"
# --------------------------------------------------------------------------

def test_overview_tab_renders_coach_summary_not_raw_specialist_narratives():
    at = _load_sample_and_analyze(AppTest.from_file("app.py", default_timeout=30))
    graph_result = at.session_state["graph_result"]
    overview_md = "\n".join(m.value for m in at.tabs[0].markdown)

    assert graph_result["coach_summary"]["overall_health"] in overview_md
    for key in ("spending_result", "budget_result", "savings_result", "debt_result"):
        narrative = graph_result[key]["narrative"]
        assert narrative not in overview_md, f"Overview leaked {key}'s raw narrative instead of the Coach Summary"


# --------------------------------------------------------------------------
# Gate: "A triggered validator fallback is visible in the UI"
# --------------------------------------------------------------------------

def test_validator_fallback_is_surfaced_as_a_warning():
    at = _load_sample_and_analyze(AppTest.from_file("app.py", default_timeout=30))
    assert not any(at.warning)  # no fallback in the ordinary offline run

    at.session_state["graph_result"]["validation_result"]["fallback_used"] = True
    at.run()
    assert not at.exception
    assert any("consistency check" in w.value for w in at.warning)


# --------------------------------------------------------------------------
# Scenario Comparison: "cut discretionary spending" - bug found while
# smoke-testing this feature. A confirmed_monthly_expenses override (Step 3
# pre-fills and confirms this for every profile) shadowed the scenario's
# transaction-level cut entirely, since calculate_financial_snapshot() reads
# the override instead of recomputing from the (now-reduced) transactions -
# the comparison silently showed zero effect no matter the cut percentage.
# --------------------------------------------------------------------------

def test_cut_discretionary_spending_scenario_actually_changes_the_comparison():
    at = _load_sample_and_analyze(AppTest.from_file("app.py", default_timeout=30))
    assert not at.exception
    assert at.session_state["pipeline_inputs"][0].get("confirmed_monthly_expenses") is not None  # the shadowing precondition

    dataframes = at.tabs[9].dataframe  # "Cut discretionary spending" sub-tab
    assert len(dataframes) == 1
    comparison_df = dataframes[0].value
    assert comparison_df.loc["Gross surplus", "delta"] > 0  # cutting spending must raise surplus, not leave it at 0


# --------------------------------------------------------------------------
# Gate: "Golden tests from Phase 6 still pass" is verified by the full
# suite, not re-implemented here.
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# Logto authentication gating (utils/auth.py). The real OIDC redirect
# round-trip against Logto's hosted sign-in page cannot be driven headlessly
# (same category of AppTest limitation as st.data_editor - see this file's
# module docstring); what's tested here is that app.py's gate actually
# blocks/unblocks the rest of the script, using monkeypatched auth state
# exactly like test_full_sample_path_works_offline_with_no_exception already
# asserts the *disabled* case implicitly by running the full flow unchanged.
# --------------------------------------------------------------------------

def test_auth_disabled_by_default_leaves_the_existing_app_unaffected():
    from utils import auth as authn
    assert authn.auth_enabled() is False, "no .streamlit/secrets.toml is committed; this must stay the default in CI"


def test_signed_out_user_sees_login_screen_and_nothing_else_when_auth_enabled(monkeypatch):
    from utils import auth as authn

    monkeypatch.setattr(authn, "auth_enabled", lambda: True)
    monkeypatch.setattr(authn, "is_logged_in", lambda: False)

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()

    assert not at.exception
    assert any("Sign in" in b.label for b in at.button)
    # None of the ordinary app's widgets (only reachable past the auth gate)
    # were ever rendered - st.stop() must have fired before app.py's own
    # sidebar/upload widgets ran.
    assert not any(b.key == "load_sample_button" for b in at.sidebar.button)


def test_signed_in_user_reaches_the_ordinary_app_when_auth_enabled(monkeypatch):
    from utils import auth as authn

    monkeypatch.setattr(authn, "auth_enabled", lambda: True)
    monkeypatch.setattr(authn, "is_logged_in", lambda: True)
    monkeypatch.setattr(authn, "current_user_label", lambda: "test@example.com")

    at = _load_sample_and_analyze(AppTest.from_file("app.py", default_timeout=30))
    assert not at.exception
    assert any("test@example.com" in c.value for c in at.sidebar.caption)
