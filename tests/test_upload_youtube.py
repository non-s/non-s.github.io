"""Focused tests for YouTube uploader helpers."""
from __future__ import annotations

import pytest

pytest.importorskip("googleapiclient")

from upload_youtube import _done_marker, _is_uploadable_meta, _normalise_tags, _video_url, _youtube_description, _youtube_title


def test_title_respects_youtube_limit():
    assert len(_youtube_title({"title": "x" * 140})) <= 100


def test_description_adds_shorts_discovery_tags():
    desc = _youtube_description({"title": "Cats are surprising", "description": "Body"})
    assert "#Shorts" in desc
    assert "#AnimalFacts" in desc
    assert "#Wildlife" in desc


def test_tags_are_deduplicated_case_insensitively():
    assert _normalise_tags(["Cats", "cats", "#Wildlife"]) == ["Cats", "Wildlife"]


def test_short_url_is_canonical():
    assert _video_url("abc123") == "https://www.youtube.com/shorts/abc123"


def test_orphan_metadata_is_not_uploadable(tmp_path):
    assert not _is_uploadable_meta({"video": str(tmp_path / "missing.mp4")})


def test_done_marker_preserves_production_quality_signals():
    marker = _done_marker("abc123", {
        "title": "Octopus", "has_broll": True, "has_captions": True,
        "script_quality_grade": 9,
        "visual_qa": {"checked": True, "approved": True, "thumbnail_quality": 8},
        "humanity": {"score": 88, "label": "signature"},
        "studio_polish": {"applied": True, "before_score": 20, "after_score": 88},
        "studio_state": "polished",
    })
    assert marker["url"] == "https://www.youtube.com/shorts/abc123"
    assert marker["has_broll"] is True
    assert marker["has_captions"] is True
    assert marker["script_quality_grade"] == 9
    assert marker["visual_qa"]["thumbnail_quality"] == 8
    assert marker["humanity"]["label"] == "signature"
    assert marker["studio_polish"]["applied"] is True
    assert marker["studio_state"] == "polished"
