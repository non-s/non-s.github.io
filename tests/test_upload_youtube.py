"""Focused tests for YouTube uploader helpers."""
from __future__ import annotations

import pytest

pytest.importorskip("googleapiclient")

from upload_youtube import (
    _comment_text,
    _done_marker,
    _is_uploadable_meta,
    _normalise_tags,
    _playlist_titles,
    _video_url,
    _youtube_description,
    _youtube_title,
    check_auth,
    run_post_upload_operations,
)


def test_title_respects_youtube_limit():
    assert len(_youtube_title({"title": "x" * 140})) <= 100


def test_description_adds_shorts_discovery_tags():
    desc = _youtube_description({"title": "Cats are surprising", "description": "Body"})
    assert "#Shorts" in desc
    assert "#NatureFacts" in desc
    assert "#WildBrief" in desc
    assert "#EarthScience" in desc


def test_tags_are_deduplicated_case_insensitively():
    assert _normalise_tags(["Cats", "cats", "#Wildlife"]) == ["Cats", "Wildlife"]


def test_short_url_is_canonical():
    assert _video_url("abc123") == "https://www.youtube.com/shorts/abc123"


def test_check_auth_loads_credentials(monkeypatch):
    called = {"value": False}

    def fake_load():
        called["value"] = True
        return object()

    monkeypatch.setattr("upload_youtube._load_credentials", fake_load)

    assert check_auth() is True
    assert called["value"] is True


def test_orphan_metadata_is_not_uploadable(tmp_path):
    assert not _is_uploadable_meta({"video": str(tmp_path / "missing.mp4")})


def test_rejected_pre_publish_audit_is_not_uploadable(tmp_path):
    video = tmp_path / "short.mp4"
    video.write_bytes(b"fake")
    assert not _is_uploadable_meta({
        "video": str(video),
        "pre_publish_audit": {"approved": False, "score": 40},
    })


def test_done_marker_preserves_production_quality_signals():
    marker = _done_marker("abc123", {
        "title": "Octopus", "has_broll": True, "has_captions": True,
        "script_quality_grade": 9,
        "visual_qa": {"checked": True, "approved": True, "thumbnail_quality": 8},
        "humanity": {"score": 88, "label": "signature"},
        "studio_polish": {"applied": True, "before_score": 20, "after_score": 88},
        "studio_state": "polished",
        "ai_rewrite": {"attempted": True, "accepted": True},
        "pre_publish_audit": {"approved": True, "score": 92},
        "monetization_audit": {"approved": True, "score": 94},
        "seo_score": {"score": 96},
        "seo_optimisation": {"applied": True},
        "cta_prompt": "Follow for more animal facts.",
        "replay_prompt": "End by pointing back to the wing.",
        "youtube_operations": {"enabled": True},
    })
    assert marker["url"] == "https://www.youtube.com/shorts/abc123"
    assert marker["has_broll"] is True
    assert marker["has_captions"] is True
    assert marker["script_quality_grade"] == 9
    assert marker["visual_qa"]["thumbnail_quality"] == 8
    assert marker["humanity"]["label"] == "signature"
    assert marker["studio_polish"]["applied"] is True
    assert marker["studio_state"] == "polished"
    assert marker["ai_rewrite"]["accepted"] is True
    assert marker["pre_publish_audit"]["score"] == 92
    assert marker["monetization_audit"]["score"] == 94
    assert marker["seo_score"]["score"] == 96
    assert marker["seo_optimisation"]["applied"] is True
    assert marker["cta_prompt"] == "Follow for more animal facts."
    assert marker["replay_prompt"].startswith("End by")
    assert marker["youtube_operations"]["enabled"] is True


def test_playlist_titles_use_series_and_category():
    titles = _playlist_titles({"series": "Watch The Cue", "category": "birds"})

    assert titles == [
        "Wild Brief | Start Here",
        "Wild Brief | Watch The Cue",
        "Wild Brief | Birds",
    ]


def test_comment_text_prefers_packaging_comment():
    assert _comment_text({
        "packaging": {"pinned_comment": "What should we decode next?"},
        "cta_prompt": "Follow for more.",
    }) == "What should we decode next?"


class _Req:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _Playlists:
    def __init__(self):
        self.created = []

    def list(self, **kwargs):
        return _Req({"items": []})

    def insert(self, **kwargs):
        title = kwargs["body"]["snippet"]["title"]
        self.created.append(title)
        return _Req({"id": "PL-" + str(len(self.created))})


class _PlaylistItems:
    def __init__(self):
        self.added = []

    def list(self, **kwargs):
        return _Req({"items": []})

    def insert(self, **kwargs):
        snippet = kwargs["body"]["snippet"]
        self.added.append((snippet["playlistId"], snippet["resourceId"]["videoId"]))
        return _Req({"id": "PLI-" + str(len(self.added))})


class _CommentThreads:
    def __init__(self):
        self.comments = []

    def insert(self, **kwargs):
        snippet = kwargs["body"]["snippet"]
        text = snippet["topLevelComment"]["snippet"]["textOriginal"]
        self.comments.append((snippet["videoId"], text))
        return _Req({
            "id": "COMMENT_THREAD",
            "snippet": {
                "topLevelComment": {
                    "snippet": {
                        "authorChannelId": {"value": "CHANNEL"},
                    }
                }
            },
        })


class _YouTube:
    def __init__(self):
        self._playlists = _Playlists()
        self._playlist_items = _PlaylistItems()
        self._comment_threads = _CommentThreads()

    def playlists(self):
        return self._playlists

    def playlistItems(self):
        return self._playlist_items

    def commentThreads(self):
        return self._comment_threads


def test_post_upload_operations_adds_playlists_and_comment(monkeypatch):
    monkeypatch.setenv("YOUTUBE_POST_UPLOAD_AUTOMATION", "1")
    youtube = _YouTube()
    result = run_post_upload_operations(youtube, "VID123", {
        "series": "Watch The Cue",
        "category": "birds",
        "packaging": {"pinned_comment": "Did you catch the wing?"},
    })

    assert result["enabled"] is True
    assert [item["title"] for item in result["playlists"]] == [
        "Wild Brief | Start Here",
        "Wild Brief | Watch The Cue",
        "Wild Brief | Birds",
    ]
    assert all(item["added"] for item in result["playlists"])
    assert youtube._playlist_items.added == [("PL-1", "VID123"), ("PL-2", "VID123"), ("PL-3", "VID123")]
    assert youtube._comment_threads.comments == [("VID123", "Did you catch the wing?")]
    assert result["comment"]["posted"] is True
    assert result["comment"]["pin_status"] == "not_supported_by_youtube_data_api"


def test_post_upload_operations_can_be_disabled(monkeypatch):
    monkeypatch.setenv("YOUTUBE_POST_UPLOAD_AUTOMATION", "0")

    assert run_post_upload_operations(_YouTube(), "VID123", {}) == {"enabled": False}
