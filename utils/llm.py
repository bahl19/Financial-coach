"""LLM client wrapper with graceful offline fallback.

Talks to OpenRouter (an OpenAI-compatible API that can route to Claude,
GPT, Llama, etc.) via the `openai` SDK pointed at OpenRouter's base URL.
If no API key is configured (or the call fails), complete() returns None
and callers fall back to their own rule-based logic -- this keeps the app
fully demoable without a key.
"""
import os
from typing import Optional

_client = None
_MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")
_BASE_URL = "https://openrouter.ai/api/v1"


def _get_client():
    global _client
    if _client is not None:
        return _client
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        _client = OpenAI(base_url=_BASE_URL, api_key=api_key)
    except Exception:
        _client = None
    return _client


def is_live() -> bool:
    return _get_client() is not None


def complete(system: str, user: str, max_tokens: int = 1024) -> Optional[str]:
    """Return the model's reply, or None if no API key is configured / the call fails."""
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=_MODEL,
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
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return None
