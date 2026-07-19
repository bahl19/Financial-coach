"""Phase 8 tests: utils/app_state.py (the session-state accessor module).

Regression tests for a bug found while smoke-testing app.py: `app.py`
recomputes and re-calls the profile-field/categorized-df setters on
*every* rerun (Streamlit reruns the whole script on any widget
interaction, not just when that widget's own value changed) - an
unconditional invalidation on every call wiped out a just-computed
`graph_result` the moment an unrelated widget (e.g. the chat input) fired
a rerun. Fixed by invalidating only on an actual value change.
"""

import pandas as pd
import streamlit as st

from utils import app_state


def _reset():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    app_state.init_state()


def test_set_profile_fields_with_unchanged_values_does_not_invalidate_analysis():
    _reset()
    fields = dict(
        monthly_income=5000.0, current_savings=1000.0, debts=[], goals=[],
        constraints={"minimum_monthly_buffer": 0.0, "protected_categories": []}, assumptions=None,
    )
    app_state.set_profile_fields(**fields)
    app_state.set_analysis_result(("p", "s", "t", "f", "r"), {"marker": "graph_ran"})

    # app.py calls this again, unconditionally, on every rerun
    app_state.set_profile_fields(**fields)
    assert app_state.get_graph_result() == {"marker": "graph_ran"}


def test_set_profile_fields_with_a_changed_value_does_invalidate_analysis():
    _reset()
    fields = dict(
        monthly_income=5000.0, current_savings=1000.0, debts=[], goals=[],
        constraints={"minimum_monthly_buffer": 0.0, "protected_categories": []}, assumptions=None,
    )
    app_state.set_profile_fields(**fields)
    app_state.set_analysis_result(("p", "s", "t", "f", "r"), {"marker": "graph_ran"})

    app_state.set_profile_fields(**{**fields, "monthly_income": 5500.0})
    assert app_state.get_graph_result() is None
    assert not app_state.is_profile_confirmed()


def test_set_categorized_df_with_an_equivalent_frame_does_not_invalidate_analysis():
    _reset()
    df = pd.DataFrame({"date": pd.to_datetime(["2026-01-01"]), "description": ["x"], "amount": [-5.0]})
    app_state.set_categorized_df(df)
    app_state.set_analysis_result(("p", "s", "t", "f", "r"), {"marker": "graph_ran"})

    # app.py rebuilds working_df fresh every rerun - a new object, same content
    app_state.set_categorized_df(df.copy())
    assert app_state.get_graph_result() == {"marker": "graph_ran"}


def test_set_categorized_df_with_a_changed_frame_does_invalidate_analysis():
    _reset()
    df = pd.DataFrame({"date": pd.to_datetime(["2026-01-01"]), "description": ["x"], "amount": [-5.0]})
    app_state.set_categorized_df(df)
    app_state.set_analysis_result(("p", "s", "t", "f", "r"), {"marker": "graph_ran"})

    changed = df.copy()
    changed.loc[0, "amount"] = -6.0
    app_state.set_categorized_df(changed)
    assert app_state.get_graph_result() is None


def test_set_raw_transactions_always_invalidates_and_resets_categorized_df():
    _reset()
    app_state.set_categorized_df(pd.DataFrame({"a": [1]}))
    app_state.set_analysis_result(("p", "s", "t", "f", "r"), {"marker": "graph_ran"})

    app_state.set_raw_transactions(pd.DataFrame({"date": pd.to_datetime(["2026-01-01"]), "description": ["x"], "amount": [-5.0]}))
    assert app_state.get_categorized_df() is None
    assert app_state.get_graph_result() is None


def test_build_session_context_matches_the_documented_shape():
    profile = {
        "transactions": [{"description": "x"}], "monthly_income": 5000.0, "current_savings": 1000.0,
        "debts": [{"name": "Card"}], "goals": [{"name": "Trip"}],
    }
    snapshot = {"metrics": {"gross_surplus": 900.0, "allocatable_surplus": 700.0}}
    roadmap = {"allocation": {
        "debt_extra_payment": 100.0, "savings_contribution": 400.0, "goal_contributions": {"Trip": 200.0},
    }}
    context = app_state.build_session_context(profile, snapshot, roadmap)
    assert context == {
        "transactions": profile["transactions"],
        "monthly_income": 5000.0, "current_savings": 1000.0,
        "debts": profile["debts"], "goals": profile["goals"],
        "monthly_surplus": 900.0, "allocatable_surplus": 700.0,
        "extra_debt_payment": 100.0, "savings_contribution": 400.0, "goal_contributions": {"Trip": 200.0},
    }
