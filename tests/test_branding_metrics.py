"""Tests for utils/branding_metrics.py."""

from __future__ import annotations

import json

from utils import branding_metrics


def _write_marker(videos_dir, name, *, video_id, title, series="", dedupe_applied=False):
    marker = {
        "video_id": video_id,
        "title": title,
        "series": series,
        "upload_title_dedupe": {"applied": dedupe_applied},
    }
    (videos_dir / name).write_text(json.dumps(marker), encoding="utf-8")


def test_returns_zeroed_stats_for_an_empty_directory(tmp_path):
    stats = branding_metrics.collect_branding_stats(tmp_path)
    assert stats == {
        "total": 0,
        "title_collisions": 0,
        "collision_rate": 0.0,
        "playlist_buckets": {},
        "series": {},
    }


def test_counts_total_and_collisions(tmp_path):
    _write_marker(tmp_path, "short-1.done", video_id="V1", title="Rainy Night Anime Lofi", dedupe_applied=True)
    _write_marker(tmp_path, "short-2.done", video_id="V2", title="Sleepy Cat Anime Lofi", dedupe_applied=False)
    _write_marker(tmp_path, "short-3.done", video_id="V3", title="Snowy Night Anime Lofi", dedupe_applied=True)

    stats = branding_metrics.collect_branding_stats(tmp_path)

    assert stats["total"] == 3
    assert stats["title_collisions"] == 2
    assert stats["collision_rate"] == round(2 / 3, 4)


def test_groups_by_playlist_bucket_from_the_title(tmp_path):
    _write_marker(tmp_path, "short-1.done", video_id="V1", title="Rainy Night Anime Lofi")
    _write_marker(tmp_path, "short-2.done", video_id="V2", title="Rain on the Window Anime Lofi")
    _write_marker(tmp_path, "short-3.done", video_id="V3", title="Sleepy Cat Anime Lofi")

    stats = branding_metrics.collect_branding_stats(tmp_path)

    assert stats["playlist_buckets"] == {"Rainy Night Lofi": 2, "Cozy Cat Lofi": 1}


def test_groups_by_series_when_present(tmp_path):
    _write_marker(
        tmp_path, "short-1.done", video_id="V1", title="Rainy Night Anime Lofi", series="Rainy Night Lofi Shorts"
    )
    _write_marker(
        tmp_path, "short-2.done", video_id="V2", title="Rain on the Window Anime Lofi", series="Rainy Night Lofi Shorts"
    )
    _write_marker(
        tmp_path, "mix-1.done", video_id="V3", title="Rainy Night Anime Lofi (1 Hour)", series="Rainy Night Lofi Mix"
    )

    stats = branding_metrics.collect_branding_stats(tmp_path)

    assert stats["series"] == {"Rainy Night Lofi Shorts": 2, "Rainy Night Lofi Mix": 1}


def test_ignores_markers_without_a_video_id(tmp_path):
    (tmp_path / "short-1.done").write_text(json.dumps({"title": "no video id here"}), encoding="utf-8")
    stats = branding_metrics.collect_branding_stats(tmp_path)
    assert stats["total"] == 0


def test_ignores_unreadable_or_malformed_markers(tmp_path):
    (tmp_path / "short-1.done").write_text("not json", encoding="utf-8")
    _write_marker(tmp_path, "short-2.done", video_id="V2", title="Rainy Night Anime Lofi")

    stats = branding_metrics.collect_branding_stats(tmp_path)
    assert stats["total"] == 1
