"""Tests for utils/ai_helper.py's Gemini-only path."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import requests

from utils import ai_helper


class _FakeHTTPError(requests.exceptions.HTTPError):
    def __init__(self, status: int, headers: dict | None = None):
        resp = type("R", (), {"status_code": status, "headers": headers or {}})()
        super().__init__(response=resp)
        self.response = resp


@pytest.fixture(autouse=True)
def _isolated_cache(monkeypatch, tmp_path):
    """Per-test AI cache + provider-stats path, plus skip sleeps."""
    monkeypatch.setenv("AI_CACHE_PATH", str(tmp_path / "c.jsonl"))
    monkeypatch.setenv("AI_CACHE_ENABLED", "1")
    import importlib

    from utils import ai_cache as _ac

    importlib.reload(_ac)
    _ac.reset_cache_for_tests()
    monkeypatch.setattr(ai_helper, "ai_cache", _ac)
    from utils import provider_stats as _ps

    monkeypatch.setattr(_ps, "STATS_LOG", tmp_path / "provider_stats.jsonl")
    monkeypatch.setattr(ai_helper, "sleep", lambda *_, **__: None)
    monkeypatch.setattr(ai_helper.time, "sleep", lambda *_, **__: None)


def test_ai_text_returns_empty_when_no_gemini_key_configured(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert ai_helper.ai_text("prompt") == ""


def test_ai_text_returns_gemini_response_on_success(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    with patch.object(ai_helper, "_call_gemini", lambda *a, **k: "gemini response"):
        assert ai_helper.ai_text("prompt") == "gemini response"


def test_ai_text_retries_once_on_429_then_succeeds(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    attempts = {"n": 0}

    def _gemini_429_then_ok(*a, **k):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise _FakeHTTPError(429, headers={"Retry-After": "1"})
        return "gemini response after retry"

    with patch.object(ai_helper, "_call_gemini", side_effect=_gemini_429_then_ok):
        assert ai_helper.ai_text("prompt") == "gemini response after retry"
    assert attempts["n"] == 2


def test_gemini_circuit_opens_after_threshold_consecutive_429s(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    with patch.object(ai_helper, "_call_gemini", side_effect=_FakeHTTPError(429)):
        for i in range(ai_helper._GEMINI_429_CIRCUIT_THRESHOLD):
            assert ai_helper.ai_text(f"prompt {i}") == ""
    assert ai_helper._gemini_circuit_open is True


def test_circuit_open_skips_gemini_entirely(monkeypatch):
    """Once open, ai_text must NOT call _call_gemini at all."""
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    ai_helper._gemini_circuit_open = True
    with patch.object(ai_helper, "_call_gemini") as gemini:
        out = ai_helper.ai_text("anything")
    assert out == ""
    gemini.assert_not_called()


def test_successful_gemini_call_resets_streak(monkeypatch):
    """Streak must reset on a healthy 200 — a single transient 429 then
    success shouldn't accumulate toward opening the breaker."""
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    ai_helper._gemini_429_streak = 2
    with patch.object(ai_helper, "_call_gemini", return_value="ok"):
        assert ai_helper.ai_text("x") == "ok"
    assert ai_helper._gemini_429_streak == 0
    assert ai_helper._gemini_circuit_open is False


def test_threshold_is_configurable(monkeypatch):
    monkeypatch.setattr(ai_helper, "_GEMINI_429_CIRCUIT_THRESHOLD", 2)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    with patch.object(ai_helper, "_call_gemini", side_effect=_FakeHTTPError(429)):
        for i in range(2):
            ai_helper.ai_text(f"prompt {i}")
    assert ai_helper._gemini_circuit_open is True


def test_5xx_failures_open_breaker(monkeypatch):
    """5xx errors should also open the breaker to protect the run
    from long timeout/retry cycles when the provider is down."""
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    with patch.object(ai_helper, "_call_gemini", side_effect=_FakeHTTPError(503)):
        for _ in range(ai_helper._GEMINI_429_CIRCUIT_THRESHOLD):
            ai_helper.ai_text(f"prompt {_}")
    assert ai_helper._gemini_circuit_open is True


def test_timeouts_open_breaker(monkeypatch):
    """Timeouts should also open the breaker."""
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    with patch.object(ai_helper, "_call_gemini", side_effect=requests.exceptions.Timeout("Timeout info")):
        for _ in range(ai_helper._GEMINI_429_CIRCUIT_THRESHOLD):
            ai_helper.ai_text(f"prompt {_}")
    assert ai_helper._gemini_circuit_open is True


def test_400_status_returns_empty_without_retry(monkeypatch):
    """Non-transient failures (400, 401) shouldn't retry or burn quota."""
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    with patch.object(ai_helper, "_call_gemini", side_effect=_FakeHTTPError(400)) as gemini:
        out = ai_helper.ai_text("x")
    assert out == ""
    assert gemini.call_count == 1


def test_cache_hit_skips_provider(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_CACHE_PATH", str(tmp_path / "c.jsonl"))
    monkeypatch.setenv("AI_CACHE_ENABLED", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    import importlib

    from utils import ai_cache as _ac

    importlib.reload(_ac)
    _ac.reset_cache_for_tests()

    with patch.object(ai_helper, "_call_gemini", return_value="fresh-out") as gemini:
        first = ai_helper.ai_text("hello prompt")
    assert first == "fresh-out"
    gemini.assert_called_once()

    with patch.object(ai_helper, "_call_gemini") as gemini2:
        second = ai_helper.ai_text("hello prompt")
    assert second == "fresh-out"
    gemini2.assert_not_called()


def test_cache_stores_failed_result(monkeypatch, tmp_path):
    """A successful Gemini-served answer should be hot-served from cache on the next call."""
    monkeypatch.setenv("AI_CACHE_PATH", str(tmp_path / "c.jsonl"))
    monkeypatch.setenv("AI_CACHE_ENABLED", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    import importlib

    from utils import ai_cache as _ac

    importlib.reload(_ac)
    _ac.reset_cache_for_tests()

    with patch.object(ai_helper, "_call_gemini", return_value="from-gemini"):
        out1 = ai_helper.ai_text("identical prompt")
    assert out1 == "from-gemini"

    with patch.object(ai_helper, "_call_gemini") as gemini:
        out2 = ai_helper.ai_text("identical prompt")
    assert out2 == "from-gemini"
    gemini.assert_not_called()


def test_reset_helper_clears_state():
    ai_helper._gemini_429_streak = 5
    ai_helper._gemini_circuit_open = True
    ai_helper._reset_gemini_circuit_breaker()
    assert ai_helper._gemini_429_streak == 0
    assert ai_helper._gemini_circuit_open is False
