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
        "title":       "Fed cuts rates",
        "seo_title":   "Fed cuts rates today",
        "hook":        "The Fed just cut rates.",
        "category":    "business",
        "geo_hashtag": "USA",
        "topic_hashtag": "Markets",
        "source":      "Reuters",
        "yt_tags":     ["fed", "powell", "rates", "world news"],
    })
    entries = isolated.read_text(encoding="utf-8").strip().split("\n")
    assert len(entries) == 1
    e = json.loads(entries[0])
    assert e["slug"] == "story-abc"
    assert e["title"] == "Fed cuts rates today"
    assert e["entities"] == ["fed", "powell", "rates"]   # first 3 only


def test_remember_skips_when_no_slug(isolated):
    channel_memory.remember({"title": "no slug here"})
    assert not isolated.exists() or isolated.read_text() == ""


def test_find_callback_candidates_returns_empty_without_memory(isolated):
    out = channel_memory.find_callback_candidates({"slug": "x"})
    assert out == []


def test_find_callback_candidates_matches_on_entities(isolated):
    # Past: a Fed-Powell story.
    channel_memory.remember({
        "slug": "past-1", "id": "past-1",
        "title": "Fed signals rate cut",
        "hook": "Powell hinted at cutting rates.",
        "yt_tags": ["fed", "powell", "rates", "x", "y"],
        "geo_hashtag": "USA",
        "topic_hashtag": "Markets",
    })
    # New: shares entities with the past one.
    new_story = {
        "slug": "new-1",
        "seo_title": "Fed actually cuts rates today",
        "hook": "Powell did it — 50 bps cut.",
        "yt_tags": ["fed", "powell", "rates"],
        "geo_hashtag": "USA",
        "topic_hashtag": "Markets",
    }
    candidates = channel_memory.find_callback_candidates(new_story)
    assert candidates
    assert candidates[0]["slug"] == "past-1"


def test_find_callback_candidates_skips_unrelated(isolated):
    channel_memory.remember({
        "slug": "past-1", "id": "past-1",
        "title": "Apple unveils iPhone",
        "hook": "Apple shipped the new iPhone.",
        "yt_tags": ["apple", "iphone", "tech"],
        "geo_hashtag": "USA",
        "topic_hashtag": "Tech",
    })
    new_story = {
        "slug": "new-1",
        "seo_title": "Ukraine peace talks resume",
        "hook": "Zelensky agrees to ceasefire.",
        "yt_tags": ["ukraine", "russia", "ceasefire"],
        "geo_hashtag": "Ukraine",
        "topic_hashtag": "Conflict",
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
            "title": "Powell rate decision",
            "hook": "Fed cut rates.",
            "yt_tags": ["fed", "powell", "rates"],
        })
    new_story = {
        "slug": "n",
        "seo_title": "Fed news",
        "hook": "Powell again on rates.",
        "yt_tags": ["fed", "powell", "rates"],
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
