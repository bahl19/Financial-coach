"""LLM client wrapper with graceful offline fallback.

Talks to OpenRouter (an OpenAI-compatible API that can route to Claude,
GPT, Llama, etc.) via the `openai` SDK pointed at OpenRouter's base URL.
If no API key is configured (or the call fails), complete() returns None
and callers fall back to their own rule-based logic -- this keeps the app
fully demoable without a key.

**Failures are recorded, not swallowed.** An earlier version returned None
from a bare `except Exception` with no logging, which meant a configured but
non-working key (no credits, model not enabled on the account, rate limit,
typo) was indistinguishable from having no key at all: the app quietly served
templated narratives and there was nothing anywhere to explain why. Every
failure now logs its reason and is retrievable via `last_error()` so the UI
can say what went wrong. The *behaviour* is unchanged - callers still get
None and still fall back - only the silence is gone.

The API key and model are read lazily rather than at import time. Streamlit
promotes top-level secrets into `os.environ` only when `st.secrets` is first
accessed, which happens *after* this module is imported; reading at import
time would miss anything set through Streamlit secrets.
"""
import logging
import os
from typing import Optional

_LOGGER = logging.getLogger(__name__)

_client = None
_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"

# Reason the most recent call could not produce a model response, or None
# when the last call succeeded / none has been made. Never contains the key.
_last_error: Optional[str] = None


def model_name() -> str:
    """Read lazily: `OPENROUTER_MODEL` may arrive via Streamlit secrets, which
    are promoted to `os.environ` only after this module is imported."""
    return os.environ.get("OPENROUTER_MODEL") or _DEFAULT_MODEL


def last_error() -> Optional[str]:
    """Why the last attempt fell back to rule-based output, if it did."""
    return _last_error


def _get_client():
    global _client, _last_error
    if _client is not None:
        return _client
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        _last_error = (
            "No OPENROUTER_API_KEY found. Set it in .env locally, or as a "
            "TOP-LEVEL key in Streamlit secrets - a key nested under a "
            "[section] is never promoted to the environment."
        )
        return None
    try:
        from openai import OpenAI

        _client = OpenAI(base_url=_BASE_URL, api_key=api_key)
        _last_error = None
    except Exception as exc:
        _client = None
        _last_error = f"Could not create the OpenRouter client: {type(exc).__name__}: {exc}"
        _LOGGER.warning("OpenRouter client init failed: %s", _last_error)
    return _client


def is_live() -> bool:
    return _get_client() is not None


def complete(system: str, user: str, max_tokens: int = 1024) -> Optional[str]:
    """Return the model's reply, or None if no API key is configured / the
    call fails. On failure the reason is logged and stored in
    `last_error()` - callers still fall back to rule-based output."""
    global _last_error
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=model_name(),
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            extra_headers={
                "HTTP-Referer": "https://github.com/ai-financial-coach",
                "X-Title": "AI Financial Coach Agent",
            },
        )
        _last_error = None
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        # Message only - never the key, and never the prompt, which carries
        # the user's financial figures.
        _last_error = f"{type(exc).__name__}: {exc}"
        _LOGGER.warning(
            "OpenRouter call failed for model %s, falling back to rule-based output: %s",
            model_name(), _last_error,
        )
        return None
