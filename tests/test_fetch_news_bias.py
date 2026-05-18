"""Tests for the trending-keyword + analytics-bias scoring in fetch_news.py."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

# fetch_news.py pulls in feedparser at import time. The CI runner has
# it installed; bare sandboxes may not. Skip the module's tests cleanly
# in that case so the rest of the suite still runs.
pytest.importorskip("feedparser")


@pytest.fixture
def restore_cwd(tmp_path, monkeypatch):
    """Run each test in a fresh tmp dir so file I/O is isolated."""
    monkeypatch.chdir(tmp_path)
    yield tmp_path


def test_perf_bias_boosts_high_retention():
    from fetch_news import _perf_bias
    perf = {"world": 75.0, "ai": 25.0, "business": 50.0}
    assert _perf_bias("world", perf) == 1
    assert _perf_bias("ai", perf) == -1
    assert _perf_bias("business", perf) == 0
    assert _perf_bias("unknown-category", perf) == 0
    assert _perf_bias("WORLD", perf) == 1  # case-insensitive


def test_load_category_perf_handles_missing_file(restore_cwd):
    """No analytics file → empty dict, no exceptions."""
    import importlib
    import fetch_news
    importlib.reload(fetch_news)
    perf = fetch_news._load_category_perf()
    assert perf == {}


def test_load_category_perf_reads_latest_json(restore_cwd):
    import importlib
    import fetch_news
    importlib.reload(fetch_news)

    analytics_dir = Path("_data/analytics")
    analytics_dir.mkdir(parents=True)
    (analytics_dir / "latest.json").write_text(json.dumps({
        "pulled_at": "2026-05-18",
        "avg_view_pct": 55.0,
        "category_avg_view_pct": {"world": 72.0, "ai": 28.0},
    }))
    perf = fetch_news._load_category_perf()
    assert perf == {"world": 72.0, "ai": 28.0}


def test_load_category_perf_handles_malformed_json(restore_cwd):
    import importlib
    import fetch_news
    importlib.reload(fetch_news)

    analytics_dir = Path("_data/analytics")
    analytics_dir.mkdir(parents=True)
    (analytics_dir / "latest.json").write_text("{not: json")
    assert fetch_news._load_category_perf() == {}


def test_enrich_story_applies_trending_boost(restore_cwd):
    """Story whose title overlaps a trending term gets a score bump."""
    import importlib
    import fetch_news
    importlib.reload(fetch_news)

    base_story = {
        "id": "abc123",
        "title": "Jerome Powell announces rate decision today",
        "description": "x" * 200,
        "source": "Test",
        "category": "business",
    }
    # AI returns a score of 5 — below the default threshold of 6. With
    # a trending hit, the bias should bump it over the threshold.
    with patch.object(fetch_news, "_ai_enhance", return_value={
        "score": 5, "seo_title": "Powell speaks", "yt_tags": ["powell"],
        "geo_hashtag": "USA", "topic_hashtag": "Markets",
        "yt_description": "powell speaks", "thumbnail_text": "NEW RATE",
        "hook": "Powell speaks.", "script": "...", "lead": "...",
        "key_points": ["a", "b", "c"], "sentiment": "neutral",
    }):
        result = fetch_news._enrich_story(
            dict(base_story),
            trending={"powell", "jerome powell", "rate"},
            perf={},
        )
    assert result is not None
    # 5 raw + 2 (two trending hits) = 7
    assert result["score"] >= 6


def test_enrich_story_drops_below_threshold_without_bias(restore_cwd):
    import importlib
    import fetch_news
    importlib.reload(fetch_news)

    base_story = {
        "id": "abc",
        "title": "Plain headline",
        "description": "x" * 200,
        "source": "Test",
        "category": "business",
    }
    with patch.object(fetch_news, "_ai_enhance", return_value={
        "score": 5, "seo_title": "x", "yt_tags": [],
        "geo_hashtag": "G", "topic_hashtag": "T",
        "yt_description": "y", "thumbnail_text": "z",
        "hook": "h", "script": "s", "lead": "l",
        "key_points": [], "sentiment": "neutral",
    }):
        result = fetch_news._enrich_story(dict(base_story), trending=None, perf=None)
    assert result is None


def test_enrich_story_negative_perf_pushes_below_threshold(restore_cwd):
    import importlib
    import fetch_news
    importlib.reload(fetch_news)

    base_story = {
        "id": "abc",
        "title": "Borderline interesting story",
        "description": "x" * 200,
        "source": "Test",
        "category": "ai",
    }
    # Score 6 (at threshold) — minus 1 perf bias → 5 → dropped.
    with patch.object(fetch_news, "_ai_enhance", return_value={
        "score": 6, "seo_title": "x", "yt_tags": [],
        "geo_hashtag": "G", "topic_hashtag": "T",
        "yt_description": "y", "thumbnail_text": "z",
        "hook": "h", "script": "s", "lead": "l",
        "key_points": [], "sentiment": "neutral",
    }):
        result = fetch_news._enrich_story(
            dict(base_story),
            trending=None,
            perf={"ai": 20.0},  # historically underperforms
        )
    assert result is None


def test_public_item_to_entry_round_trips_fields():
    """The synthetic feedparser-shaped object should carry the original metadata."""
    from datetime import datetime, timezone
    import fetch_news

    item = {
        "title":       "Major event",
        "link":        "https://e.test/a",
        "description": "Multi-paragraph context that's longer than 60 chars and clear.",
        "image":       "https://e.test/img.jpg",
        "published":   datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc),
        "source":      "Reddit r/worldnews",
        "category":    "world",
        "tags":        ["reddit"],
    }
    entry = fetch_news._public_item_to_entry(item)
    assert entry.title == "Major event"
    assert entry.link == "https://e.test/a"
    assert entry.media_thumbnail[0]["url"] == "https://e.test/img.jpg"
    assert entry.published_parsed is not None


def test_prune_dead_health_drops_orphan_feeds():
    """Health entries for feeds no longer in FEEDS should be removed."""
    import fetch_news
    health = {
        "BBC World":     2,
        "Old Defunct":   5,
        "Another Gone":  3,
        "TechCrunch":    0,
    }
    active = {"BBC World", "TechCrunch", "NewFeed"}
    fetch_news._prune_dead_health(health, active)
    assert health == {"BBC World": 2, "TechCrunch": 0}


def test_prune_dead_health_empty_inputs():
    import fetch_news
    h = {}
    fetch_news._prune_dead_health(h, {"AnyFeed"})
    assert h == {}
    h = {"x": 1}
    fetch_news._prune_dead_health(h, set())
    assert h == {}
