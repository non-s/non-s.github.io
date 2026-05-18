"""Tests for the multi-provider fallback chain in utils.ai_helper.ai_text.

We mock the three transport functions (_call_mistral, _call_cerebras,
_call_gemini, _call_groq) so the tests run offline.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest
import requests

from utils import ai_helper


class _FakeHTTPError(requests.exceptions.HTTPError):
    def __init__(self, status: int):
        resp = MagicMock()
        resp.status_code = status
        resp.headers = {}
        super().__init__(response=resp)
        self.response = resp


@pytest.fixture(autouse=True)
def _clear_keys(monkeypatch):
    """Strip provider keys so each test sets only the ones it needs."""
    for var in ("MISTRAL_API_KEY", "CEREBRAS_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def fast_sleep(monkeypatch):
    """Skip the throttle + backoff sleeps."""
    monkeypatch.setattr(ai_helper, "sleep", lambda *_, **__: None)
    monkeypatch.setattr(ai_helper.time, "sleep", lambda *_, **__: None)


def test_mistral_success_short_circuits(monkeypatch, fast_sleep):
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    monkeypatch.setenv("CEREBRAS_API_KEY", "c")
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    with patch.object(ai_helper, "_call_mistral", return_value="ok-mistral") as m, \
         patch.object(ai_helper, "_call_cerebras") as ce, \
         patch.object(ai_helper, "_call_gemini") as ge, \
         patch.object(ai_helper, "_call_groq") as gr:
        out = ai_helper.ai_text("anything")
    assert out == "ok-mistral"
    m.assert_called_once()
    ce.assert_not_called()
    ge.assert_not_called()
    gr.assert_not_called()


def test_falls_back_to_cerebras_on_mistral_429(monkeypatch, fast_sleep):
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    monkeypatch.setenv("CEREBRAS_API_KEY", "c")
    with patch.object(ai_helper, "_call_mistral", side_effect=_FakeHTTPError(429)), \
         patch.object(ai_helper, "_call_cerebras", return_value="ok-cerebras") as ce:
        out = ai_helper.ai_text("x")
    assert out == "ok-cerebras"
    ce.assert_called_once()


def test_falls_through_to_gemini_when_cerebras_also_429(monkeypatch, fast_sleep):
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    monkeypatch.setenv("CEREBRAS_API_KEY", "c")
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    with patch.object(ai_helper, "_call_mistral", side_effect=_FakeHTTPError(429)), \
         patch.object(ai_helper, "_call_cerebras", side_effect=_FakeHTTPError(429)), \
         patch.object(ai_helper, "_call_gemini", return_value="ok-gemini") as ge:
        out = ai_helper.ai_text("x")
    assert out == "ok-gemini"
    ge.assert_called()


def test_falls_through_to_groq_when_everything_else_fails(monkeypatch, fast_sleep):
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    monkeypatch.setenv("CEREBRAS_API_KEY", "c")
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("GROQ_API_KEY", "gr")
    with patch.object(ai_helper, "_call_mistral", side_effect=_FakeHTTPError(503)), \
         patch.object(ai_helper, "_call_cerebras", side_effect=_FakeHTTPError(429)), \
         patch.object(ai_helper, "_call_gemini", side_effect=_FakeHTTPError(500)), \
         patch.object(ai_helper, "_call_groq", return_value="ok-groq") as gr:
        out = ai_helper.ai_text("x")
    assert out == "ok-groq"
    gr.assert_called()


def test_no_fallback_keys_returns_empty(monkeypatch, fast_sleep):
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    with patch.object(ai_helper, "_call_mistral", side_effect=_FakeHTTPError(429)):
        out = ai_helper.ai_text("x")
    assert out == ""


def test_400_status_skips_fallbacks(monkeypatch, fast_sleep):
    """Non-transient failures (400, 401) shouldn't burn fallback quota."""
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    monkeypatch.setenv("CEREBRAS_API_KEY", "c")
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("GROQ_API_KEY", "gr")
    with patch.object(ai_helper, "_call_mistral", side_effect=_FakeHTTPError(400)), \
         patch.object(ai_helper, "_call_cerebras") as ce, \
         patch.object(ai_helper, "_call_gemini") as ge, \
         patch.object(ai_helper, "_call_groq") as gr:
        out = ai_helper.ai_text("x")
    assert out == ""
    ce.assert_not_called()
    ge.assert_not_called()
    gr.assert_not_called()


def test_no_mistral_key_short_circuits(monkeypatch, fast_sleep):
    # Without MISTRAL_API_KEY we don't even reach the fallback chain —
    # the chain triggers only on a transient Mistral failure.
    monkeypatch.setenv("CEREBRAS_API_KEY", "c")
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    with patch.object(ai_helper, "_call_mistral") as m, \
         patch.object(ai_helper, "_call_cerebras") as ce, \
         patch.object(ai_helper, "_call_gemini") as ge:
        out = ai_helper.ai_text("x")
    assert out == ""
    m.assert_not_called()
    ce.assert_not_called()
    ge.assert_not_called()


def test_skips_provider_without_key(monkeypatch, fast_sleep):
    """If Gemini is configured but Cerebras is not, the chain should skip Cerebras."""
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    with patch.object(ai_helper, "_call_mistral", side_effect=_FakeHTTPError(429)), \
         patch.object(ai_helper, "_call_cerebras") as ce, \
         patch.object(ai_helper, "_call_gemini", return_value="ok-gemini") as ge:
        out = ai_helper.ai_text("x")
    assert out == "ok-gemini"
    ce.assert_not_called()
    ge.assert_called()
