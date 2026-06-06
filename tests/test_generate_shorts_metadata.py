"""Tests for the YouTube Shorts metadata contract."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PIL")


def _story() -> dict:
    return {
        "title": "How lions coordinate during a hunt",
        "category": "wildlife",
        "source": "Pexels",
        "source_url": "https://www.pexels.com/video/xyz",
        "slug": "how-lions-coordinate-during-a-hunt-2026-05-19",
        "yt_description": "AI-authored Short description. More info follows.",
        "yt_tags": ["lion", "wildlife", "savanna"],
        "topic_hashtag": "Wildlife",
        "discovery_hashtags": ["wildlife", "wildanimals", "safari", "funfacts"],
        "experiments": {"hook_style": "outcome_first"},
        "trend_context": {
            "animal": "lion",
            "trend_score": 70,
            "headline": "Rare mountain lion sighting draws attention",
        },
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
        "channel_handle", "seo_score",
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


def test_metadata_preserves_trend_context(tmp_path: Path):
    assert _meta(tmp_path)["trend_context"]["animal"] == "lion"


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


def test_queue_adapter_preserves_trend_context():
    from generate_shorts import _queue_to_story
    story = _queue_to_story({
        "id": "story-trend",
        "trend_context": {"animal": "dog", "trend_score": 88},
    })
    assert story["trend_context"]["animal"] == "dog"


def test_queue_adapter_backfills_new_experiment_axes():
    from generate_shorts import _queue_to_story
    story = _queue_to_story({
        "id": "story-1",
        "seo_title": "Chickens remember faces",
        "category": "farm",
        "experiments": {"hook_style": "outcome_first"},
    })
    assert story["experiments"]["hook_style"] == "outcome_first"
    assert "narrator_voice" in story["experiments"]


def test_queue_adapter_polishes_robotic_story():
    from generate_shorts import _queue_to_story
    story = _queue_to_story({
        "id": "story-robotic",
        "title": "Cats purr for more than happiness",
        "seo_title": "Cats purr for more than happiness",
        "category": "cats",
        "description": "A close video of a cat face and body while it purrs.",
        "hook": "Did you know cats are amazing?",
        "script": "Did you know cats are amazing? Animals have incredible adaptations.",
        "thumbnail_text": "",
    })
    assert story["studio_polish"]["applied"] is True
    assert "I love this detail" in story["script"]


def test_queue_adapter_frontloads_seo_title():
    from generate_shorts import _queue_to_story
    story = _queue_to_story({
        "id": "story-seo",
        "title": "cats playing outside",
        "seo_title": "Why cats play like this — it is not just fun",
        "category": "cats",
        "hook": "Cats play to practice hunting.",
        "script": "Cats play to practice hunting. Watch their paws and tail because each pounce builds timing. That's why play matters.",
        "thumbnail_text": "CATS PLAY TO SURVIVE",
        "yt_tags": ["cats", "play behavior"],
        "source_url": "https://www.pexels.com/video/cats/",
        "score": 9,
    })
    assert story["title"].startswith("Cats ")
    assert story["seo_optimisation"]["score"] >= 80


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
