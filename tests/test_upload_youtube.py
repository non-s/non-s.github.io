"""Focused tests for YouTube uploader helpers."""
from __future__ import annotations

import pytest

pytest.importorskip("googleapiclient")

from upload_youtube import _normalise_tags, _video_url, _youtube_description, _youtube_title


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
