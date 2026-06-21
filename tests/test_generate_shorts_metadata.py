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
        "agency": {
            "score": 84,
            "decision": "publish_now",
            "strengths": ["strong_quality", "timely_trend"],
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
        "title",
        "description",
        "tags",
        "youtube_privacy",
        "youtube_category_id",
        "thumbnail",
        "video",
        "is_short",
        "channel_handle",
        "seo_score",
    ):
        assert required in meta, f"missing required field: {required}"


def test_metadata_caption_uses_youtube_shorts_hashtags(tmp_path: Path):
    desc = _meta(tmp_path)["description"]
    assert "#Shorts" in desc
    assert "#NatureFacts" in desc
    assert "#WildBrief" in desc
    assert "#EarthScience" in desc
    assert "#Nature" in desc


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
    assert "#NatureFacts" in meta["description"]


def test_metadata_preserves_experiments(tmp_path: Path):
    assert _meta(tmp_path)["experiments"] == {"hook_style": "outcome_first"}


def test_loop_line_and_end_card_use_experiment_axes():
    from generate_shorts import _end_card_text_for_story, _loop_enhanced_script

    story = {
        "experiments": {"cta_pattern": "sequel_tease", "end_card_style": "loop_callback"},
        "packaging": {
            "loop_plan": {"final_line": "Now the wing at the start makes sense.", "callback_keyword": "wing"}
        },
    }
    script = _loop_enhanced_script(story, "Ducks fake injuries to protect young.")

    assert script.endswith("Now the wing at the start makes sense.")
    assert _end_card_text_for_story(story) == "WATCH THE WING AGAIN"


def test_metadata_preserves_trend_context(tmp_path: Path):
    assert _meta(tmp_path)["trend_context"]["animal"] == "lion"


def test_metadata_preserves_agency_decision(tmp_path: Path):
    assert _meta(tmp_path)["agency"]["decision"] == "publish_now"


def test_metadata_includes_global_audience_strategy(tmp_path: Path):
    meta = _meta(tmp_path)
    assert meta["audience_strategy"]["mode"] == "global"
    assert len(meta["audience_strategy"]["publish_windows"]) == 24


def test_metadata_includes_youtube_brain(tmp_path: Path):
    from generate_shorts import _queue_to_story, build_short_metadata

    story = _queue_to_story(
        {
            "id": "brain-story",
            "seo_title": "Ducks fake injuries to protect young",
            "title": "Ducks fake injuries to protect young",
            "hook": "Ducks fake injuries to protect their young.",
            "script": (
                "Ducks fake injuries to protect their young. Watch the wing movement first, "
                "because that cue pulls predators away from the nest. The duck escapes after "
                "the chicks have cover."
            ),
            "thumbnail_text": "WATCH THE WING",
            "category": "birds",
        }
    )
    meta = build_short_metadata(story, tmp_path / "short.mp4", tmp_path / "thumb.jpg")
    assert meta["youtube_brain"]["viewer_promise"]


def test_metadata_includes_packaging_and_pinned_comment(tmp_path: Path):
    from generate_shorts import _queue_to_story, build_short_metadata

    story = _queue_to_story(
        {
            "id": "package-story",
            "seo_title": "Ducks fake injuries to protect young",
            "title": "Ducks fake injuries to protect young",
            "hook": "Ducks fake injuries to protect their young.",
            "script": (
                "Ducks fake injuries to protect their young. Watch the wing movement first, "
                "because that cue pulls predators away from the nest."
            ),
            "thumbnail_text": "WATCH THE WING",
            "category": "birds",
        }
    )
    meta = build_short_metadata(story, tmp_path / "short.mp4", tmp_path / "thumb.jpg")
    assert meta["packaging"]["pinned_comment"]
    assert meta["pinned_comment"] == meta["packaging"]["pinned_comment"]


