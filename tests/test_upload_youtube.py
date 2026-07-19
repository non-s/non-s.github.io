"""Focused tests for YouTube uploader helpers."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

pytest.importorskip("googleapiclient")

from googleapiclient.errors import HttpError

import upload_youtube
from upload_youtube import (
    _apply_unique_upload_title,
    _done_marker,
    _existing_upload_titles,
    _is_uploadable_meta,
    _normalise_tags,
    _playlist_titles,
    _scheduled_publish_at,
    _video_url,
    _youtube_description,
    _youtube_title,
    check_auth,
    run_post_upload_operations,
    upload_video,
)


def test_title_respects_youtube_limit():
    assert len(_youtube_title({"title": "x" * 140})) <= 100


def test_unique_upload_title_uses_concrete_detail_for_repeated_title():
    meta = {
        "title": "Plants turn sunlight into stored sugar",
        "description": "Plants turn sunlight into stored sugar. A plant short.",
        "category": "plants",
        "tags": ["tropical leaves", "plant physics", "nature"],
        "story_id": "8e163c589af35632",
    }

    result = _apply_unique_upload_title(meta, {"plants turn sunlight into stored sugar"})

    assert result["applied"] is True
    assert meta["title"] == "Tropical leaves turn sunlight into stored sugar"
    assert meta["description"].startswith("Tropical leaves turn sunlight into stored sugar.")
    assert meta["upload_title_dedupe"]["reason"] == "published_title_collision"


def test_unique_upload_title_preserves_story_subject_when_visual_tags_conflict():
    meta = {
        "title": "Plants use trap hairs to count touches before snapping shut",
        "description": "Plants use trap hairs to count touches before snapping shut. A plant short.",
        "category": "plants",
        "tags": ["wasp", "pollination", "flower", "insects", "plants"],
        "search_intent": {
            "visible_cue": "leaf surface",
            "terms": ["plants", "leaf surface", "plant mechanism"],
        },
        "story_id": "0ea9a0496d40aaef",
    }

    result = _apply_unique_upload_title(
        meta,
        {"plants use trap hairs to count touches before snapping shut"},
    )

    assert result["applied"] is True
    assert meta["title"] == "Plants use trap hairs to count touches before snapping shut | Leaf surface"
    assert not meta["title"].lower().startswith("wasp ")
    assert meta["description"].startswith("Plants use trap hairs to count touches before snapping shut | Leaf surface.")


def test_unique_upload_title_leaves_fresh_title_unchanged():
    meta = {"title": "Sharks sense tiny electric fields", "tags": ["sharks"]}

    result = _apply_unique_upload_title(meta, {"cats purr when muscles vibrate"})

    assert result == {"applied": False, "title": "Sharks sense tiny electric fields"}
    assert meta["title"] == "Sharks sense tiny electric fields"


def test_unique_upload_title_uses_the_video_own_mood_not_a_fixed_tag():
    """Regression: with the mood tag last in a lofi video's tag list,
    _candidate_title_details() always exhausted the shared DEFAULT_TAGS
    entries first, so any two colliding lofi titles landed on the exact
    same dedup suffix regardless of their own mood -- generate_lofi_short.py
    now puts the mood tag first instead."""
    base_tags = ["anime lofi", "rainy night lofi", "cozy anime lofi", "amber hours"]

    cat_meta = {
        "title": "Cozy Anime Lofi — Amber Hours",
        "description": "cat sleeping lofi beats -- chill music to relax, study or unwind to.",
        "category": "lofi",
        "tags": ["cat sleeping", *base_tags],
    }
    snow_meta = {
        "title": "Cozy Anime Lofi — Amber Hours",
        "description": "snow window lofi beats -- chill music to relax, study or unwind to.",
        "category": "lofi",
        "tags": ["snow window", *base_tags],
    }

    cat_result = _apply_unique_upload_title(cat_meta, {"cozy anime lofi — amber hours"})
    snow_result = _apply_unique_upload_title(snow_meta, {"cozy anime lofi — amber hours"})

    assert cat_result["applied"] is True
    assert snow_result["applied"] is True
    assert "Cat sleeping" in cat_meta["title"]
    assert "Snow window" in snow_meta["title"]
    assert cat_meta["title"] != snow_meta["title"]


def test_existing_upload_titles_reads_done_markers(tmp_path):
    (tmp_path / "short.done").write_text(json.dumps({"title": "Cats purr softly"}), encoding="utf-8")
    (tmp_path / "ignored.json").write_text(json.dumps({"title": "Not uploaded yet"}), encoding="utf-8")

    assert _existing_upload_titles(tmp_path) == {"cats purr softly"}


def test_description_adds_default_shorts_discovery_tag(monkeypatch):
    monkeypatch.delenv("CHANNEL_DEFAULT_HASHTAGS", raising=False)
    desc = _youtube_description({"title": "Cats are surprising", "description": "Body"})
    assert "#Shorts" in desc


def test_description_uses_configured_channel_hashtags(monkeypatch):
    monkeypatch.setenv("CHANNEL_DEFAULT_HASHTAGS", "#Shorts,#Lofi,#ChillBeats")
    desc = _youtube_description({"title": "Rainy night loop", "description": "Body"})
    assert "#Shorts" in desc
    assert "#Lofi" in desc
    assert "#ChillBeats" in desc


def test_description_does_not_duplicate_hashtags_already_present(monkeypatch):
    monkeypatch.setenv("CHANNEL_DEFAULT_HASHTAGS", "#Shorts,#Lofi")
    desc = _youtube_description({"title": "Rainy night loop", "description": "Body #Lofi"})
    assert desc.count("#Lofi") == 1


def test_tags_are_deduplicated_case_insensitively():
    assert _normalise_tags(["Cats", "cats", "#Wildlife"]) == ["Cats", "Wildlife"]


def test_short_url_is_canonical():
    assert _video_url("abc123") == "https://www.youtube.com/shorts/abc123"


def test_long_form_url_is_not_a_shorts_link():
    assert _video_url("abc123", {"is_short": False}) == "https://www.youtube.com/watch?v=abc123"


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
    assert not _is_uploadable_meta(
        {
            "video": str(video),
            "pre_publish_audit": {"approved": False, "score": 40},
        }
    )


def test_done_marker_preserves_lofi_production_signals():
    """Regression: _done_marker() used to silently drop duration_s/story_id/
    bgm_track_id/bgm_license_ccurl (missing from its old ~90-field schema
    despite both generators always setting them on meta) while persisting
    ~75 narrated-content fields (gbif, narrator_voice, humanity, ...) that
    nothing in the lofi pipeline -- or anything downstream -- ever reads."""
    marker = _done_marker(
        "abc123",
        {
            "title": "Rainy Night Anime Lofi — Amber Hours",
            "duration_s": 42.5,
            "story_id": "lofi-1700000000-1234",
            "bgm_track_id": "99",
            "bgm_license_ccurl": "http://creativecommons.org/licenses/by/3.0/",
            "pre_publish_audit": {"approved": True, "reason": "lofi_no_claims_to_vet"},
            "youtube_operations": {"enabled": True},
        },
    )
    assert marker["url"] == "https://www.youtube.com/shorts/abc123"
    assert marker["duration_s"] == 42.5
    assert marker["story_id"] == "lofi-1700000000-1234"
    assert marker["bgm_track_id"] == "99"
    assert marker["bgm_license_ccurl"] == "http://creativecommons.org/licenses/by/3.0/"
    assert marker["pre_publish_audit"]["approved"] is True
    assert marker["youtube_operations"]["enabled"] is True


def test_done_marker_defaults_lofi_fields_when_absent():
    marker = _done_marker("abc123", {"title": "Cozy Anime Lofi"})
    assert marker["duration_s"] == 0.0
    assert marker["story_id"] == ""
    assert marker["bgm_track_id"] == ""
    assert marker["bgm_license_ccurl"] == ""


def test_done_marker_uses_scheduled_publish_time_for_temporal_fields():
    marker = _done_marker(
        "abc123",
        {
            "title": "Scheduled Short",
            "scheduled_publish_at": "2026-06-13T00:23:00Z",
            "publish_ts_utc": "2026-06-13T00:23:00Z",
            "youtube_privacy": "private",
        },
    )

    assert marker["scheduled_publish_at"] == "2026-06-13T00:23:00Z"
    assert marker["publish_ts_utc"].startswith("2026-06-13T00:23:00")
    assert marker["youtube_privacy"] == "private"


def test_playlist_titles_use_series_and_category():
    titles = _playlist_titles({"series": "Watch The Cue", "category": "birds"})

    assert titles == [
        "Start Here",
        "Watch The Cue",
        "Birds",
        "Cozy Anime Lofi",
    ]


def test_playlist_titles_apply_configured_prefix(monkeypatch):
    monkeypatch.setattr(upload_youtube, "PLAYLIST_PREFIX", "Wild Brief | ")
    titles = _playlist_titles({"series": "Watch The Cue", "category": "birds"})

    assert titles == [
        "Wild Brief | Start Here",
        "Wild Brief | Watch The Cue",
        "Wild Brief | Birds",
        "Wild Brief | Cozy Anime Lofi",
    ]


def test_playlist_titles_group_by_mood_signal_in_the_title():
    titles = _playlist_titles(
        {"title": "Rainy Night Anime Lofi — Amber Hours \U0001f327️", "series": "Lofi Beats", "category": "lofi"}
    )
    assert "Rainy Night Lofi" in titles

    titles = _playlist_titles(
        {"title": "Sleepy Cat Anime Lofi — Amber Hours \U0001f43e", "series": "Lofi Beats", "category": "lofi"}
    )
    assert "Cozy Cat Lofi" in titles


class _Req:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _UploadReq:
    def next_chunk(self):
        return None, {"id": "VID123"}


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


class _PlaylistItemsPrecheck404(_PlaylistItems):
    def list(self, **kwargs):
        raise HttpError(SimpleNamespace(status=404, reason="Not Found"), b'{"error":{"message":"playlist not found"}}')


class _Videos:
    def __init__(self):
        self.inserts = []

    def insert(self, **kwargs):
        self.inserts.append(kwargs)
        return _UploadReq()


class _Thumbnails:
    def __init__(self):
        self.uploads = []

    def set(self, **kwargs):
        self.uploads.append(kwargs)
        return _Req({"id": "thumb"})


class _YouTube:
    def __init__(self):
        self._playlists = _Playlists()
        self._playlist_items = _PlaylistItems()
        self._videos = _Videos()
        self._thumbnails = _Thumbnails()

    def playlists(self):
        return self._playlists

    def playlistItems(self):
        return self._playlist_items

    def videos(self):
        return self._videos

    def thumbnails(self):
        return self._thumbnails


def test_post_upload_operations_adds_playlists(monkeypatch):
    monkeypatch.setenv("YOUTUBE_POST_UPLOAD_AUTOMATION", "1")
    monkeypatch.setattr(upload_youtube, "PLAYLIST_PREFIX", "Wild Brief | ")
    youtube = _YouTube()
    result = run_post_upload_operations(
        youtube,
        "VID123",
        {
            "series": "Watch The Cue",
            "category": "birds",
        },
    )

    assert result["enabled"] is True
    assert [item["title"] for item in result["playlists"]] == [
        "Wild Brief | Start Here",
        "Wild Brief | Watch The Cue",
        "Wild Brief | Birds",
        "Wild Brief | Cozy Anime Lofi",
    ]
    assert all(item["added"] for item in result["playlists"])
    assert youtube._playlist_items.added == [
        ("PL-1", "VID123"),
        ("PL-2", "VID123"),
        ("PL-3", "VID123"),
        ("PL-4", "VID123"),
    ]


def test_post_upload_operations_inserts_after_playlist_precheck_404(monkeypatch):
    monkeypatch.setenv("YOUTUBE_POST_UPLOAD_AUTOMATION", "1")
    youtube = _YouTube()
    youtube._playlist_items = _PlaylistItemsPrecheck404()

    result = run_post_upload_operations(youtube, "VID123", {"series": "Tiny Worlds", "category": "insects"})

    assert all(item["added"] for item in result["playlists"])
    assert youtube._playlist_items.added == [
        ("PL-1", "VID123"),
        ("PL-2", "VID123"),
        ("PL-3", "VID123"),
        ("PL-4", "VID123"),
    ]


def test_post_upload_operations_can_be_disabled(monkeypatch):
    monkeypatch.setenv("YOUTUBE_POST_UPLOAD_AUTOMATION", "0")

    assert run_post_upload_operations(_YouTube(), "VID123", {}) == {"enabled": False}


def test_scheduled_publish_at_uses_rolling_slots(monkeypatch):
    monkeypatch.setenv("YOUTUBE_SCHEDULE_UPLOADS", "1")
    monkeypatch.setenv("YOUTUBE_SCHEDULE_START_UTC", "2026-06-13T00:00:00Z")
    monkeypatch.setenv("YOUTUBE_SCHEDULE_SLOTS_UTC", "00:23,02:23")

    assert _scheduled_publish_at({}, sequence_index=0) == "2026-06-13T00:23:00Z"
    assert _scheduled_publish_at({}, sequence_index=2) == "2026-06-14T00:23:00Z"


def test_upload_video_sets_publish_at_for_scheduled_private_upload(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUTUBE_SCHEDULE_UPLOADS", "1")
    monkeypatch.setenv("YOUTUBE_SCHEDULE_START_UTC", "2026-06-13T00:00:00Z")
    monkeypatch.setenv("YOUTUBE_SCHEDULE_SLOTS_UTC", "00:23,02:23")
    video = tmp_path / "short.mp4"
    video.write_bytes(b"fake")
    thumb = tmp_path / "thumb.jpg"
    thumb.write_bytes(b"fake")
    youtube = _YouTube()
    meta = {"video": str(video), "thumbnail": str(thumb), "title": "Test Short"}

    assert upload_video(youtube, meta, sequence_index=1) == "VID123"

    status = youtube._videos.inserts[0]["body"]["status"]
    assert status["privacyStatus"] == "private"
    assert status["publishAt"] == "2026-06-13T02:23:00Z"
    assert meta["scheduled_publish_at"] == "2026-06-13T02:23:00Z"
