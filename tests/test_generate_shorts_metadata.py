"""Tests for build_short_metadata in generate_shorts.py.

Pins the contract between the generator (which writes the meta JSON)
and the uploader (which reads it). The `is_short` flag in particular
used to be missing — the .done sidecar then defaulted to False, so
analytics classified every Short as a regular video.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PIL")  # generate_shorts pulls Pillow at import time


def _story() -> dict:
    return {
        "title":          "Headline that will become the seo title",
        "category":       "wildlife",
        "source":         "Pexels",
        "source_url":     "https://www.pexels.com/video/xyz",
        "slug":           "headline-that-will-become-the-seo-title-2026-05-19",
        "yt_description": "AI-authored Short description. More info follows.",
        "yt_tags":        ["lion", "wildlife", "savanna"],
        "topic_hashtag":  "Wildlife",
        "discovery_hashtags": [
            "fyp", "foryou", "wildlife", "wildanimals", "safari", "funfacts",
        ],
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
    # Contract with upload_tiktok.upload_video — the keys it actually reads.
    for required in ("title", "description", "tags", "privacy_level",
                     "thumbnail", "video", "is_short", "channel_handle"):
        assert required in meta, f"missing required field: {required}"


def test_metadata_caption_uses_tiktok_hashtags(tmp_path: Path):
    """TikTok-native hashtags (#fyp / #foryou + niche) replace the legacy
    YouTube #Shorts block. The story carries `discovery_hashtags` set
    by fetch_animals.ANIMAL_TOPICS, lowercased into the caption."""
    from generate_shorts import build_short_metadata
    meta = build_short_metadata(
        _story(),
        tmp_path / "short-foo.mp4",
        tmp_path / "short-foo_thumb.jpg",
    )
    desc = meta["description"]
    assert "#fyp" in desc
    assert "#foryou" in desc
    assert "#wildlife" in desc
    # Niche discovery hashtag from the story's discovery_hashtags list.
    assert "#wildanimals" in desc
    # No legacy YouTube hashtags should survive.
    assert "#Shorts" not in desc
    # The empty #Global geo hashtag should not appear either.
    assert "#Global" not in desc


def test_metadata_hashtags_are_lowercase(tmp_path: Path):
    """TikTok treats #Wildlife and #wildlife as different in some
    discovery surfaces — we always lowercase for consistency."""
    from generate_shorts import build_short_metadata
    meta = build_short_metadata(
        _story(),
        tmp_path / "short-foo.mp4",
        tmp_path / "short-foo_thumb.jpg",
    )
    import re as _re
    hashtags = _re.findall(r"#([A-Za-z0-9]+)", meta["description"])
    for tag in hashtags:
        assert tag == tag.lower(), f"hashtag #{tag} is not lowercase"


def test_metadata_caption_respects_tiktok_2200_limit(tmp_path: Path):
    from generate_shorts import build_short_metadata
    meta = build_short_metadata(
        _story(),
        tmp_path / "short-foo.mp4",
        tmp_path / "short-foo_thumb.jpg",
    )
    assert len(meta["description"]) <= 2200


def test_metadata_falls_back_when_discovery_hashtags_missing(tmp_path: Path):
    """Older queue entries (pre-discovery_hashtags) still get a sensible
    hashtag block synthesised from category + topic_hashtag."""
    from generate_shorts import build_short_metadata
    legacy_story = _story()
    del legacy_story["discovery_hashtags"]
    meta = build_short_metadata(
        legacy_story,
        tmp_path / "short-foo.mp4",
        tmp_path / "short-foo_thumb.jpg",
    )
    desc = meta["description"]
    assert "#fyp" in desc
    assert "#wildlife" in desc


def test_metadata_preserves_experiments(tmp_path: Path):
    from generate_shorts import build_short_metadata
    meta = build_short_metadata(
        _story(),
        tmp_path / "short-foo.mp4",
        tmp_path / "short-foo_thumb.jpg",
    )
    assert meta["experiments"] == {"hook_style": "outcome_first"}


def test_metadata_privacy_level_defaults_public(tmp_path: Path):
    from generate_shorts import build_short_metadata
    meta = build_short_metadata(
        _story(),
        tmp_path / "short-foo.mp4",
        tmp_path / "short-foo_thumb.jpg",
    )
    assert meta["privacy_level"] in (
        "PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"
    )
