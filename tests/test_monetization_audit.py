"""Tests for local monetization-readiness checks."""
from utils.monetization_audit import audit


def _meta(**overrides):
    base = {
        "title": "Why octopuses vanish in seconds",
        "description": "Original narration with source.",
        "hook": "Octopuses vanish in seconds.",
        "has_broll": True,
        "has_captions": True,
        "script_quality_grade": 9,
        "humanity": {"score": 88},
        "source_url": "https://www.pexels.com/video/octopus/",
    }
    base.update(overrides)
    return base


def test_monetization_audit_approves_transformative_package():
    out = audit(_meta())
    assert out["approved"] is True
    assert out["state"] == "monetization_ready"


def test_monetization_audit_blocks_weak_package():
    out = audit(_meta(has_broll=False, script_quality_grade=4, humanity={"score": 40}))
    assert out["approved"] is False
    assert "no motion b-roll" in out["reasons"]
    assert "script quality too low" in out["reasons"]
