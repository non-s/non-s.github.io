"""Tests for the YouTube Shorts metadata contract."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PIL")


def _story() -> dict:
    return {
        "title": "Headline that will become the seo title",
        "category": "wildlife",
        "source": "Pexels",
        "source_url": "https://www.pexels.com/video/xyz",
        "slug": "headline-that-will-become-the-seo-title-2026-05-19",
        "yt_description": "AI-authored Short description. More info follows.",
        "yt_tags": ["lion", "wildlife", "savanna"],
        "topic_hashtag": "Wildlife",
        "discovery_hashtags": ["wildlife", "wildanimals", "safari", "funfacts"],
        "experiments": {"hook_style": "outcome_first"},
    }


def _meta(tmp_path: Path) -> dict:
    from generate_shorts import build_short_metadata
    return build_short_metadata(
        _story(),
        tmp_path / "short-foo.mp4",
        tmp_path / "short-foo_thumb.jpg",
    )


def test_metadata_marks_is_short_true(tmp_path: Path):
    assert _meta(tmp_path)["is_short"] is True


def test_metadata_carries_required_youtube_fields(tmp_path: Path):
    meta = _meta(tmp_path)
    for required in (
        "title", "description", "tags", "youtube_privacy",
        "youtube_category_id", "thumbnail", "video", "is_short",
        "channel_handle",
    ):
        assert required in meta, f"missing required field: {required}"


def test_metadata_caption_uses_youtube_shorts_hashtags(tmp_path: Path):
    desc = _meta(tmp_path)["description"]
    assert "#Shorts" in desc
    assert "#AnimalFacts" in desc
    assert "#Wildlife" in desc


def test_metadata_caption_respects_youtube_limit(tmp_path: Path):
    assert len(_meta(tmp_path)["description"]) <= 5000


def test_metadata_falls_back_when_discovery_hashtags_missing(tmp_path: Path):
    from generate_shorts import build_short_metadata
    story = _story()
    del story["discovery_hashtags"]
    meta = build_short_metadata(
        story,
        tmp_path / "short-foo.mp4",
        tmp_path / "short-foo_thumb.jpg",
    )
    assert "#Shorts" in meta["description"]
    assert "#Wildlife" in meta["description"]


def test_metadata_preserves_experiments(tmp_path: Path):
    assert _meta(tmp_path)["experiments"] == {"hook_style": "outcome_first"}


def test_metadata_privacy_defaults_public(tmp_path: Path):
    assert _meta(tmp_path)["youtube_privacy"] == "public"
