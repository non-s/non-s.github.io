"""Tests for fetch_animals.py.

Cover the queue-shape contract with generate_shorts.py, the AI JSON
parsing, dedupe, and prune-on-age behaviour. The Pexels and AI
network calls are mocked — no test should hit the real internet.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest

import fetch_animals
from utils.broll import BrollClip


def _clip(url: str = "https://www.pexels.com/video/cat/123/",
          dl: str = "https://files.pexels.com/v/cat-1.mp4",
          title: str = "Cat playing in sunlight") -> BrollClip:
    return BrollClip(
        source="pexels",
        url=url,
        download_url=dl,
        width=1080,
        height=1920,
        duration_s=12.0,
        title=title,
        license="Pexels",
    )


_AI_OK_PAYLOAD = json.dumps({
    "score":          8,
    "seo_title":      "Why cats really purr — it is not just happiness",
    "yt_tags":        ["cats", "cat facts", "purring", "animals", "wildlife"],
    "topic_hashtag":  "Cats",
    "yt_description": "Cats purr for more than joy. They self-soothe and "
                      "even heal their own bones at 25-150 Hz. Source: Pexels",
    "thumbnail_text": "WHY CATS PURR",
    "hook":           "Cats purr to heal their own bones.",
    "script":         "Cats purr to heal their own bones. The 25-150 Hz "
                      "frequency promotes bone density. Big cats can purr "
                      "too — sometimes. What's the strangest thing your "
                      "cat does?",
    "sentiment":      "positive",
})


# ── AI parsing ────────────────────────────────────────────────────

def test_ai_enhance_animal_parses_valid_json(monkeypatch):
    monkeypatch.setattr(fetch_animals, "ai_text", lambda *a, **kw: _AI_OK_PAYLOAD)
    out = fetch_animals._ai_enhance_animal("cat playing", "A clip of cats")
    assert out is not None
    assert out["seo_title"].startswith("Why cats really purr")
    assert out["hook"].startswith("Cats purr")
    assert out["topic_hashtag"] == "Cats"
    assert "#Shorts" in out["yt_description"]
    assert "#Animals" in out["yt_description"]
    assert "#Cats" in out["yt_description"]
    assert out["sentiment"] == "positive"


def test_ai_enhance_returns_none_on_empty_response(monkeypatch):
    monkeypatch.setattr(fetch_animals, "ai_text", lambda *a, **kw: "")
    assert fetch_animals._ai_enhance_animal("cat", "a cat clip") is None


def test_ai_enhance_returns_none_on_unparseable(monkeypatch):
    monkeypatch.setattr(fetch_animals, "ai_text", lambda *a, **kw: "not json {{{")
    assert fetch_animals._ai_enhance_animal("cat", "a cat clip") is None


def test_ai_enhance_strips_code_fences(monkeypatch):
    wrapped = f"```json\n{_AI_OK_PAYLOAD}\n```"
    monkeypatch.setattr(fetch_animals, "ai_text", lambda *a, **kw: wrapped)
    out = fetch_animals._ai_enhance_animal("cat", "a cat clip")
    assert out is not None and out["topic_hashtag"] == "Cats"


def test_ai_enhance_caps_tag_list_to_five(monkeypatch):
    bloat = dict(json.loads(_AI_OK_PAYLOAD))
    bloat["yt_tags"] = ["a", "b", "c", "d", "e", "f", "g", "h"]
    monkeypatch.setattr(fetch_animals, "ai_text", lambda *a, **kw: json.dumps(bloat))
    out = fetch_animals._ai_enhance_animal("cat", "a cat clip")
    assert len(out["yt_tags"]) <= 5


# ── Story builder ─────────────────────────────────────────────────

def test_build_story_shape_matches_news_queue_schema():
    """The downstream generate_shorts.py reads a fixed set of keys;
    pin them here so a future fetch_animals refactor can't silently
    drop one and break the rest of the pipeline."""
    ai_out = json.loads(_AI_OK_PAYLOAD)
    # Reproduce the post-parse normalisation _ai_enhance_animal does.
    ai_out["geo_hashtag"] = "Global"
    ai_out["lead"] = ai_out["script"][:400]
    ai_out["yt_description"] = (
        ai_out["yt_description"] + "\n#Shorts #Animals #Cats"
    )[:500]
    story = fetch_animals._build_story(
        clip_subject="cat playing",
        topic_key="cats",
        topic_cfg=fetch_animals.ANIMAL_TOPICS["cats"],
        pexels_clip=_clip(),
        ai_out=ai_out,
    )
    for required in (
        # Queue identity / state
        "id", "fetched_at", "published_at", "consumed", "consumed_at",
        # Original fields generate_shorts reads as fallbacks
        "title", "url", "source", "category", "description", "image_url",
        # Score chain
        "breaking", "relevance", "score", "safety_penalty", "native_lang",
        # AI-enriched fields generate_shorts reads directly
        "seo_title", "yt_tags", "geo_hashtag", "topic_hashtag",
        "yt_description", "thumbnail_text", "hook", "script", "lead",
        "sentiment",
    ):
        assert required in story, f"missing field: {required}"


def test_build_story_starts_unconsumed():
    ai_out = json.loads(_AI_OK_PAYLOAD)
    ai_out.setdefault("geo_hashtag", "Global")
    ai_out.setdefault("lead", ai_out["script"][:400])
    story = fetch_animals._build_story(
        "cat", "cats",
        fetch_animals.ANIMAL_TOPICS["cats"],
        _clip(), ai_out,
    )
    assert story["consumed"] is False
    assert story["consumed_at"] is None
    assert story["source"] == "Pexels"
    assert story["category"] == "cats"


def test_build_story_id_is_stable():
    """Same clip URL → same id. Used for dedupe across runs."""
    ai_out = json.loads(_AI_OK_PAYLOAD)
    ai_out.setdefault("geo_hashtag", "Global")
    ai_out.setdefault("lead", "")
    a = fetch_animals._build_story("cat", "cats",
                                    fetch_animals.ANIMAL_TOPICS["cats"],
                                    _clip(url="https://x/y/1"), ai_out)
    b = fetch_animals._build_story("cat", "cats",
                                    fetch_animals.ANIMAL_TOPICS["cats"],
                                    _clip(url="https://x/y/1"), ai_out)
    assert a["id"] == b["id"]


def test_build_story_id_differs_per_clip():
    ai_out = json.loads(_AI_OK_PAYLOAD)
    ai_out.setdefault("geo_hashtag", "Global")
    ai_out.setdefault("lead", "")
    a = fetch_animals._build_story("cat", "cats",
                                    fetch_animals.ANIMAL_TOPICS["cats"],
                                    _clip(url="https://x/y/1"), ai_out)
    b = fetch_animals._build_story("cat", "cats",
                                    fetch_animals.ANIMAL_TOPICS["cats"],
                                    _clip(url="https://x/y/2"), ai_out)
    assert a["id"] != b["id"]


# ── Prune ──────────────────────────────────────────────────────────

def test_prune_keeps_unconsumed_regardless_of_age():
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    queue = [
        {"id": "a", "consumed": False, "fetched_at": old},
        {"id": "b", "consumed": False, "fetched_at": old},
    ]
    out = fetch_animals._prune_queue(queue, keep_days=14)
    assert [s["id"] for s in out] == ["a", "b"]


def test_prune_drops_old_consumed():
    long_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    queue = [
        {"id": "old", "consumed": True, "consumed_at": long_ago},
        {"id": "new", "consumed": True, "consumed_at": recent},
        {"id": "pending", "consumed": False},
    ]
    out = fetch_animals._prune_queue(queue, keep_days=14)
    ids = {s["id"] for s in out}
    assert "old" not in ids
    assert "new" in ids
    assert "pending" in ids


# ── Query rotation ────────────────────────────────────────────────

def test_rotate_queries_returns_requested_count():
    queries = ["a", "b", "c", "d", "e"]
    out = fetch_animals._rotate_queries("cats", queries, take=2)
    assert len(out) == 2
    assert set(out).issubset(set(queries))


def test_rotate_queries_empty_input_returns_empty():
    assert fetch_animals._rotate_queries("cats", [], take=2) == []


def test_rotate_queries_is_deterministic_within_window():
    """Same topic + same 3-hour window → same picks."""
    qs = ["a", "b", "c", "d", "e", "f"]
    a = fetch_animals._rotate_queries("cats", qs, take=2)
    b = fetch_animals._rotate_queries("cats", qs, take=2)
    assert a == b


# ── Topic table ───────────────────────────────────────────────────

def test_topic_table_covers_expected_categories():
    """Pivot doc / channel branding refers to these 6 topics; if one
    drops out the channel suddenly stops covering, say, ocean life
    without anyone noticing in code review."""
    expected = {"cats", "dogs", "ocean", "wildlife", "birds", "farm"}
    assert expected.issubset(set(fetch_animals.ANIMAL_TOPICS))


def test_every_topic_has_queries_and_hashtag():
    for key, cfg in fetch_animals.ANIMAL_TOPICS.items():
        assert cfg.get("queries"), f"{key} has no queries"
        assert cfg.get("topic_hashtag"), f"{key} has no topic_hashtag"
        assert cfg.get("tags"), f"{key} has no tags"