def test_metadata_keeps_earth_from_space_out_of_animal_lane(tmp_path: Path):
    from generate_shorts import _queue_to_story, build_short_metadata

    story = _queue_to_story(
        {
            "id": "storm-story",
            "seo_title": "Storm clouds filter sunlight into a softer glow",
            "title": "Storm clouds filter sunlight into a softer glow",
            "hook": "Storm clouds spread sunlight before it reaches the ground.",
            "script": (
                "Storm clouds spread sunlight before it reaches the ground. Watch the flat light, "
                "because thick cloud layers scatter direct sun in many directions. Which light clue "
                "should we compare next?"
            ),
            "thumbnail_text": "SOFT LIGHT",
            "category": "earth_from_space",
            "series": "Animal Superpowers #16",
            "story_format": "animal_intelligence",
            "yt_tags": ["earth_from_space", "clouds", "atmosphere"],
        }
    )
    meta = build_short_metadata(story, tmp_path / "short.mp4", tmp_path / "thumb.jpg")

    assert meta["story_format"] == "earth_engine"
    assert meta["series"].startswith("Earth Engine") or meta["series"].startswith("Planet Earth")
    assert "animal signal" not in meta["cta_prompt"].lower()
    assert "another nature signal" in meta["pinned_comment"].lower()


def test_metadata_includes_retention_surgery(tmp_path: Path):
    surgery = _meta(tmp_path)["retention_surgery"]
    assert "score" in surgery
    assert "verdict" in surgery


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
        "cats",
        "dogs",
        "birds",
        "cats",
    ]


def test_mark_rejected_consumes_blocked_candidate():
    from generate_shorts import mark_rejected

    queue = {"stories": [{"id": "blocked", "title": "Blocked story"}]}

    mark_rejected(queue, "blocked", ["cooldown_subject", "low_editorial_score"], stage="editor_in_chief")

    story = queue["stories"][0]
    assert story["consumed"] is True
    assert story["rejection_stage"] == "editor_in_chief"
    assert story["rejection_reasons"] == ["cooldown_subject", "low_editorial_score"]
    assert story["rejected_at"]


def test_queue_adapter_preserves_original_pexels_clip():
    from generate_shorts import _queue_to_story

    story = _queue_to_story(
        {
            "id": "story-1",
            "pexels_download_url": "https://files.pexels.com/video.mp4",
        }
    )
    assert story["pexels_download_url"] == "https://files.pexels.com/video.mp4"


def test_queue_adapter_preserves_trend_context():
    from generate_shorts import _queue_to_story

    story = _queue_to_story(
        {
            "id": "story-trend",
            "trend_context": {"animal": "dog", "trend_score": 88},
        }
    )
    assert story["trend_context"]["animal"] == "dog"


def test_queue_adapter_backfills_new_experiment_axes():
    from generate_shorts import _queue_to_story

    story = _queue_to_story(
        {
            "id": "story-1",
            "seo_title": "Chickens remember faces",
            "category": "farm",
            "experiments": {"hook_style": "outcome_first"},
        }
    )
    assert story["experiments"]["hook_style"] == "outcome_first"
    assert "narrator_voice" in story["experiments"]


def test_queue_adapter_polishes_robotic_story():
    from generate_shorts import _queue_to_story

    story = _queue_to_story(
        {
            "id": "story-robotic",
            "title": "Cats purr for more than happiness",
            "seo_title": "Cats purr for more than happiness",
            "category": "cats",
            "description": "A close video of a cat face and body while it purrs.",
            "hook": "Did you know cats are amazing?",
            "script": "Did you know cats are amazing? Animals have incredible adaptations.",
            "thumbnail_text": "",
        }
    )
    assert story["studio_polish"]["applied"] is True
    assert "I love this detail" in story["script"]


def test_queue_adapter_frontloads_seo_title():
    from generate_shorts import _queue_to_story

    story = _queue_to_story(
        {
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
        }
    )
    assert story["title"].startswith("Cats ")
    assert story["seo_optimisation"]["score"] >= 80


def test_thumbnail_copy_is_short_and_uppercase():
    from generate_shorts import _clean_thumbnail_text, _thumbnail_copy

    assert _thumbnail_copy("Why cats really purr at night") == "CATS PURR NIGHT"
    assert _clean_thumbnail_text("Chickens head movement") == "HEAD TILT"
    assert _clean_thumbnail_text("Butterflies rely on wing movement to trick") == "WING FLASH"


