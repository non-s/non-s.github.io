"""Tests for utils/channel_memory.py."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from utils import channel_memory


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    p = tmp_path / "memory.jsonl"
    monkeypatch.setattr(channel_memory, "MEMORY_LOG", p)
    return p


def test_remember_appends_jsonl(isolated):
    channel_memory.remember({
        "id":          "story-abc",
        "slug":        "story-abc",
        "title":       "Octopus changes colour",
        "seo_title":   "Octopus changes colour in seconds",
        "hook":        "This octopus changes colour in seconds.",
        "category":    "ocean",
        "geo_hashtag": "Ocean",
        "topic_hashtag": "Octopus",
        "source":      "Pexels",
        "yt_tags":     ["octopus", "cephalopod", "camouflage", "animal facts"],
    })
    entries = isolated.read_text(encoding="utf-8").strip().split("\n")
    assert len(entries) == 1
    e = json.loads(entries[0])
    assert e["slug"] == "story-abc"
    assert e["title"] == "Octopus changes colour in seconds"
    assert e["entities"] == ["octopus", "cephalopod", "camouflage"]   # first 3 only


def test_remember_skips_when_no_slug(isolated):
    channel_memory.remember({"title": "no slug here"})
    assert not isolated.exists() or isolated.read_text() == ""


def test_find_callback_candidates_returns_empty_without_memory(isolated):
    out = channel_memory.find_callback_candidates({"slug": "x"})
    assert out == []


def test_find_callback_candidates_matches_on_entities(isolated):
    # Past: an octopus-camouflage story.
    channel_memory.remember({
        "slug": "past-1", "id": "past-1",
        "title": "Octopus shifts colour",
        "hook": "This octopus changes its skin pattern.",
        "yt_tags": ["octopus", "camouflage", "cephalopod", "x", "y"],
        "geo_hashtag": "Ocean",
        "topic_hashtag": "Octopus",
    })
    # New: shares entities with the past one.
    new_story = {
        "slug": "new-1",
        "seo_title": "Octopus camouflage happens in seconds",
        "hook": "This octopus just disappeared against the reef.",
        "yt_tags": ["octopus", "camouflage", "cephalopod"],
        "geo_hashtag": "Ocean",
        "topic_hashtag": "Octopus",
    }
    candidates = channel_memory.find_callback_candidates(new_story)
    assert candidates
    assert candidates[0]["slug"] == "past-1"


def test_find_callback_candidates_skips_unrelated(isolated):
    channel_memory.remember({
        "slug": "past-1", "id": "past-1",
        "title": "Octopus changes colour",
        "hook": "This octopus shifts colour in seconds.",
        "yt_tags": ["octopus", "camouflage", "cephalopod"],
        "geo_hashtag": "Ocean",
        "topic_hashtag": "Octopus",
    })
    new_story = {
        "slug": "new-1",
        "seo_title": "Owls rotate their heads farther than humans",
        "hook": "This owl turns its head almost all the way around.",
        "yt_tags": ["owl", "bird", "neck"],
        "geo_hashtag": "Forest",
        "topic_hashtag": "Birds",
    }
    assert channel_memory.find_callback_candidates(new_story) == []


def test_find_callback_candidates_skips_self(isolated):
    channel_memory.remember({
        "slug": "x", "id": "x",
        "title": "Same story",
        "yt_tags": ["a", "b", "c"],
    })
    # Same slug → must be skipped.
    out = channel_memory.find_callback_candidates({
        "slug": "x", "yt_tags": ["a", "b", "c"],
    })
    assert out == []


def test_find_callback_candidates_caps_at_max(isolated):
    for i in range(5):
        channel_memory.remember({
            "slug": f"p-{i}", "id": f"p-{i}",
            "title": "Octopus camouflage",
            "hook": "Octopus changed colour.",
            "yt_tags": ["octopus", "camouflage", "cephalopod"],
        })
    new_story = {
        "slug": "n",
        "seo_title": "Octopus camouflage detail",
        "hook": "Octopus changes colour again.",
        "yt_tags": ["octopus", "camouflage", "cephalopod"],
    }
    out = channel_memory.find_callback_candidates(new_story, max_candidates=2)
    assert len(out) == 2


def test_callback_prompt_block_empty_for_no_candidates():
    assert channel_memory.callback_prompt_block([]) == ""


def test_callback_prompt_block_renders_candidates():
    cands = [
        {"iso": "2026-05-10T00:00:00+00:00", "hook": "Past hook 1"},
        {"iso": "2026-05-12T00:00:00+00:00", "hook": "Past hook 2"},
    ]
    block = channel_memory.callback_prompt_block(cands)
    assert "Past hook 1" in block
    assert "Past hook 2" in block
    assert "callback" in block.lower()


def test_lookback_window_excludes_old_entries(isolated, monkeypatch):
    # Forge an old entry directly.
    old = time.time() - 90 * 86400
    isolated.write_text(
        json.dumps({"ts": old, "slug": "ancient", "title": "old",
                     "hook": "Old.", "entities": ["fed", "powell"]}) + "\n",
        encoding="utf-8",
    )
    out = channel_memory.find_callback_candidates({
        "slug": "n", "yt_tags": ["fed", "powell"],
    }, days=30)
    # Outside the 30-day window.
    assert out == []


def test_angle_key_is_stable_for_same_subject_angle():
    a = {"topic_hashtag": "Cats", "title": "Why cats purr to heal bones"}
    b = {"topic_hashtag": "Cats", "seo_title": "Cats purr to heal faster"}
    assert channel_memory.angle_key(a).startswith("cats-")
    assert "purr" in channel_memory.angle_key(a)
    assert channel_memory.angle_key(a).split("-")[:2] == channel_memory.angle_key(b).split("-")[:2]


def test_recent_angle_repeat_detects_same_angle(tmp_path):
    story = {
        "slug": "new",
        "topic_hashtag": "Cats",
        "title": "Why cats purr to heal bones",
    }
    past = {
        "ts": time.time(),
        "slug": "old",
        "angle_key": channel_memory.angle_key(story),
    }
    path = tmp_path / "memory.jsonl"
    path.write_text(json.dumps(past) + "\n", encoding="utf-8")
    assert channel_memory.recent_angle_repeat(story, path=path)
