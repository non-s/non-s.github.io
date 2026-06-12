"""Tests for global audience expansion helpers."""

from __future__ import annotations

from utils.audience_expansion import global_strategy, merge_hashtags, merge_search_tags


def test_merge_hashtags_keeps_global_discovery_first():
    tags = merge_hashtags(["wildlife", "safari", "animalfacts"])

    assert tags[:5] == ["Shorts", "NatureFacts", "WildBrief", "EarthScience", "Nature"]
    assert len(tags) == len(set(tag.lower() for tag in tags))


def test_merge_search_tags_blends_subject_and_global_terms():
    tags = merge_search_tags(["lion", "wildlife"], "wildlife")

    assert tags[:2] == ["lion", "wildlife"]
    assert "earth science" in tags
    assert "natural phenomena" in tags
    assert len(tags) <= 15


def test_global_strategy_covers_major_regions():
    strategy = global_strategy()

    assert strategy["mode"] == "global"
    assert [item["utc_hour"] for item in strategy["publish_windows"]] == list(range(24))
