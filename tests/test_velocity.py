"""Tests for utils/velocity.py — snapshot logic and aggregation."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from utils import velocity


def _write_done(dirpath: Path, slug: str, uploaded_at: str,
                 video_id: str, **extra) -> Path:
    dirpath.mkdir(parents=True, exist_ok=True)
    p = dirpath / f"{slug}.done"
    payload = {"video_id": video_id, "uploaded_at": uploaded_at,
                "category": extra.get("category", "wildlife"),
                "experiments": extra.get("experiments", {}),
                "language": extra.get("language", "en")}
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_videos_due_finds_2h_offset(tmp_path):
    d = tmp_path / "_videos"
    now = time.time()
    ts = datetime.fromtimestamp(now - 2.1 * 3600, tz=timezone.utc).isoformat()
    _write_done(d, "fresh", ts, "vid-2h")
    targets = velocity._videos_due_for_snapshot(d, now=now)
    assert any(t["video_id"] == "vid-2h" and t["offset_h"] == 2 for t in targets)


def test_videos_due_finds_24h_offset(tmp_path):
    d = tmp_path / "_videos"
    now = time.time()
    ts = datetime.fromtimestamp(now - 23.5 * 3600, tz=timezone.utc).isoformat()
    _write_done(d, "dayold", ts, "vid-24h")
    targets = velocity._videos_due_for_snapshot(d, now=now)
    assert any(t["offset_h"] == 24 for t in targets)


def test_videos_due_skips_outside_window(tmp_path):
    d = tmp_path / "_videos"
    now = time.time()
    ts = datetime.fromtimestamp(now - 12 * 3600, tz=timezone.utc).isoformat()
    _write_done(d, "midday", ts, "vid-mid")
    targets = velocity._videos_due_for_snapshot(d, now=now)
    assert all(t["video_id"] != "vid-mid" for t in targets)


def test_snapshot_velocities_records_to_jsonl(tmp_path, monkeypatch):
    log_path = tmp_path / "velocity.jsonl"
    monkeypatch.setattr(velocity, "VELOCITY_LOG", log_path)
    from utils import tiktok_quota
    monkeypatch.setattr(tiktok_quota, "QUOTA_LOG", tmp_path / "quota.jsonl")
    d = tmp_path / "_videos"
    now = time.time()
    ts = datetime.fromtimestamp(now - 2.0 * 3600, tz=timezone.utc).isoformat()
    _write_done(d, "freshy", ts, "abc123")

    # Stub the TikTok video/query call.
    def _fake_query(_token, _ids):
        return {"abc123": {"id": "abc123", "view_count": 1234,
                            "like_count": 50, "comment_count": 10,
                            "share_count": 7}}
    monkeypatch.setattr(velocity, "_query_tiktok_videos", _fake_query)

    n = velocity.snapshot_velocities(access_token="tk_fake",
                                     done_dirs=(d,), now=now)
    assert n == 1
    body = log_path.read_text(encoding="utf-8").strip()
    entry = json.loads(body)
    assert entry["video_id"] == "abc123"
    assert entry["views"] == 1234
    assert entry["likes"] == 50
    assert entry["shares"] == 7
    assert entry["offset_h"] == 2


def test_snapshot_is_idempotent(tmp_path, monkeypatch):
    log_path = tmp_path / "velocity.jsonl"
    monkeypatch.setattr(velocity, "VELOCITY_LOG", log_path)
    from utils import tiktok_quota
    monkeypatch.setattr(tiktok_quota, "QUOTA_LOG", tmp_path / "quota.jsonl")
    d = tmp_path / "_videos"
    now = time.time()
    ts = datetime.fromtimestamp(now - 2.0 * 3600, tz=timezone.utc).isoformat()
    _write_done(d, "freshy", ts, "abc123")

    monkeypatch.setattr(
        velocity,
        "_query_tiktok_videos",
        lambda _t, _ids: {"abc123": {"id": "abc123", "view_count": 1234}},
    )

    n1 = velocity.snapshot_velocities(access_token="tk_fake",
                                      done_dirs=(d,), now=now)
    n2 = velocity.snapshot_velocities(access_token="tk_fake",
                                      done_dirs=(d,), now=now)
    assert n1 == 1
    assert n2 == 0  # second pass deduplicates by (video_id, offset_h)


def test_aggregate_by_category(tmp_path, monkeypatch):
    log_path = tmp_path / "v.jsonl"
    monkeypatch.setattr(velocity, "VELOCITY_LOG", log_path)
    entries = [
        {"offset_h": 2, "category": "cats",     "views": 500},
        {"offset_h": 2, "category": "cats",     "views": 1500},
        {"offset_h": 2, "category": "wildlife", "views": 2000},
        {"offset_h": 24, "category": "cats",    "views": 10000},  # ignored
    ]
    log_path.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")
    agg = velocity.aggregate_by_category(log_path)
    assert agg["cats"]["n"] == 2
    assert agg["cats"]["mean_2h"] == 1000
    assert agg["wildlife"]["mean_2h"] == 2000


def test_snapshot_empty_when_no_done_files(tmp_path, monkeypatch):
    monkeypatch.setattr(velocity, "VELOCITY_LOG", tmp_path / "v.jsonl")
    # Avoid spurious refresh attempts when there's no work to do.
    monkeypatch.setattr(velocity, "_query_tiktok_videos",
                        lambda _t, _ids: {})
    n = velocity.snapshot_velocities(access_token="tk_fake",
                                     done_dirs=(tmp_path / "empty",))
    assert n == 0
