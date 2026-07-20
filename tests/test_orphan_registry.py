"""Tests for utils/orphan_registry.py."""

from __future__ import annotations

import json

from utils import orphan_registry


def test_load_orphan_ids_returns_empty_set_when_file_missing(tmp_path):
    assert orphan_registry.load_orphan_ids(tmp_path / "missing.jsonl") == set()


def test_append_orphans_then_load_round_trips(tmp_path):
    path = tmp_path / "orphaned_videos.jsonl"
    rows = [
        {"video_id": "abc123", "title": "Rainy Night Anime Lofi", "detected_at": "2026-07-19T00:00:00+00:00"},
        {"video_id": "def456", "title": "Sleepy Cat Anime Lofi", "detected_at": "2026-07-19T00:00:00+00:00"},
    ]

    orphan_registry.append_orphans(rows, path)

    assert orphan_registry.load_orphan_ids(path) == {"abc123", "def456"}


def test_append_orphans_is_additive_across_calls(tmp_path):
    path = tmp_path / "orphaned_videos.jsonl"
    orphan_registry.append_orphans([{"video_id": "abc123"}], path)
    orphan_registry.append_orphans([{"video_id": "def456"}], path)

    assert orphan_registry.load_orphan_ids(path) == {"abc123", "def456"}
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_append_orphans_does_nothing_for_empty_list(tmp_path):
    path = tmp_path / "orphaned_videos.jsonl"
    orphan_registry.append_orphans([], path)
    assert not path.exists()


def test_load_orphan_ids_skips_malformed_lines(tmp_path):
    path = tmp_path / "orphaned_videos.jsonl"
    path.write_text('{"video_id": "abc123"}\nnot json\n\n{"video_id": "def456"}\n', encoding="utf-8")

    assert orphan_registry.load_orphan_ids(path) == {"abc123", "def456"}


def test_load_orphan_ids_ignores_rows_without_a_video_id(tmp_path):
    path = tmp_path / "orphaned_videos.jsonl"
    path.write_text(json.dumps({"title": "no id here"}) + "\n", encoding="utf-8")

    assert orphan_registry.load_orphan_ids(path) == set()
