"""Tests for scripts/rebrand_video_titles.py."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import scripts.rebrand_video_titles as rebrand


def _write_marker(videos_dir, video_id, title, name):
    videos_dir.mkdir(parents=True, exist_ok=True)
    path = videos_dir / name
    path.write_text(
        json.dumps({"video_id": video_id, "title": title, "description": "d", "tags": ["lofi"]}),
        encoding="utf-8",
    )
    return path


def test_apply_continues_past_a_single_video_failure(tmp_path, monkeypatch):
    """A 404 (deleted/private video) on one id must not sink the rest of
    the batch -- this is exactly what happened in production on 2026-07-19:
    an unhandled exception on the first id crashed main() before any of
    the other 19 were even attempted."""
    videos_dir = tmp_path / "_videos"
    ids = list(rebrand.NEW_TITLES.keys())[:3]
    for i, video_id in enumerate(ids):
        _write_marker(videos_dir, video_id, f"Old Title {i}", f"short-{i}.done")

    monkeypatch.setattr(rebrand, "VIDEOS_DIR", videos_dir)

    calls = []

    def fake_apply_plan(youtube, plan):
        calls.append(plan["video_id"])
        if plan["video_id"] == ids[0]:
            raise Exception("404 videoNotFound")
        return {"id": plan["video_id"]}

    with patch.object(rebrand, "get_youtube_service", return_value=MagicMock()):
        with patch.object(rebrand, "apply_plan", side_effect=fake_apply_plan):
            import sys

            monkeypatch.setattr(
                sys, "argv", ["rebrand_video_titles.py", "--videos-dir", str(videos_dir), "--apply", "--json"]
            )
            exit_code = rebrand.main()

    assert calls == ids
    assert exit_code == 0


def test_main_returns_error_when_every_video_fails(tmp_path, monkeypatch):
    videos_dir = tmp_path / "_videos"
    video_id = next(iter(rebrand.NEW_TITLES))
    _write_marker(videos_dir, video_id, "Old Title", "short-0.done")
    monkeypatch.setattr(rebrand, "VIDEOS_DIR", videos_dir)

    with patch.object(rebrand, "get_youtube_service", return_value=MagicMock()):
        with patch.object(rebrand, "apply_plan", side_effect=Exception("boom")):
            import sys

            monkeypatch.setattr(
                sys, "argv", ["rebrand_video_titles.py", "--videos-dir", str(videos_dir), "--apply", "--json"]
            )
            exit_code = rebrand.main()

    assert exit_code == 1
