"""Tests for upload_tiktok._build_caption — caption composition."""
from __future__ import annotations

from upload_tiktok import _build_caption


def test_caption_includes_title_and_description():
    meta = {
        "title":       "A cat reads the newspaper",
        "description": "Watch this one twice.\n\n#fyp #cats",
    }
    cap = _build_caption(meta)
    assert "A cat reads the newspaper" in cap
    assert "#fyp #cats" in cap


def test_caption_omits_exact_duplicate_description():
    """If the description equals the title we don't double up."""
    meta = {
        "title":       "Same line",
        "description": "Same line",
    }
    cap = _build_caption(meta)
    assert cap.count("Same line") == 1


def test_caption_truncates_over_2200_chars():
    meta = {
        "title":       "x" * 50,
        "description": ("desc " * 600).strip() + "\n#fyp",
    }
    cap = _build_caption(meta)
    assert len(cap) <= 2200


def test_caption_defaults_when_both_missing():
    cap = _build_caption({})
    assert cap == "Wild Brief"


def test_caption_strips_whitespace_only_fields():
    meta = {"title": "  \n", "description": "real body\n#fyp"}
    cap = _build_caption(meta)
    assert cap.startswith("real body")