def test_dynamic_thumbnails_change_with_story(tmp_path: Path):
    from PIL import Image, ImageStat

    from generate_shorts import create_short_thumbnail

    frame = Image.new("RGB", (1080, 1920), (80, 120, 90))
    cats = tmp_path / "cats.jpg"
    birds = tmp_path / "birds.jpg"
    create_short_thumbnail(frame, cats, "WHY CATS PURR", "cats")
    create_short_thumbnail(frame, birds, "OWL NIGHT VISION", "birds")
    assert cats.exists() and birds.exists()
    assert cats.read_bytes() != birds.read_bytes()
    assert sum(ImageStat.Stat(Image.open(cats).convert("L")).mean) / 1 > 55


def test_load_pending_stories_uses_pruned_publish_ready_queue(monkeypatch, tmp_path):
    import importlib
    import json
    import sys

    if "generate_shorts" in sys.modules:
        del sys.modules["generate_shorts"]
    monkeypatch.chdir(tmp_path)
    import generate_shorts as gs

    importlib.reload(gs)

    data_dir = tmp_path / "_data"
    data_dir.mkdir()
    original = {"stories": [{"id": "unchecked", "title": "Unchecked", "consumed": False}]}
    pruned = {
        "stories": [
            {
                "id": "ready",
                "title": "Ready story",
                "seo_title": "Ready story",
                "consumed": False,
                "queue_prune": {"state": "publish_ready"},
            },
            {
                "id": "rewrite",
                "title": "Rewrite story",
                "seo_title": "Rewrite story",
                "consumed": False,
                "queue_prune": {"state": "rewrite"},
            },
        ]
    }
    (data_dir / "stories_queue.json").write_text(json.dumps(original), encoding="utf-8")

    monkeypatch.setattr(
        gs,
        "prune_queue",
        lambda queue, analytics_strategy=None: (
            pruned,
            [],
            {
                "pending_before": 1,
                "pending_after": 2,
                "rejected": 0,
            },
        ),
    )
    monkeypatch.setattr(gs, "load_strategy", lambda: {})
    monkeypatch.setattr(gs, "_queue_story_quality_issues", lambda story, seen_scripts: [])
    monkeypatch.setattr(gs, "_queue_to_story", lambda story: {"slug": story["id"], **story})
    monkeypatch.setattr(gs, "score_topic", lambda story, memory=None: {"verdict": "keep"})
    monkeypatch.setattr(gs, "detect_weak_content", lambda story, memory=None: {"state": "clear"})
    monkeypatch.setattr(gs, "analyze_retention", lambda story: {"verdict": "keep"})
    monkeypatch.setattr(
        gs,
        "publish_score_story",
        lambda story, analytics_strategy=None: {
            "state": "publish_ready",
            "approved": True,
            "score": 90,
        },
    )
    monkeypatch.setattr(gs, "package_story", lambda story: story)
    monkeypatch.setattr(gs, "creator_premortem", lambda story: {"state": "publish_minded", "risks": []})
    monkeypatch.setattr(gs, "load_format_memory", lambda: {})
    monkeypatch.setattr(gs, "filter_candidates", lambda candidates: (candidates, []))
    monkeypatch.setattr(gs, "rank_candidates", lambda candidates: candidates)
    monkeypatch.setattr(gs, "rank_for_growth", lambda candidates, strategy: candidates)
    monkeypatch.setattr(gs, "rank_for_agency", lambda candidates, strategy: candidates)

    candidates, queue = gs.load_pending_stories()

    assert [item["id"] for item in candidates] == ["ready"]
    assert queue == pruned
    saved = json.loads((data_dir / "stories_queue.json").read_text(encoding="utf-8"))
    assert saved == pruned


