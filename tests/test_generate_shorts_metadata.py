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


def test_candidates_are_distributed_across_categories():
    from generate_shorts import diversify_candidates
    candidates = [
        {"category": "cats", "title": "cat one"},
        {"category": "cats", "title": "cat two"},
        {"category": "dogs", "title": "dog one"},
        {"category": "birds", "title": "bird one"},
    ]
    diversified = diversify_candidates(candidates)
    assert [item["category"] for item in diversified] == [
        "cats", "dogs", "birds", "cats",
    ]


def test_queue_adapter_preserves_original_pexels_clip():
    from generate_shorts import _queue_to_story
    story = _queue_to_story({
        "id": "story-1",
        "pexels_download_url": "https://files.pexels.com/video.mp4",
    })
    assert story["pexels_download_url"] == "https://files.pexels.com/video.mp4"


def test_thumbnail_copy_is_short_and_uppercase():
    from generate_shorts import _thumbnail_copy
    assert _thumbnail_copy("Why cats really purr at night") == "WHY CATS REALLY PURR"


def test_dynamic_thumbnails_change_with_story(tmp_path: Path):
    from PIL import Image
    from generate_shorts import create_short_thumbnail
    frame = Image.new("RGB", (1080, 1920), (80, 120, 90))
    cats = tmp_path / "cats.jpg"
    birds = tmp_path / "birds.jpg"
    create_short_thumbnail(frame, cats, "WHY CATS PURR", "cats")
    create_short_thumbnail(frame, birds, "OWL NIGHT VISION", "birds")
    assert cats.exists() and birds.exists()
    assert cats.read_bytes() != birds.read_bytes()
