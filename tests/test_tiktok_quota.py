"""Tests for utils/tiktok_quota.py — pure file I/O + arithmetic."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from utils import tiktok_quota


@pytest.fixture
def isolated_log(tmp_path, monkeypatch):
    p = tmp_path / "tiktok_quota_log.jsonl"
    monkeypatch.setattr(tiktok_quota, "QUOTA_LOG", p)
    return p


def test_cost_of_known_op():
    assert tiktok_quota.cost_of("video.publish.init") == 1
    assert tiktok_quota.cost_of("video.upload.init") == 1
    assert tiktok_quota.cost_of("publish.status.fetch") == 0
    assert tiktok_quota.cost_of("video.list") == 0


def test_cost_of_unknown_op_is_zero():
    assert tiktok_quota.cost_of("not.a.real.op") == 0


def test_record_appends_jsonl(isolated_log):
    tiktok_quota.record("video.publish.init", channel="en",
                        publish_id="v_inbox.123")
    lines = isolated_log.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["op"] == "video.publish.init"
    assert entry["cost"] == 1
    assert entry["channel"] == "en"
    assert entry["publish_id"] == "v_inbox.123"


def test_record_handles_unknown_op_gracefully(isolated_log):
    cost = tiktok_quota.record("nope.unknown", channel="en")
    assert cost == 0
    entry = json.loads(isolated_log.read_text(encoding="utf-8").strip())
    assert entry["cost"] == 0


def test_daily_used_sums_today_only(isolated_log):
    now = time.time()
    yesterday = now - 86400 * 2  # safely two days ago
    isolated_log.write_text("\n".join([
        json.dumps({"ts": now,       "op": "video.publish.init", "cost": 1}),
        json.dumps({"ts": now,       "op": "video.publish.init", "cost": 1}),
        json.dumps({"ts": yesterday, "op": "video.publish.init", "cost": 1}),  # excluded
    ]) + "\n", encoding="utf-8")
    assert tiktok_quota.daily_used(now=now, path=isolated_log) == 2


def test_daily_used_handles_missing_file(tmp_path):
    p = tmp_path / "nope.jsonl"
    assert tiktok_quota.daily_used(path=p) == 0


def test_daily_used_skips_malformed_lines(isolated_log):
    now = time.time()
    isolated_log.write_text("not json\n"
                              + json.dumps({"ts": now, "cost": 1}) + "\n"
                              + "{partial\n"
                              + json.dumps({"ts": now, "cost": 1}) + "\n",
                              encoding="utf-8")
    assert tiktok_quota.daily_used(now=now, path=isolated_log) == 2


def test_warn_if_near_cap_under_threshold(isolated_log, monkeypatch):
    monkeypatch.setattr(tiktok_quota, "DAILY_BUDGET", 30)
    monkeypatch.setattr(tiktok_quota, "WARN_AT", 0.80)
    now = time.time()
    isolated_log.write_text(
        json.dumps({"ts": now, "cost": 1}) + "\n",
        encoding="utf-8",
    )
    assert tiktok_quota.warn_if_near_cap(now=now, path=isolated_log) == ""


def test_warn_if_near_cap_emits_when_over(isolated_log, monkeypatch):
    monkeypatch.setattr(tiktok_quota, "DAILY_BUDGET", 30)
    monkeypatch.setattr(tiktok_quota, "WARN_AT", 0.80)
    now = time.time()
    # 25 posts = 83 % of 30 — over threshold.
    isolated_log.write_text("\n".join(
        json.dumps({"ts": now, "cost": 1}) for _ in range(25)
    ) + "\n", encoding="utf-8")
    warn = tiktok_quota.warn_if_near_cap(now=now, path=isolated_log)
    assert "25" in warn
    assert "30" in warn


def test_summary_shape(isolated_log):
    now = time.time()
    isolated_log.write_text(
        json.dumps({"ts": now, "cost": 1}) + "\n",
        encoding="utf-8",
    )
    s = tiktok_quota.summary(now=now, path=isolated_log)
    assert s["used"] == 1
    assert s["budget"] == tiktok_quota.DAILY_BUDGET
    assert s["remaining"] == tiktok_quota.DAILY_BUDGET - 1
    assert s["pct_used"] > 0
    assert s["warning"] == ""


def test_prune_drops_old_entries(isolated_log):
    now = time.time()
    old = now - 86400 * 60      # 60 days
    fresh = now - 86400 * 3     # 3 days
    isolated_log.write_text("\n".join([
        json.dumps({"ts": old,   "cost": 1, "op": "old"}),
        json.dumps({"ts": fresh, "cost": 1, "op": "fresh"}),
        json.dumps({"ts": now,   "cost": 1, "op": "today"}),
    ]) + "\n", encoding="utf-8")
    kept = tiktok_quota.prune_older_than(days=30, path=isolated_log)
    assert kept == 2
    body = isolated_log.read_text(encoding="utf-8")
    assert "old" not in body
    assert "fresh" in body
    assert "today" in body


def test_record_doesnt_raise_on_unwritable_path(monkeypatch):
    """If the log path can't be written (e.g. read-only volume) the
    record() call still returns the estimated cost without raising."""
    monkeypatch.setattr(
        tiktok_quota,
        "QUOTA_LOG",
        Path("/proc/this/will/never/be/writable.jsonl"),
    )
    assert tiktok_quota.record("video.publish.init") == 1
