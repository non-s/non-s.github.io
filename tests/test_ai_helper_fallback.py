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
def _clear_keys(monkeypatch, tmp_path):
    """Strip provider keys + isolate the AI disk cache + provider stats."""
    for var in ("MISTRAL_API_KEY", "CEREBRAS_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    # Each test gets its own cache file so a hit in one test never
    # bleeds into another. Reload `ai_cache` so the module-level
    # _DEFAULT_PATH constant picks up the env var.
    monkeypatch.setenv("AI_CACHE_PATH", str(tmp_path / "ai_cache.jsonl"))
    monkeypatch.setenv("AI_CACHE_ENABLED", "1")
    import importlib
    from utils import ai_cache as _ac
    importlib.reload(_ac)
    _ac.reset_cache_for_tests()
    monkeypatch.setattr(ai_helper, "ai_cache", _ac)
    # provider_stats.record() writes to `_data/provider_stats.jsonl`
    # by default. Tests must NEVER leak into the repo's _data dir.
    from utils import provider_stats as _ps
    monkeypatch.setattr(_ps, "STATS_LOG", tmp_path / "provider_stats.jsonl")


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


# ── Cache integration ────────────────────────────────────────────

def test_cache_hit_skips_every_provider(monkeypatch, fast_sleep, tmp_path):
    """A cached response means no API is contacted at all."""
    monkeypatch.setenv("AI_CACHE_PATH", str(tmp_path / "c.jsonl"))
    monkeypatch.setenv("AI_CACHE_ENABLED", "1")
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    monkeypatch.setenv("CEREBRAS_API_KEY", "c")

    import importlib
    from utils import ai_cache as _ac
    importlib.reload(_ac)
    _ac.reset_cache_for_tests()
    # Patch ai_helper's reference to the freshly-reloaded module.
    monkeypatch.setattr(ai_helper, "ai_cache", _ac)

    # First call hits Mistral, populates cache.
    with patch.object(ai_helper, "_call_mistral", return_value="fresh-out") as m1:
        first = ai_helper.ai_text("hello prompt")
    assert first == "fresh-out"
    m1.assert_called_once()

    # Second call: no provider should be invoked.
    with patch.object(ai_helper, "_call_mistral") as m2, \
         patch.object(ai_helper, "_call_cerebras") as ce, \
         patch.object(ai_helper, "_call_gemini") as ge, \
         patch.object(ai_helper, "_call_groq") as gr:
        second = ai_helper.ai_text("hello prompt")
    assert second == "fresh-out"
    m2.assert_not_called()
    ce.assert_not_called()
    ge.assert_not_called()
    gr.assert_not_called()


def test_fallback_result_is_cached_under_primary_key(monkeypatch, fast_sleep, tmp_path):
    """A Cerebras-served answer should be hot-served from cache on the next call."""
    monkeypatch.setenv("AI_CACHE_PATH", str(tmp_path / "c.jsonl"))
    monkeypatch.setenv("AI_CACHE_ENABLED", "1")
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    monkeypatch.setenv("CEREBRAS_API_KEY", "c")

    import importlib
    from utils import ai_cache as _ac
    importlib.reload(_ac)
    _ac.reset_cache_for_tests()
    monkeypatch.setattr(ai_helper, "ai_cache", _ac)

    with patch.object(ai_helper, "_call_mistral", side_effect=_FakeHTTPError(429)), \
         patch.object(ai_helper, "_call_cerebras", return_value="from-cerebras"):
        out1 = ai_helper.ai_text("identical prompt")
    assert out1 == "from-cerebras"

    # Second call: cache hit means we never reach Mistral or Cerebras.
    with patch.object(ai_helper, "_call_mistral") as m, \
         patch.object(ai_helper, "_call_cerebras") as ce:
        out2 = ai_helper.ai_text("identical prompt")
    assert out2 == "from-cerebras"
    m.assert_not_called()
    ce.assert_not_called()