def test_queue_adapter_preserves_editorial_cooldown_supply_fallback(monkeypatch):
    import generate_shorts as gs

    monkeypatch.setattr(gs, "package_story", lambda story: story)
    monkeypatch.setattr(
        gs,
        "studio_brief_for_story",
        lambda story: {
            "narrator": {},
            "narrative_template": {},
            "production_mode": "short",
        },
    )
    monkeypatch.setattr(gs, "creator_premortem", lambda story: {"state": "publish_minded", "risks": []})
    monkeypatch.setattr(gs, "optimise_story", lambda story: story)
    monkeypatch.setattr(gs, "polish_story", lambda story: story)

    story = gs._queue_to_story(
        {
            "id": "fallback",
            "seo_title": "Snakes sample the air with a tongue flick",
            "title": "Snakes sample the air with a tongue flick",
            "hook": "Snakes sample the air with a tongue flick.",
            "script": "Snakes sample the air with a tongue flick. Watch the tongue before the next move.",
            "thumbnail_text": "TONGUE FLICK",
            "category": "reptiles",
            "queue_prune": {
                "state": "publish_ready",
                "objective_reasons": ["editorial_cooldown_supply_fallback"],
            },
            "editorial": {
                "approved": True,
                "state": "publish_now",
                "override": "editorial_cooldown_supply_fallback",
            },
            "rights_audit": {"approved": True, "warnings": []},
            "publish_score": {"approved": True, "state": "publish_ready", "score": 100},
        }
    )

    assert gs._has_editorial_cooldown_supply_fallback(story) is True
    assert story["queue_prune"]["state"] == "publish_ready"
    assert story["editorial"]["override"] == "editorial_cooldown_supply_fallback"
    assert story["rights_audit"]["approved"] is True


def test_load_pending_stories_keeps_publish_priority_after_agency_ranking(monkeypatch, tmp_path):
    import importlib
    import json
    import sys

    if "generate_shorts" in sys.modules:
        del sys.modules["generate_shorts"]
    monkeypatch.chdir(tmp_path)
    import generate_shorts as gs

    importlib.reload(gs)

    data_dir = tmp_path / "_data"
    data_dir.mkdir()
    queue = {
        "stories": [
            {
                "id": "low-priority",
                "title": "Low priority",
                "seo_title": "Low priority",
                "consumed": False,
                "queue_prune": {"state": "publish_ready", "score": 99},
                "autonomy": {"priority": 10},
            },
            {
                "id": "high-priority",
                "title": "High priority",
                "seo_title": "High priority",
                "consumed": False,
                "queue_prune": {"state": "publish_ready", "score": 70},
                "autonomy": {"priority": 130},
            },
        ]
    }
    (data_dir / "stories_queue.json").write_text(json.dumps(queue), encoding="utf-8")

    monkeypatch.setattr(
        gs,
        "prune_queue",
        lambda queue, analytics_strategy=None: (
            queue,
            [],
            {
                "pending_before": 2,
                "pending_after": 2,
                "rejected": 0,
            },
        ),
    )
    monkeypatch.setattr(gs, "load_strategy", lambda: {})
    monkeypatch.setattr(gs, "_queue_story_quality_issues", lambda story, seen_scripts: [])
    monkeypatch.setattr(gs, "_queue_to_story", lambda story: {"slug": story["id"], **story})
    monkeypatch.setattr(gs, "score_topic", lambda story, memory=None: {"verdict": "keep"})
    monkeypatch.setattr(gs, "detect_weak_content", lambda story, memory=None: {"state": "clear"})
    monkeypatch.setattr(gs, "analyze_retention", lambda story: {"verdict": "keep"})
    monkeypatch.setattr(
        gs,
        "publish_score_story",
        lambda story, analytics_strategy=None: {
            "state": "publish_ready",
            "approved": True,
            "score": 90,
        },
    )
    monkeypatch.setattr(gs, "package_story", lambda story: story)
    monkeypatch.setattr(gs, "creator_premortem", lambda story: {"state": "publish_minded", "risks": []})
    monkeypatch.setattr(gs, "load_format_memory", lambda: {})
    monkeypatch.setattr(gs, "filter_candidates", lambda candidates: (candidates, []))
    monkeypatch.setattr(gs, "rank_candidates", lambda candidates: candidates)
    monkeypatch.setattr(gs, "rank_for_growth", lambda candidates, strategy: candidates)
    monkeypatch.setattr(gs, "rank_for_agency", lambda candidates, strategy: list(reversed(candidates)))

    candidates, _queue = gs.load_pending_stories()

    assert [item["id"] for item in candidates] == ["high-priority", "low-priority"]
