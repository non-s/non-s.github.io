"""Tests for utils/ai_helper.py's provider fallback chain and the Mistral
circuit breaker — the part of the module that previously had zero coverage.

These mock the private `_call_*` functions directly (not `requests`) so
each test controls exactly what each provider call does without touching
`_throttle()`'s real sleep or HTTP internals. `ai_helper.sleep` is
monkeypatched to a no-op so the in-loop 429 retry-after wait doesn't slow
the suite down.
"""

from __future__ import annotations

import requests

from utils import ai_helper


def _http_error(status: int, retry_after: str | None = None) -> requests.exceptions.HTTPError:
    response = requests.Response()
    response.status_code = status
    if retry_after is not None:
        response.headers["Retry-After"] = retry_after
    return requests.exceptions.HTTPError(f"status {status}", response=response)


def _no_cache(monkeypatch):
    """ai_cache isn't covered by the autouse state-file isolation fixture
    in conftest.py, so route get/put to no-ops to avoid touching disk and
    to stop a cached response from short-circuiting the call we're testing."""
    monkeypatch.setattr(ai_helper.ai_cache, "get", lambda *a, **k: None)
    monkeypatch.setattr(ai_helper.ai_cache, "put", lambda *a, **k: None)


def test_ai_text_returns_empty_when_no_provider_key_configured(monkeypatch):
    _no_cache(monkeypatch)
    for env_var in ("MISTRAL_API_KEY", "CEREBRAS_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)
    assert ai_helper.ai_text("prompt") == ""


def test_ai_text_returns_mistral_response_on_success(monkeypatch):
    _no_cache(monkeypatch)
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(ai_helper, "_call_mistral", lambda *a, **k: "mistral response")
    assert ai_helper.ai_text("prompt") == "mistral response"


def test_ai_text_falls_back_to_next_provider_on_non_retryable_failure(monkeypatch):
    """A 500 (non-429) failure breaks out of the per-provider retry loop
    after one attempt and moves to the next configured provider."""
    _no_cache(monkeypatch)
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    calls: list[str] = []

    def _mistral_fails(*a, **k):
        calls.append("mistral")
        raise _http_error(500)

    def _groq_succeeds(*a, **k):
        calls.append("groq")
        return "groq response"

    monkeypatch.setattr(ai_helper, "_call_mistral", _mistral_fails)
    monkeypatch.setattr(ai_helper, "_call_groq", _groq_succeeds)

    assert ai_helper.ai_text("prompt") == "groq response"
    assert calls == ["mistral", "groq"]


def test_ai_text_retries_once_on_429_then_succeeds(monkeypatch):
    _no_cache(monkeypatch)
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(ai_helper, "sleep", lambda *_: None)

    attempts = {"n": 0}

    def _mistral_429_then_ok(*a, **k):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise _http_error(429, retry_after="1")
        return "mistral response after retry"

    monkeypatch.setattr(ai_helper, "_call_mistral", _mistral_429_then_ok)

    assert ai_helper.ai_text("prompt") == "mistral response after retry"
    assert attempts["n"] == 2


def test_mistral_circuit_breaker_opens_after_threshold_failures(monkeypatch):
    """Three consecutive non-retryable Mistral failures (the default
    MISTRAL_429_CIRCUIT_THRESHOLD) should open the breaker; a follow-up
    call with only Mistral configured then returns "" immediately instead
    of calling the provider again."""
    _no_cache(monkeypatch)
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    call_count = {"n": 0}

    def _always_fails(*a, **k):
        call_count["n"] += 1
        raise _http_error(500)

    monkeypatch.setattr(ai_helper, "_call_mistral", _always_fails)

    for _ in range(ai_helper._MISTRAL_429_CIRCUIT_THRESHOLD):
        assert ai_helper.ai_text(f"prompt {_}") == ""

    assert ai_helper._mistral_circuit_open is True
    calls_before = call_count["n"]

    # Breaker open + Mistral is the only configured provider: ai_text
    # should skip straight past it without calling it again.
    assert ai_helper.ai_text("one more prompt") == ""
    assert call_count["n"] == calls_before


def test_mistral_circuit_breaker_resets_streak_on_success(monkeypatch):
    _no_cache(monkeypatch)
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    script = iter([_http_error(500), _http_error(500), "ok"])

    def _scripted(*a, **k):
        item = next(script)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(ai_helper, "_call_mistral", _scripted)

    assert ai_helper.ai_text("p1") == ""
    assert ai_helper.ai_text("p2") == ""
    assert ai_helper._mistral_429_streak == 2
    assert ai_helper.ai_text("p3") == "ok"
    assert ai_helper._mistral_429_streak == 0
    assert ai_helper._mistral_circuit_open is False
