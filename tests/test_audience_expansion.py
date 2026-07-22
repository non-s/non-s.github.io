"""Tests for global audience expansion helpers."""

from __future__ import annotations

from utils.audience_expansion import global_strategy, merge_hashtags, merge_search_tags


def test_merge_hashtags_keeps_global_discovery_first():
    tags = merge_hashtags(["rain", "thunder", "sleepsounds"])

    assert tags[:5] == ["Shorts", "RainSounds", "SleepSounds", "Ambience", "Nature"]
    assert len(tags) == len(set(tag.lower() for tag in tags))


def test_merge_search_tags_blends_subject_and_global_terms():
    tags = merge_search_tags(["rain", "thunder"], "storm")

    assert tags[:2] == ["rain", "thunder"]
    assert "rain sounds" in tags
    assert "sleep sounds" in tags
    assert len(tags) <= 15


def test_global_strategy_covers_major_regions():
    strategy = global_strategy()

    assert strategy["mode"] == "global"
    # Every-2-hours Shorts cadence (12 slots/day, deliberately sparse --
    # see GLOBAL_PUBLISH_WINDOWS's docstring): even hours only, but every
    # region bucket _region_for_hour() can return must still get at least
    # one slot, in ascending order.
    windows = strategy["publish_windows"]
    hours = [item["utc_hour"] for item in windows]
    assert hours == sorted(hours)
    assert hours == list(range(0, 24, 2))
    labels = {item["label"] for item in windows}
    assert labels == {
        "Americas evening and late scroll",
        "Asia/Oceania evening",
        "Europe/Africa daytime",
        "Americas daytime",
    }
