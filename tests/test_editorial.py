"""Tests for the automated Wild Brief editor-in-chief."""
from __future__ import annotations

from utils import editorial


def _story() -> dict:
    return {
        "title": "Octopus camouflage changes in seconds",
        "description": "A clip of an octopus underwater.",
        "hook": "This octopus changes colour in seconds.",
        "script": (
            "This octopus changes colour in seconds. Special skin cells shift "
            "colour while tiny muscles reshape its texture. It can match coral, "
            "rocks, and sand even while moving. That makes the disguise useful "
            "for both hunting and hiding. Which animal power should we explain next?"
        ),
        "thumbnail_text": "OCTOPUS VANISHES",
        "yt_tags": ["octopus", "camouflage", "cephalopod"],
        "category": "ocean",
        "score": 9,
        "source_url": "https://www.pexels.com/video/octopus-123/",
    }


def test_editor_approves_specific_non_repeated_story(monkeypatch):
    monkeypatch.setattr(editorial.channel_memory, "_iter_recent", lambda days: iter(()))
    out = editorial.review(_story())
    assert out.approved
    assert out.score >= editorial.MIN_EDITORIAL_SCORE
    assert out.subject == "octopus"
    assert out.series == "Ocean Mysteries"
    assert out.humanity["score"] >= 58


def test_editor_blocks_recent_subject_repeat(monkeypatch):
    monkeypatch.setattr(
        editorial.channel_memory,
        "_iter_recent",
        lambda days: iter(({"subject": "octopus", "entities": ["octopus"]},)),
    )
    out = editorial.review(_story())
    assert not out.approved
    assert any("cooldown" in reason for reason in out.reasons)


def test_rank_candidates_puts_approved_story_first(monkeypatch):
    monkeypatch.setattr(editorial.channel_memory, "_iter_recent", lambda days: iter(()))
    weak = dict(_story(), thumbnail_text="", score=1)
    ranked = editorial.rank_candidates([weak, _story()])
    assert ranked[0]["editorial"]["approved"] is True
    assert ranked[0]["series"] == "Ocean Mysteries"
    assert ranked[0]["editorial"]["humanity"]["label"] in {"human", "signature"}


def test_subject_normalises_plural_and_ignores_habitat_tag():
    story = _story()
    story["yt_tags"] = ["coral", "octopuses", "camouflage"]
    assert editorial.subject_for_story(story) == "octopus"
