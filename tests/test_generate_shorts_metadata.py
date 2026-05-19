"""Tests for build_short_metadata in generate_shorts.py.

Pins the contract between the generator (which writes the meta JSON)
and the uploader (which reads it). The `is_short` flag in particular
used to be missing — the .done sidecar then defaulted to False, so
youtube_analytics.py classified every Short as a regular video.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PIL")  # generate_shorts pulls Pillow at import time


def _story() -> dict:
    return {
        "title":          "Headline that will become the seo title",
        "category":       "world",
        "source":         "Reuters",
        "source_url":     "https://example.com/article",
        "slug":           "headline-that-will-become-the-seo-title-2026-05-19",
        "yt_description": "AI-authored Short description. #Shorts #WorldNews #Global #Breaking",
        "yt_tags":        ["headline", "world", "reuters"],
        "geo_hashtag":    "Global",
        "topic_hashtag":  "Breaking",
        "experiments":    {"hook_style": "outcome_first"},
    }


def test_metadata_marks_is_short_true(tmp_path: Path):
    from generate_shorts import build_short_metadata
    meta = build_short_metadata(
        _story(),
        tmp_path / "short-foo.mp4",
        tmp_path / "short-foo_thumb.jpg",
    )
    assert meta["is_short"] is True


def test_metadata_carries_required_uploader_fields(tmp_path: Path):
    from generate_shorts import build_short_metadata
    meta = build_short_metadata(
        _story(),
        tmp_path / "short-foo.mp4",
        tmp_path / "short-foo_thumb.jpg",
    )
    # Contract with upload_youtube.upload_video — the keys it actually reads.
    for required in ("title", "description", "tags", "category_id",
                     "privacy", "thumbnail", "video", "is_short"):
        assert required in meta, f"missing required field: {required}"


def test_metadata_title_carries_shorts_suffix(tmp_path: Path):
    from generate_shorts import build_short_metadata
    meta = build_short_metadata(
        _story(),
        tmp_path / "short-foo.mp4",
        tmp_path / "short-foo_thumb.jpg",
    )
    # YouTube needs `#Shorts` in either title OR description — we put
    # it in both to be safe. Title check is the high-confidence one.
    assert meta["title"].endswith("#Shorts")
    assert len(meta["title"]) <= 100  # YouTube hard limit


def test_metadata_preserves_experiments(tmp_path: Path):
    from generate_shorts import build_short_metadata
    meta = build_short_metadata(
        _story(),
        tmp_path / "short-foo.mp4",
        tmp_path / "short-foo_thumb.jpg",
    )
    assert meta["experiments"] == {"hook_style": "outcome_first"}
