"""Session-state accessor (Implementation Plan - MVP 1.md, Phase 8).

`app.py` is the only writer to `st.session_state` (Phase 8's standing
constraint) - domain components (`agents.graph`, `utils.*`) stay pure and
return values rather than mutating shared state. This module is the one
place that reads and writes session state, rather than scattering direct
key access across `app.py` - Streamlit reruns the whole script on every
interaction, and scattered mutable-state access is where rerun bugs breed.

Every setter that changes an upstream input (transactions, income, debts,
goals, assumptions) also invalidates the last analysis run, so a stale
`graph_result` is never displayed against inputs it was not computed from.
"""

from __future__ import annotations

import streamlit as st

# Factories, not literal defaults - a bare `[]`/`{}` in a dict literal is one
# shared object; assigning it into session state would let one session's
# in-place mutation leak into another session's "default" on the next
# `not in st.session_state` check within the same process.
_DEFAULTS = {
    "raw_transactions": lambda: None,
    "categorized_df": lambda: None,
    "monthly_income": lambda: None,
    "confirmed_monthly_expenses": lambda: None,
    "current_savings": lambda: None,
    "current_investments": lambda: None,
    "debts": list,
    "goals": list,
    "constraints": lambda: {"minimum_monthly_buffer": 0.0, "protected_categories": []},
    "assumptions": lambda: None,
    "profile_confirmed": lambda: False,
    "graph_result": lambda: None,
    "pipeline_inputs": lambda: None,  # (profile, snapshot, trends, findings, risks) behind graph_result
    "scenario_preview": lambda: None,
    "chat_history": list,
}


def init_state() -> None:
    for key, factory in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = factory()


def _invalidate_analysis() -> None:
    st.session_state["graph_result"] = None
    st.session_state["pipeline_inputs"] = None
    st.session_state["scenario_preview"] = None
    st.session_state["profile_confirmed"] = False


# --------------------------------------------------------------------------
# Step 1: raw transactions
# --------------------------------------------------------------------------

def get_raw_transactions():
    return st.session_state["raw_transactions"]


def set_raw_transactions(df) -> None:
    st.session_state["raw_transactions"] = df
    st.session_state["categorized_df"] = None
    _invalidate_analysis()


# --------------------------------------------------------------------------
# Step 2: categorized transactions (post category-review corrections)
# --------------------------------------------------------------------------

def get_categorized_df():
    return st.session_state["categorized_df"]


def set_categorized_df(df) -> None:
    """`app.py` recomputes `working_df` fresh from `raw_transactions` on
    every rerun and calls this unconditionally, so - as with
    `set_profile_fields()` - invalidation must be conditioned on an actual
    content change, not merely a new DataFrame object, or any unrelated
    rerun would silently wipe a just-computed `graph_result`."""
    previous = st.session_state["categorized_df"]
    changed = previous is None or not previous.equals(df)
    st.session_state["categorized_df"] = df
    if changed:
        _invalidate_analysis()


# --------------------------------------------------------------------------
# Step 3: profile fields (income, savings, debts, goals, constraints,
# assumptions) and the confirmation gate itself
# --------------------------------------------------------------------------

def get_profile_fields() -> dict:
    return {
        "monthly_income": st.session_state["monthly_income"],
        "confirmed_monthly_expenses": st.session_state["confirmed_monthly_expenses"],
        "current_savings": st.session_state["current_savings"],
        "current_investments": st.session_state["current_investments"],
        "debts": st.session_state["debts"],
        "goals": st.session_state["goals"],
        "constraints": st.session_state["constraints"],
        "assumptions": st.session_state["assumptions"],
    }


def set_profile_fields(
    monthly_income, current_savings, debts, goals, constraints, assumptions,
    confirmed_monthly_expenses=None, current_investments=None,
) -> None:
    """`app.py` calls this on every rerun (Streamlit reruns the whole script
    on any widget interaction, not just when a profile field's widget itself
    changed) - invalidating analysis unconditionally here would wipe out a
    just-computed `graph_result` on the very next unrelated rerun (e.g.
    sending a chat message). Only invalidate when a value genuinely changed
    from what is already stored."""
    changed = get_profile_fields() != {
        "monthly_income": monthly_income, "confirmed_monthly_expenses": confirmed_monthly_expenses,
        "current_savings": current_savings, "current_investments": current_investments,
        "debts": debts, "goals": goals, "constraints": constraints, "assumptions": assumptions,
    }
    st.session_state["monthly_income"] = monthly_income
    st.session_state["confirmed_monthly_expenses"] = confirmed_monthly_expenses
    st.session_state["current_savings"] = current_savings
    st.session_state["current_investments"] = current_investments
    st.session_state["debts"] = debts
    st.session_state["goals"] = goals
    st.session_state["constraints"] = constraints
    st.session_state["assumptions"] = assumptions
    if changed:
        _invalidate_analysis()


def is_profile_confirmed() -> bool:
    return bool(st.session_state["profile_confirmed"])


def confirm_profile() -> None:
    st.session_state["profile_confirmed"] = True


# --------------------------------------------------------------------------
# Step 4: analysis (the one LangGraph invocation the whole app reads from)
# --------------------------------------------------------------------------

def get_graph_result():
    return st.session_state["graph_result"]


def get_pipeline_inputs():
    return st.session_state["pipeline_inputs"]


def set_analysis_result(pipeline_inputs, graph_result) -> None:
    st.session_state["pipeline_inputs"] = pipeline_inputs
    st.session_state["graph_result"] = graph_result


# --------------------------------------------------------------------------
# Step 5: scenario preview (never commits until the user says so)
# --------------------------------------------------------------------------

def get_scenario_preview():
    return st.session_state["scenario_preview"]


def set_scenario_preview(preview) -> None:
    st.session_state["scenario_preview"] = preview


def clear_scenario_preview() -> None:
    st.session_state["scenario_preview"] = None


# --------------------------------------------------------------------------
# Chat
# --------------------------------------------------------------------------

def get_chat_history() -> list:
    return st.session_state["chat_history"]


def append_chat(role: str, message: str) -> None:
    st.session_state["chat_history"] = st.session_state["chat_history"] + [(role, message)]


# --------------------------------------------------------------------------
# Session-state adaptor (Implementation Plan - MVP 1.md, Phase 8 task list):
# the flattened display/download context built from confirmed profile +
# snapshot + roadmap - distinct from `pipeline_inputs`/`graph_result` above,
# which carry the full contracts the graph nodes actually consume.
# --------------------------------------------------------------------------

def build_session_context(profile: dict, snapshot: dict, roadmap: dict) -> dict:
    allocation = roadmap["allocation"]
    metrics = snapshot["metrics"]
    return {
        "transactions": profile.get("transactions") or [],
        "monthly_income": profile.get("monthly_income"),
        "current_savings": profile.get("current_savings"),
        "debts": profile.get("debts") or [],
        "goals": profile.get("goals") or [],
        "monthly_surplus": metrics.get("gross_surplus"),
        "allocatable_surplus": metrics.get("allocatable_surplus"),
        "extra_debt_payment": allocation["debt_extra_payment"],
        "savings_contribution": allocation["savings_contribution"],
        "goal_contributions": allocation["goal_contributions"],
    }
