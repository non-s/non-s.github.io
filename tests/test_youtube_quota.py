"""Tests for utils/youtube_quota.py — pure file I/O + arithmetic."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from utils import youtube_quota


@pytest.fixture
def isolated_log(tmp_path, monkeypatch):
    p = tmp_path / "quota_log.jsonl"
    monkeypatch.setattr(youtube_quota, "QUOTA_LOG", p)
    return p


def test_cost_of_known_op():
    assert youtube_quota.cost_of("videos.insert") == 1600
    assert youtube_quota.cost_of("thumbnails.set") == 50
    assert youtube_quota.cost_of("playlistItems.insert") == 50
    assert youtube_quota.cost_of("commentThreads.insert") == 50


def test_cost_of_unknown_op_is_zero():
    assert youtube_quota.cost_of("not.a.real.op") == 0


def test_record_appends_jsonl(isolated_log):
    youtube_quota.record("videos.insert", channel="en", video_id="abc")
    lines = isolated_log.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["op"] == "videos.insert"
    assert entry["cost"] == 1600
    assert entry["channel"] == "en"
    assert entry["video_id"] == "abc"


def test_record_handles_unknown_op_gracefully(isolated_log):
    cost = youtube_quota.record("nope.unknown", channel="en")
    assert cost == 0
    entry = json.loads(isolated_log.read_text(encoding="utf-8").strip())
    assert entry["cost"] == 0


def test_daily_used_sums_today_only(isolated_log):
    now = time.time()
    yesterday = now - 86400 * 2  # safely two days ago
    # Write entries directly so we control timestamps.
    isolated_log.write_text("\n".join([
        json.dumps({"ts": now,       "op": "videos.insert",   "cost": 1600}),
        json.dumps({"ts": now,       "op": "thumbnails.set",  "cost": 50}),
        json.dumps({"ts": yesterday, "op": "videos.insert",   "cost": 1600}),  # excluded
    ]) + "\n", encoding="utf-8")
    assert youtube_quota.daily_used(now=now, path=isolated_log) == 1650


def test_daily_used_handles_missing_file(tmp_path):
    p = tmp_path / "nope.jsonl"
    assert youtube_quota.daily_used(path=p) == 0


def test_daily_used_skips_malformed_lines(isolated_log):
    now = time.time()
    isolated_log.write_text("not json\n"
                              + json.dumps({"ts": now, "cost": 50}) + "\n"
                              + "{partial\n"
                              + json.dumps({"ts": now, "cost": 100}) + "\n",
                              encoding="utf-8")
    assert youtube_quota.daily_used(now=now, path=isolated_log) == 150


def test_warn_if_near_cap_under_threshold(isolated_log, monkeypatch):
    monkeypatch.setattr(youtube_quota, "DAILY_BUDGET", 10000)
    monkeypatch.setattr(youtube_quota, "WARN_AT", 0.80)
    now = time.time()
    isolated_log.write_text(
        json.dumps({"ts": now, "cost": 1600}) + "\n",
        encoding="utf-8",
    )
    assert youtube_quota.warn_if_near_cap(now=now, path=isolated_log) == ""


def test_warn_if_near_cap_emits_when_over(isolated_log, monkeypatch):
    monkeypatch.setattr(youtube_quota, "DAILY_BUDGET", 10000)
    monkeypatch.setattr(youtube_quota, "WARN_AT", 0.80)
    now = time.time()
    # 5 uploads × 1650 = 8250 = 82.5 % of 10k — over threshold.
    isolated_log.write_text("\n".join(
        json.dumps({"ts": now, "cost": 1650}) for _ in range(5)
    ) + "\n", encoding="utf-8")
    warn = youtube_quota.warn_if_near_cap(now=now, path=isolated_log)
    assert "8250" in warn
    assert "82" in warn


def test_summary_shape(isolated_log):
    now = time.time()
    isolated_log.write_text(
        json.dumps({"ts": now, "cost": 1650}) + "\n",
        encoding="utf-8",
    )
    s = youtube_quota.summary(now=now, path=isolated_log)
    assert s["used"] == 1650
    assert s["budget"] == youtube_quota.DAILY_BUDGET
    assert s["remaining"] == youtube_quota.DAILY_BUDGET - 1650
    assert s["pct_used"] > 0
    assert s["warning"] == ""


def test_prune_drops_old_entries(isolated_log):
    now = time.time()
    old = now - 86400 * 60      # 60 days
    fresh = now - 86400 * 3     # 3 days
    isolated_log.write_text("\n".join([
        json.dumps({"ts": old,   "cost": 100}),
        json.dumps({"ts": fresh, "cost": 200}),
        json.dumps({"ts": now,   "cost": 300}),
    ]) + "\n", encoding="utf-8")
    kept = youtube_quota.prune_older_than(days=30, path=isolated_log)
    assert kept == 2
    # File now contains only the fresh + now entries.
    body = isolated_log.read_text(encoding="utf-8")
    assert "100" not in body
    assert "200" in body
    assert "300" in body


def test_record_doesnt_raise_on_unwritable_path(monkeypatch):
    """If the log path can't be written (e.g. read-only volume) the
    record() call still returns the estimated cost without raising."""
    monkeypatch.setattr(
        youtube_quota,
        "QUOTA_LOG",
        Path("/proc/this/will/never/be/writable.jsonl"),
    )
    # Should not raise; should still return cost.
    assert youtube_quota.record("videos.insert") == 1600
