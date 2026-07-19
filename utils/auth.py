"""Logto-backed sign-in via Streamlit's native OIDC support (`st.login()`).

Architecture decision (2026-07-19, recorded in `Implementation Plan - MVP 1.md`'s
Post-Release Maintenance Log and `Architecture Plan.md`): authentication was
originally deferred to `Architecture Plan - Later.md`'s L0 milestone. This
module is a deliberate, user-directed pivot that moves it earlier, using
Streamlit's native `st.login()`/`st.user`/`st.logout()` (stable since
Streamlit 1.42, backed by Authlib) against Logto as the OIDC provider,
rather than a hand-rolled session/cookie implementation.

Gating follows the exact pattern `utils.llm.is_live()` already established
for `OPENROUTER_API_KEY`: a missing configuration must never crash the app
or a test, only skip the feature it powers. `st.secrets` has no `[auth]`
section unless `.streamlit/secrets.toml` is present (gitignored; see
`.streamlit/secrets.toml.example`) - CI and every `AppTest`-based test in
this repository run without that file, so authentication is transparently
disabled there, exactly like offline mode is for the LLM.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st


def auth_enabled() -> bool:
    """True only when a real `[auth]` section is configured. `st.secrets`
    raises if no secrets file exists at all, not just returns empty - both
    "no file" and "file present but no [auth] section" must resolve to
    disabled, not an exception."""
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def is_logged_in() -> bool:
    if not auth_enabled():
        return False
    return bool(st.user.is_logged_in)


def current_user_label() -> Optional[str]:
    """A short, display-safe label for the signed-in user - never the full
    ID token claims (which may carry more than this app needs to show)."""
    if not is_logged_in():
        return None
    return st.user.get("email") or st.user.get("name") or "signed in"


def render_login_screen() -> None:
    """Renders a minimal sign-in gate. Callers are responsible for calling
    `st.stop()` immediately after this when `not is_logged_in()`, so no
    gated content executes for an unauthenticated visitor - Streamlit has
    no routing/middleware layer to do this centrally."""
    st.title("AI Financial Coach")
    st.write("Sign in to continue. Your financial data stays private to your signed-in session.")
    if st.button("Sign in", type="primary", key="auth_sign_in_button"):
        st.login()


def render_signed_in_sidebar_control() -> None:
    if not is_logged_in():
        return
    with st.sidebar:
        st.caption(f"Signed in as {current_user_label()}")
        if st.button("Sign out", key="auth_sign_out_button"):
            st.logout()
