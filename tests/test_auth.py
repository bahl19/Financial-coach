"""Tests for utils/auth.py (Logto-backed sign-in via st.login()).

`st.login()`/`st.user`'s real OIDC redirect round-trip is a live,
browser-based flow against Logto's hosted sign-in page - it cannot be
driven headlessly, the same documented limitation category as
`AppTest`'s lack of a `st.data_editor` query interface (Implementation
Plan - MVP 1.md, Phase 11's tooling note). What *is* tested here, without
a network call or browser:

- The gating logic itself (`auth_enabled()`, `is_logged_in()`,
  `current_user_label()`) against monkeypatched `st.secrets`/`st.user`,
  proving it degrades to "disabled" on every kind of missing
  configuration rather than raising.
- Via `tests/test_app.py`'s `AppTest`-based tests, that the login screen
  actually renders and blocks the rest of the app when auth is enabled
  and the user is not signed in, and that the existing full app flow is
  completely unaffected when auth is not configured (this repository's
  default, matching CI).
"""

from __future__ import annotations

import streamlit as st

from utils import auth as authn


class _FakeSecretsMissing:
    def __contains__(self, key):
        raise Exception("No secrets found")  # mirrors StreamlitSecretNotFoundError's shape, not its exact type


class _FakeSecretsPresentButNoAuth(dict):
    pass


class _FakeUser:
    def __init__(self, is_logged_in: bool, claims: dict | None = None):
        self.is_logged_in = is_logged_in
        self._claims = claims or {}

    def get(self, key, default=None):
        return self._claims.get(key, default)


def test_auth_disabled_when_no_secrets_file_exists(monkeypatch):
    monkeypatch.setattr(st, "secrets", _FakeSecretsMissing())
    assert authn.auth_enabled() is False


def test_auth_disabled_when_secrets_file_exists_but_has_no_auth_section(monkeypatch):
    monkeypatch.setattr(st, "secrets", _FakeSecretsPresentButNoAuth({"some_other_section": {}}))
    assert authn.auth_enabled() is False


def test_auth_enabled_when_auth_section_present(monkeypatch):
    monkeypatch.setattr(st, "secrets", {"auth": {"client_id": "x"}})
    assert authn.auth_enabled() is True


def test_is_logged_in_false_when_auth_disabled_regardless_of_user_state(monkeypatch):
    monkeypatch.setattr(st, "secrets", _FakeSecretsMissing())
    monkeypatch.setattr(st, "user", _FakeUser(is_logged_in=True))
    assert authn.is_logged_in() is False


def test_is_logged_in_reflects_st_user_when_auth_enabled(monkeypatch):
    monkeypatch.setattr(st, "secrets", {"auth": {"client_id": "x"}})
    monkeypatch.setattr(st, "user", _FakeUser(is_logged_in=True))
    assert authn.is_logged_in() is True

    monkeypatch.setattr(st, "user", _FakeUser(is_logged_in=False))
    assert authn.is_logged_in() is False


def test_current_user_label_prefers_email_then_name_then_fallback(monkeypatch):
    monkeypatch.setattr(st, "secrets", {"auth": {"client_id": "x"}})

    monkeypatch.setattr(st, "user", _FakeUser(is_logged_in=True, claims={"email": "a@b.com", "name": "A"}))
    assert authn.current_user_label() == "a@b.com"

    monkeypatch.setattr(st, "user", _FakeUser(is_logged_in=True, claims={"name": "A"}))
    assert authn.current_user_label() == "A"

    monkeypatch.setattr(st, "user", _FakeUser(is_logged_in=True, claims={}))
    assert authn.current_user_label() == "signed in"


def test_current_user_label_none_when_not_logged_in(monkeypatch):
    monkeypatch.setattr(st, "secrets", {"auth": {"client_id": "x"}})
    monkeypatch.setattr(st, "user", _FakeUser(is_logged_in=False))
    assert authn.current_user_label() is None
