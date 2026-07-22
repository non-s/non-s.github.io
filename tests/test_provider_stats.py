"""Tests for utils/provider_stats.py."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from utils import provider_stats


@pytest.fixture
def isolated_log(tmp_path, monkeypatch):
    p = tmp_path / "stats.jsonl"
    monkeypatch.setattr(provider_stats, "STATS_LOG", p)
    return p


def test_no_data_returns_default_order(isolated_log):
    assert provider_stats.preferred_chain() == list(provider_stats.DEFAULT_ORDER)


def test_records_get_written(isolated_log):
    provider_stats.record("mistral", success=True)
    provider_stats.record("cerebras", success=False, status=429)
    body = isolated_log.read_text(encoding="utf-8").strip().split("\n")
    assert len(body) == 2
    e0 = json.loads(body[0])
    assert e0["provider"] == "mistral"
    assert e0["ok"] is True
    e1 = json.loads(body[1])
    assert e1["ok"] is False
    assert e1["status"] == 429


def test_success_rate_basic(isolated_log):
    for _ in range(3):
        provider_stats.record("mistral", success=True)
    provider_stats.record("mistral", success=False)
    rate = provider_stats.success_rate("mistral")
    assert rate is not None
    assert 0.7 < rate < 0.8  # 3/4 = 0.75


def test_success_rate_no_data_returns_none(isolated_log):
    assert provider_stats.success_rate("mistral") is None


def test_preferred_chain_sorts_by_rate(isolated_log):
    # Mistral: 0 % success → push to back.
    for _ in range(10):
        provider_stats.record("mistral", success=False, status=429)
    # Cerebras: 100 % success → front.
    for _ in range(10):
        provider_stats.record("cerebras", success=True)
    # Gemini: 50 % success → middle.
    for _ in range(5):
        provider_stats.record("gemini", success=True)
        provider_stats.record("gemini", success=False)
    chain = provider_stats.preferred_chain()
    assert chain[0] == "cerebras"
    assert chain[-1] == "mistral"
    assert chain.index("gemini") < chain.index("mistral")


def test_preferred_chain_for_json_starts_with_json_strength_provider(isolated_log):
    chain = provider_stats.preferred_chain_for_task("auto", json_mode=True)
    assert chain[0] == "gemini"
    assert chain.index("cerebras") < chain.index("mistral")


def test_provider_cooldown_pushes_recent_429_to_back(isolated_log, monkeypatch):
    monkeypatch.setattr(provider_stats, "COOLDOWN_SECONDS", 900)
    now = time.time()
    isolated_log.write_text(
        json.dumps({"ts": now - 20, "provider": "gemini", "ok": False, "status": 429})
        + "\n"
        + json.dumps({"ts": now - 10, "provider": "gemini", "ok": False, "status": 429})
        + "\n"
        + json.dumps({"ts": now - 5, "provider": "cerebras", "ok": True, "status": None})
        + "\n",
        encoding="utf-8",
    )

    assert provider_stats.is_in_cooldown("gemini", path=isolated_log, now=now)
    chain = provider_stats.preferred_chain_for_task("json", path=isolated_log)
    assert chain[-1] == "gemini"


def test_preferred_chain_unknown_providers_keep_default_rank(isolated_log):
    # Only one provider has data — the others should appear in default order.
    for _ in range(5):
        provider_stats.record("groq", success=True)
    chain = provider_stats.preferred_chain()
    # groq has data, scores 1.0; placed first.
    assert chain[0] == "groq"
    # Remaining keep their default relative order.
    remaining = [p for p in chain if p != "groq"]
    expected = [p for p in provider_stats.DEFAULT_ORDER if p != "groq"]
    assert remaining == expected


def test_window_size_caps_old_entries(isolated_log, monkeypatch):
    monkeypatch.setattr(provider_stats, "WINDOW_SIZE", 5)
    # 5 failures, then 5 successes — newest are the 5 successes.
    for _ in range(5):
        provider_stats.record("mistral", success=False)
    for _ in range(5):
        provider_stats.record("mistral", success=True)
    rate = provider_stats.success_rate("mistral")
    # Only the latest 5 count → 1.0 success.
    assert rate == 1.0


def test_prune_drops_old(isolated_log):
    # Manually write an old + new row.
    old_ts = time.time() - 30 * 86400
    new_ts = time.time()
    isolated_log.write_text(
        json.dumps({"ts": old_ts, "provider": "mistral", "ok": True})
        + "\n"
        + json.dumps({"ts": new_ts, "provider": "mistral", "ok": True})
        + "\n",
        encoding="utf-8",
    )
    kept = provider_stats.prune_older_than(days=7, path=isolated_log)
    assert kept == 1


def test_record_handles_unwritable_path(monkeypatch):
    monkeypatch.setattr(provider_stats, "STATS_LOG", Path("/proc/never-writable/x.jsonl"))
    # Should not raise.
    provider_stats.record("mistral", success=True)
