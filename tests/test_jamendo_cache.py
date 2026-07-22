"""Tests for utils/jamendo_cache.py."""

from __future__ import annotations

import importlib
import json

import pytest


@pytest.fixture
def fresh_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("JAMENDO_CACHE_PATH", str(tmp_path / "jamendo_search_cache.jsonl"))
    monkeypatch.setenv("JAMENDO_CACHE_ENABLED", "1")
    monkeypatch.setenv("JAMENDO_CACHE_TTL_HOURS", "24")
    from utils import jamendo_cache

    importlib.reload(jamendo_cache)
    jamendo_cache.reset_cache_for_tests()
    yield jamendo_cache, tmp_path / "jamendo_search_cache.jsonl"


def test_get_returns_none_on_empty_cache(fresh_cache):
    cache, _ = fresh_cache
    assert cache.get("jazz", 0, 200) is None


def test_put_then_get_round_trip(fresh_cache):
    cache, path = fresh_cache
    results = [{"id": 1}, {"id": 2}]
    cache.put("jazz", 0, 200, results)
    assert cache.get("jazz", 0, 200) == results
    assert path.exists()


def test_different_query_is_different_key(fresh_cache):
    cache, _ = fresh_cache
    cache.put("jazz", 0, 200, [{"id": 1}])
    cache.put("classical", 0, 200, [{"id": 2}])
    assert cache.get("jazz", 0, 200) == [{"id": 1}]
    assert cache.get("classical", 0, 200) == [{"id": 2}]


def test_cached_search_uses_fetcher_on_miss(fresh_cache):
    cache, _ = fresh_cache
    calls = []

    def fetcher(tags, offset, limit):
        calls.append((tags, offset, limit))
        return [{"id": 42}], False

    results, hard_failure = cache.cached_search("jazz", 400, 200, fetcher)
    assert results == [{"id": 42}]
    assert hard_failure is False
    assert calls == [("jazz", 400, 200)]


def test_cached_search_skips_fetcher_on_hit(fresh_cache):
    cache, _ = fresh_cache
    cache.put("jazz", 0, 200, [{"id": 99}])

    def fetcher(*a, **k):
        raise AssertionError("fetcher should not be called on cache hit")

    results, hard_failure = cache.cached_search("jazz", 0, 200, fetcher)
    assert results == [{"id": 99}]
    assert hard_failure is False


def test_cached_search_does_not_cache_empty_or_failed_results(fresh_cache):
    cache, path = fresh_cache

    def fetcher_empty(*a, **k):
        return [], False

    cache.cached_search("jazz", 0, 200, fetcher_empty)
    assert cache.get("jazz", 0, 200) is None

    def fetcher_fail(*a, **k):
        return [], True

    cache.cached_search("classical", 0, 200, fetcher_fail)
    assert cache.get("classical", 0, 200) is None


def test_expired_entries_are_ignored(fresh_cache):
    cache, path = fresh_cache
    key = cache._key("jazz", 0, 200)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"k": key, "ts": 0, "v": [{"id": 1}]}),
        encoding="utf-8",
    )
    cache.reset_cache_for_tests()
    assert cache.get("jazz", 0, 200) is None


def test_prune_rewrites_file_dropping_expired(fresh_cache):
    cache, path = fresh_cache
    now = cache._now()
    k1 = cache._key("jazz", 0, 200)
    k2 = cache._key("classical", 0, 200)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"k": k1, "ts": now, "v": [{"id": 1}]},
        {"k": k2, "ts": 0, "v": [{"id": 2}]},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    cache.reset_cache_for_tests()
    kept = cache.prune(path)
    assert kept == 1
