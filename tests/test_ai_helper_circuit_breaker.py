"""Tests for the in-run Mistral 429 circuit breaker in utils.ai_helper.

The queue-refresh workflow timed out at 25min on 2026-05-19 because
Mistral 429'd 36 times in a row and each give-up cost ~30s of
retry-and-wait before falling back to Cerebras. The circuit breaker
pulls Mistral out of the chain for the rest of the run after a
configurable number of consecutive 429s, so subsequent stories go
straight to the fallback chain.
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


def test_reset_helper_clears_state():
    ai_helper._mistral_429_streak = 5
    ai_helper._mistral_circuit_open = True
    ai_helper._reset_mistral_circuit_breaker()
    assert ai_helper._mistral_429_streak == 0
    assert ai_helper._mistral_circuit_open is False


def test_circuit_opens_after_threshold_consecutive_429s(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    # Default threshold is 3. After 3 give-ups (= 3 separate ai_text
    # calls where Mistral 429s both attempts), the breaker should open.
    with patch.object(ai_helper, "_call_mistral", side_effect=_FakeHTTPError(429)):
        for _ in range(3):
            ai_helper.ai_text(f"unique prompt {_}")
    assert ai_helper._mistral_circuit_open is True
    assert ai_helper._mistral_429_streak >= 3


def test_circuit_open_skips_mistral_entirely(monkeypatch):
    """Once open, ai_text must NOT call _call_mistral at all."""
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    monkeypatch.setenv("CEREBRAS_API_KEY", "c")
    ai_helper._mistral_circuit_open = True

    with (
        patch.object(ai_helper, "_call_mistral") as mistral,
        patch.object(ai_helper, "_call_cerebras", return_value="from-cerebras"),
    ):
        out = ai_helper.ai_text("anything")
    assert out == "from-cerebras"
    mistral.assert_not_called()


def test_successful_mistral_call_resets_streak(monkeypatch):
    """Streak must reset on a healthy 200 — a single transient 429 then
    success shouldn't accumulate toward opening the breaker."""
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    ai_helper._mistral_429_streak = 2  # one shy of threshold
    with patch.object(ai_helper, "_call_mistral", return_value="ok"):
        out = ai_helper.ai_text("x")
    assert out == "ok"
    assert ai_helper._mistral_429_streak == 0
    assert ai_helper._mistral_circuit_open is False


def test_threshold_is_configurable(monkeypatch):
    monkeypatch.setattr(ai_helper, "_MISTRAL_429_CIRCUIT_THRESHOLD", 2)
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    with patch.object(ai_helper, "_call_mistral", side_effect=_FakeHTTPError(429)):
        for i in range(2):
            ai_helper.ai_text(f"prompt {i}")
    assert ai_helper._mistral_circuit_open is True


def test_5xx_failures_do_not_open_breaker(monkeypatch):
    """The breaker is for 429 specifically — 5xx errors are usually
    transient and shouldn't disable Mistral for the rest of the run.
    The fallback chain still kicks in per-call."""
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    with patch.object(ai_helper, "_call_mistral", side_effect=_FakeHTTPError(503)):
        for _ in range(5):
            ai_helper.ai_text(f"prompt {_}")
    assert ai_helper._mistral_circuit_open is False
    assert ai_helper._mistral_429_streak == 0


def test_circuit_open_with_no_fallback_keys_returns_empty(monkeypatch):
    """Sanity: when the breaker is open and no fallback provider is
    configured, ai_text returns an empty string (same contract as the
    no-key case)."""
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    ai_helper._mistral_circuit_open = True
    with patch.object(ai_helper, "_call_mistral") as mistral:
        out = ai_helper.ai_text("x")
    assert out == ""
    mistral.assert_not_called()
