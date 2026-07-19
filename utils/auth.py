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
    """Renders a sign-in gate matching `UI/uploads/financial-coach-login.html`'s
    two-column brand layout (hero copy + feature checkmarks on the left,
    a card with the sign-in action on the right), rebuilt in Streamlit's
    own layout primitives rather than the static HTML file directly -
    `utils/theme.py`'s injected CSS is what actually makes it look the
    same (fonts, colors, card borders), not a copy-paste of that markup.
    Callers are responsible for calling `st.stop()` immediately after this
    when `not is_logged_in()`, so no gated content executes for an
    unauthenticated visitor - Streamlit has no routing/middleware layer to
    do this centrally."""
    st.markdown(
        "<span style='display:inline-flex;align-items:center;gap:8px;font-size:11px;"
        "letter-spacing:.24em;text-transform:uppercase;color:var(--fc-mint);"
        "border:1px solid var(--fc-mint-line);background:var(--fc-mint-dim);"
        "padding:7px 16px;border-radius:999px;margin-bottom:18px'>"
        "✨ AI-powered financial analysis</span>",
        unsafe_allow_html=True,
    )
    left, right = st.columns([1.15, 1], gap="large")
    with left:
        st.markdown(
            "<h1 style='font-size:clamp(32px,4vw,50px);line-height:1.05;margin:0 0 18px'>"
            "Stop the manual struggle.<br><span style='color:var(--fc-mint)'>Start coaching.</span></h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='color:var(--fc-muted);font-size:16px;font-weight:300;line-height:1.6;max-width:44ch'>"
            "Upload your statements and let your AI coach turn raw transactions into "
            "<strong style='color:var(--fc-ink);font-weight:500'>actionable insights in seconds</strong> "
            "&mdash; no spreadsheets, no formulas, no late nights.</p>",
            unsafe_allow_html=True,
        )
        for line in ("Personalized insights", "Trends spotted instantly", "A plan for your money, not just a summary"):
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:8px;color:var(--fc-muted);"
                f"font-size:14px;margin-bottom:8px'><span style='color:var(--fc-mint)'>✓</span>{line}</div>",
                unsafe_allow_html=True,
            )
    with right:
        with st.container(border=True):
            st.subheader("Welcome back")
            st.caption("Sign in to open your dashboard.")
            if st.button("Sign in", type="primary", key="auth_sign_in_button", width="stretch"):
                st.login()
            st.caption("New here? Signing in creates your account automatically — no separate sign-up.")


def render_signed_in_sidebar_control() -> None:
    if not is_logged_in():
        return
    with st.sidebar:
        st.caption(f"Signed in as {current_user_label()}")
        if st.button("Sign out", key="auth_sign_out_button"):
            # Send them back to the landing page, so a signed-out visitor
            # sees what a first-time visitor sees rather than being dropped
            # straight onto the sign-in gate with no context. Imported here,
            # not at module scope, to keep the auth <-> landing dependency
            # one-directional and avoid a circular import.
            from utils import landing

            landing.reset()
            st.logout()
