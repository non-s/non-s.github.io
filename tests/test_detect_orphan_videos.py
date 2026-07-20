"""Tests for scripts/detect_orphan_videos.py."""

from __future__ import annotations

import json

import scripts.detect_orphan_videos as detector
from utils import orphan_registry


def _write_marker(videos_dir, name, video_id, title="Rainy Night Anime Lofi"):
    (videos_dir / name).write_text(json.dumps({"video_id": video_id, "title": title}), encoding="utf-8")


class _Req:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _Videos:
    def __init__(self, existing_ids):
        self.existing_ids = existing_ids
        self.list_calls = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        ids = [i for i in kwargs["id"].split(",") if i in self.existing_ids]
        return _Req({"items": [{"id": i} for i in ids]})


class _YouTube:
    def __init__(self, existing_ids):
        self._videos = _Videos(existing_ids)

    def videos(self):
        return self._videos


def test_marker_video_ids_reads_every_done_marker(tmp_path):
    _write_marker(tmp_path, "short-1.done", "VID1")
    _write_marker(tmp_path, "mix-1.done", "VID2")
    (tmp_path / "short-2.json").write_text("{}", encoding="utf-8")  # not a .done marker, ignored

    ids = detector._marker_video_ids(tmp_path)
    assert set(ids) == {"VID1", "VID2"}


def test_find_orphans_flags_markers_youtube_no_longer_knows_about(tmp_path):
    _write_marker(tmp_path, "short-1.done", "STILL_UP", title="Rainy Night Anime Lofi")
    _write_marker(tmp_path, "short-2.done", "DELETED_ONE", title="Sleepy Cat Anime Lofi")
    youtube = _YouTube(existing_ids={"STILL_UP"})

    orphans = detector.find_orphans(youtube, videos_dir=tmp_path)

    assert [o["video_id"] for o in orphans] == ["DELETED_ONE"]
    assert orphans[0]["title"] == "Sleepy Cat Anime Lofi"
    assert orphans[0]["marker"] == "short-2.done"


def test_find_orphans_skips_ids_already_in_the_registry(tmp_path):
    _write_marker(tmp_path, "short-1.done", "ALREADY_KNOWN")
    _write_marker(tmp_path, "short-2.done", "NEWLY_DELETED")
    youtube = _YouTube(existing_ids=set())  # both look deleted to the API

    orphans = detector.find_orphans(youtube, videos_dir=tmp_path, already_known={"ALREADY_KNOWN"})

    assert [o["video_id"] for o in orphans] == ["NEWLY_DELETED"]


def test_find_orphans_returns_empty_when_nothing_new_to_check(tmp_path):
    _write_marker(tmp_path, "short-1.done", "ALREADY_KNOWN")
    youtube = _YouTube(existing_ids=set())

    orphans = detector.find_orphans(youtube, videos_dir=tmp_path, already_known={"ALREADY_KNOWN"})

    assert orphans == []
    assert youtube._videos.list_calls == []  # never even calls the API for nothing to check


def test_existing_video_ids_batches_requests_at_50(tmp_path):
    ids = [f"V{i}" for i in range(120)]
    youtube = _YouTube(existing_ids=set(ids))

    existing = detector._existing_video_ids(youtube, ids)

    assert existing == set(ids)
    assert len(youtube._videos.list_calls) == 3  # 50 + 50 + 20


def test_main_logs_new_orphans_and_returns_zero(tmp_path, monkeypatch):
    videos_dir = tmp_path / "_videos"
    videos_dir.mkdir()
    _write_marker(videos_dir, "short-1.done", "DELETED_ONE")
    registry_path = tmp_path / "orphaned_videos.jsonl"

    monkeypatch.setattr(detector, "VIDEOS_DIR", videos_dir)
    monkeypatch.setattr(orphan_registry, "ORPHAN_LOG_PATH", registry_path)
    monkeypatch.setattr(detector, "get_youtube_service", lambda: _YouTube(existing_ids=set()))

    assert detector.main() == 0
    assert orphan_registry.load_orphan_ids(registry_path) == {"DELETED_ONE"}


def test_main_does_not_re_log_already_known_orphans(tmp_path, monkeypatch):
    videos_dir = tmp_path / "_videos"
    videos_dir.mkdir()
    _write_marker(videos_dir, "short-1.done", "ALREADY_KNOWN")
    registry_path = tmp_path / "orphaned_videos.jsonl"
    orphan_registry.append_orphans([{"video_id": "ALREADY_KNOWN"}], registry_path)

    monkeypatch.setattr(detector, "VIDEOS_DIR", videos_dir)
    monkeypatch.setattr(orphan_registry, "ORPHAN_LOG_PATH", registry_path)
    monkeypatch.setattr(detector, "get_youtube_service", lambda: _YouTube(existing_ids=set()))

    assert detector.main() == 0
    # Still just the one line -- never re-appended, never double-checked via the API.
    assert len(registry_path.read_text(encoding="utf-8").splitlines()) == 1
