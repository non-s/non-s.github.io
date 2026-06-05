"""Tests for the local human editorial signal."""
from __future__ import annotations

from utils.humanity_engine import score_story


def _human_story() -> dict:
    return {
        "title": "Chickens remember faces and hold grudges",
        "hook": "Chickens remember your face.",
        "script": (
            "Chickens remember your face. I love this detail: they watch "
            "your eyes, voice, and the shape around your beak-level smile. "
            "That's why one calm farmer can feel familiar, but a stranger "
            "makes the flock freeze. Which farm animal should we decode next?"
        ),
        "thumbnail_text": "CHICKEN MEMORY",
    }


def test_humanity_rewards_host_tension_detail_and_payoff():
    result = score_story(_human_story())
    assert result.score >= 78
    assert result.label in {"human", "signature"}
    assert "host_voice" in result.strengths
    assert "story_tension" in result.strengths
    assert "clear_payoff" in result.strengths


def test_humanity_penalizes_generic_fact_card():
    result = score_story({
        "title": "Amazing animal fact",
        "hook": "Did you know this animal is amazing?",
        "script": (
            "Did you know this animal is amazing? Animals have incredible "
            "adaptations in the animal kingdom. Nature is fascinating and "
            "this creature plays a vital role."
        ),
        "thumbnail_text": "AMAZING FACT",
    })
    assert result.score < 58
    assert result.label == "robotic"
    assert "missing_payoff" in result.issues
    assert result.rewrite_brief


def test_humanity_is_serializable():
    payload = score_story(_human_story()).to_dict()
    assert payload["score"] >= 0
    assert isinstance(payload["strengths"], tuple)
