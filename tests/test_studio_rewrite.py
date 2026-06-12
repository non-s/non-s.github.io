"""Tests for controlled AI rewrite rescue."""

from __future__ import annotations

import json

from utils import studio_rewrite


def _needs_rewrite_story() -> dict:
    return {
        "id": "rewrite-1",
        "title": "Octopus camouflage changes in seconds",
        "description": "A clip of an octopus underwater near coral and rocks.",
        "hook": "This octopus changes colour.",
        "script": (
            "This octopus changes colour. Watch the eyes and skin because "
            "the texture shifts before the disguise works. That's why it "
            "can hide near coral and rocks. Which ocean animal should we decode next?"
        ),
        "thumbnail_text": "TOO MANY WORDS HERE",
        "yt_tags": ["octopus", "camouflage"],
        "category": "ocean",
        "score": 7,
        "source_url": "https://www.pexels.com/video/octopus-123/",
    }


def test_ai_rewrite_accepts_better_script(monkeypatch):
    monkeypatch.setattr(studio_rewrite, "ENABLED", True)
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(
        studio_rewrite,
        "ai_text",
        lambda *a, **k: json.dumps(
            {
                "hook": "This octopus disappears against coral.",
                "script": (
                    "This octopus disappears against coral. I love this detail: "
                    "watch the skin and tiny muscles. Because they change colour "
                    "and texture together, the body stops looking like an animal. "
                    "That's why predators can swim past it. Which ocean animal "
                    "should we decode next?"
                ),
                "thumbnail_text": "OCTOPUS VANISHES",
            }
        ),
    )
    out = studio_rewrite.rewrite_if_needed(_needs_rewrite_story())
    assert out["ai_rewrite"]["accepted"] is True
    assert out["studio_state"] in {"publish_now", "polished"}
    assert out["editorial"]["approved"] is True


def test_ai_rewrite_rejects_invalid_json(monkeypatch):
    monkeypatch.setattr(studio_rewrite, "ENABLED", True)
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.setattr(studio_rewrite, "ai_text", lambda *a, **k: "not json")
    out = studio_rewrite.rewrite_if_needed(_needs_rewrite_story())
    assert out["ai_rewrite"]["attempted"] is True
    assert out["ai_rewrite"]["accepted"] is False


def test_ai_rewrite_skips_without_ai_key(monkeypatch):
    monkeypatch.setattr(studio_rewrite, "ENABLED", True)
    for key in studio_rewrite._AI_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(studio_rewrite, "ai_text", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ai called")))
    out = studio_rewrite.rewrite_if_needed(_needs_rewrite_story())
    assert out == _needs_rewrite_story()
