"""Tests for the final pre-publish package audit."""

from utils.pre_publish_audit import audit_package


def _meta(**overrides):
    base = {
        "title": "Why octopuses use shells as tiny shields",
        "hook": "Octopuses carry shells like shields.",
        "has_broll": True,
        "has_captions": True,
        "script_quality_grade": 9,
        "editorial": {"approved": True, "score": 88},
        "humanity": {"score": 90, "label": "signature"},
        "visual_qa": {"checked": True, "approved": True, "thumbnail_quality": 8},
        "hook_audit": {"approved": True},
        "title_audit": {"approved": True},
    }
    base.update(overrides)
    return base


def test_pre_publish_audit_approves_strong_package():
    out = audit_package(_meta())
    assert out["approved"] is True
    assert out["state"] == "publish_ready"
    assert out["score"] >= out["threshold"]


def test_pre_publish_audit_blocks_unapproved_editorial():
    out = audit_package(_meta(editorial={"approved": False, "score": 90}))
    assert out["approved"] is False
    assert "editorial review is not approved" in out["reasons"]


def test_pre_publish_audit_penalizes_missing_retention_basics():
    out = audit_package(_meta(has_broll=False, has_captions=False))
    assert out["approved"] is False
    assert "captions are missing" in out["reasons"]
    assert "motion b-roll is missing" in out["reasons"]


def test_pre_publish_audit_blocks_monetization_review():
    out = audit_package(_meta(monetization_audit={"approved": False, "score": 45}))
    assert out["approved"] is False
    assert "monetization audit needs review" in out["reasons"]
