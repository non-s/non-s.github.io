"""Tests for utils/ai_cache.py — pure disk + in-memory cache, no network."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.fixture
def fresh_cache(tmp_path, monkeypatch):
    """Reload the module each test so module-level state is isolated."""
    monkeypatch.setenv("AI_CACHE_PATH", str(tmp_path / "cache.jsonl"))
    monkeypatch.setenv("AI_CACHE_ENABLED", "1")
    monkeypatch.setenv("AI_CACHE_TTL_DAYS", "30")
    from utils import ai_cache

    importlib.reload(ai_cache)
    ai_cache.reset_cache_for_tests()
    yield ai_cache, Path(str(tmp_path / "cache.jsonl"))


def test_get_returns_none_on_empty_cache(fresh_cache):
    ai_cache, _ = fresh_cache
    assert ai_cache.get("any prompt") is None


def test_put_then_get_round_trip(fresh_cache):
    ai_cache, path = fresh_cache
    ai_cache.put("hello", "world")
    assert ai_cache.get("hello") == "world"
    assert path.exists()


def test_put_persists_across_reload(fresh_cache, monkeypatch, tmp_path):
    ai_cache, path = fresh_cache
    ai_cache.put("hello", "world")
    # Fresh reload simulating a new process.
    ai_cache.reset_cache_for_tests()
    assert ai_cache.get("hello") == "world"


def test_different_json_mode_is_different_key(fresh_cache):
    ai_cache, _ = fresh_cache
    ai_cache.put("same prompt", "plain", json_mode=False)
    ai_cache.put("same prompt", "as-json", json_mode=True)
    assert ai_cache.get("same prompt", json_mode=False) == "plain"
    assert ai_cache.get("same prompt", json_mode=True) == "as-json"


def test_different_model_hint_is_different_key(fresh_cache):
    ai_cache, _ = fresh_cache
    ai_cache.put("p", "v1", model_hint="mistral-small-latest")
    ai_cache.put("p", "v2", model_hint="mistral-medium-latest")
    assert ai_cache.get("p", model_hint="mistral-small-latest") == "v1"
    assert ai_cache.get("p", model_hint="mistral-medium-latest") == "v2"


def test_expired_entries_are_ignored(fresh_cache):
    ai_cache, path = fresh_cache
    # Write an expired entry directly to disk; the loader should skip it.
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    expired = {
        "k": ai_cache._key("p", "", False),
        "ts": 0,  # epoch — definitely past the TTL
        "v": "old value",
    }
    path.write_text(json.dumps(expired) + "\n", encoding="utf-8")
    ai_cache.reset_cache_for_tests()
    assert ai_cache.get("p") is None


def test_put_is_noop_for_empty_value(fresh_cache):
    ai_cache, _ = fresh_cache
    ai_cache.put("prompt", "")
    assert ai_cache.get("prompt") is None


def test_disabled_cache_does_not_persist(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_CACHE_PATH", str(tmp_path / "cache.jsonl"))
    monkeypatch.setenv("AI_CACHE_ENABLED", "0")
    from utils import ai_cache

    importlib.reload(ai_cache)
    ai_cache.reset_cache_for_tests()
    ai_cache.put("p", "v")
    assert ai_cache.get("p") is None


def test_cached_call_skips_caller_on_hit(fresh_cache):
    ai_cache, _ = fresh_cache
    calls = {"n": 0}

    def producer():
        calls["n"] += 1
        return "fresh"

    out1 = ai_cache.cached_call("prompt", producer)
    out2 = ai_cache.cached_call("prompt", producer)
    assert out1 == "fresh"
    assert out2 == "fresh"
    assert calls["n"] == 1  # second call hit the cache


def test_prune_rewrites_file_dropping_expired(fresh_cache):
    ai_cache, path = fresh_cache
    # Write 2 valid + 1 expired entry directly to disk so prune has
    # something concrete to compact.
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    now = ai_cache._now()
    rows = [
        {"k": ai_cache._key("a", "", False), "ts": now, "v": "1"},
        {"k": ai_cache._key("b", "", False), "ts": now, "v": "2"},
        {"k": ai_cache._key("c", "", False), "ts": 0, "v": "expired"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    ai_cache.reset_cache_for_tests()
    kept = ai_cache.prune(path)
    assert kept == 2  # "a" and "b" stay, "c" pruned


def test_key_is_stable_across_calls():
    from utils import ai_cache

    k1 = ai_cache._key("p", "m", True)
    k2 = ai_cache._key("p", "m", True)
    assert k1 == k2
    assert len(k1) == 24  # truncated sha256
