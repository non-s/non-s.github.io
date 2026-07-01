import json

import pytest

pytest.importorskip("googleapiclient")

import upload_youtube
from scripts.upload_intent import read_intents, write_upload_intent


def test_upload_main_returns_when_quota_guard_blocks(tmp_path, monkeypatch):
    videos = tmp_path / "_videos"
    videos.mkdir()
    (videos / "short-test.json").write_text(json.dumps({"video": str(tmp_path / "missing.mp4")}), encoding="utf-8")
    monkeypatch.setattr(upload_youtube, "VIDEOS_DIR", videos)
    monkeypatch.setattr(upload_youtube, "get_youtube_service", lambda: object())
    monkeypatch.setattr(
        upload_youtube,
        "write_quota_ledger_row",
        lambda estimate: {"guard": {"block": True, "reason": "quota_ratio_exceeded"}},
    )

    assert upload_youtube.main() is None


def test_upload_main_fails_empty_publish_window_when_upload_required(tmp_path, monkeypatch):
    videos = tmp_path / "_videos"
    videos.mkdir()
    monkeypatch.setenv("REQUIRE_UPLOAD_ON_PUBLISH", "1")
    monkeypatch.setattr(upload_youtube, "VIDEOS_DIR", videos)
    monkeypatch.setattr(upload_youtube, "get_youtube_service", lambda: object())

    with pytest.raises(SystemExit) as exc:
        upload_youtube.main()

    assert exc.value.code == 1


def test_upload_main_treats_duplicate_slot_as_safe_skip_when_upload_required(tmp_path, monkeypatch):
    videos = tmp_path / "_videos"
    videos.mkdir()
    video = videos / "short-test.mp4"
    video.write_bytes(b"fake")
    (videos / "short-test.json").write_text(
        json.dumps({"video": str(video), "title": "Already Uploaded", "publish_slot_key": "2026-06-27T20:00Z"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("REQUIRE_UPLOAD_ON_PUBLISH", "1")
    monkeypatch.setenv("UPLOAD_SLOT_IDEMPOTENCY_MODE", "block")
    monkeypatch.setattr(upload_youtube, "VIDEOS_DIR", videos)
    monkeypatch.setattr(upload_youtube, "get_youtube_service", lambda: object())
    monkeypatch.setattr(upload_youtube, "write_quota_ledger_row", lambda estimate: {"guard": {"block": False}})
    monkeypatch.setattr(upload_youtube, "duplicate_slot_uploaded", lambda slot: {"video_id": "VID123"})
    monkeypatch.setattr(
        upload_youtube,
        "upload_video",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("upload called")),
    )

    assert upload_youtube.main() is None


def test_upload_main_treats_duplicate_intent_as_safe_skip_when_upload_required(tmp_path, monkeypatch):
    videos = tmp_path / "_videos"
    videos.mkdir()
    video = videos / "short-test.mp4"
    video.write_bytes(b"fake")
    (videos / "short-test.json").write_text(
        json.dumps({"video": str(video), "title": "Already Uploaded", "story_id": "story-1"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("REQUIRE_UPLOAD_ON_PUBLISH", "1")
    monkeypatch.setenv("UPLOAD_IDEMPOTENCY_MODE", "block")
    monkeypatch.setattr(upload_youtube, "VIDEOS_DIR", videos)
    monkeypatch.setattr(upload_youtube, "get_youtube_service", lambda: object())
    monkeypatch.setattr(upload_youtube, "write_quota_ledger_row", lambda estimate: {"guard": {"block": False}})
    monkeypatch.setattr(upload_youtube, "duplicate_slot_uploaded", lambda slot: None)
    monkeypatch.setattr(upload_youtube, "duplicate_uploaded", lambda intent: {"video_id": "VID456"})
    monkeypatch.setattr(
        upload_youtube,
        "upload_video",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("upload called")),
    )

    assert upload_youtube.main() is None


def test_upload_main_adopts_existing_channel_title_duplicate(tmp_path, monkeypatch):
    videos = tmp_path / "_videos"
    videos.mkdir()
    video = videos / "short-test.mp4"
    video.write_bytes(b"fake")
    meta_file = videos / "short-test.json"
    meta_file.write_text(
        json.dumps(
            {
                "video": str(video),
                "title": "Chickens keep their view steady while walking",
                "story_id": "story-1",
            }
        ),
        encoding="utf-8",
    )
    intents_path = tmp_path / "_data" / "upload_intents.jsonl"
    duplicate = {
        "video_id": "OLDVID12345",
        "title": "Chickens keep their view steady while walking",
        "published_at": "2026-07-01T17:04:49Z",
        "source": "youtube_api.uploads_playlist",
    }

    monkeypatch.setenv("REQUIRE_UPLOAD_ON_PUBLISH", "1")
    monkeypatch.setenv("UPLOAD_CHANNEL_TITLE_DEDUPE_MODE", "block")
    monkeypatch.setattr(upload_youtube, "VIDEOS_DIR", videos)
    monkeypatch.setattr(upload_youtube, "get_youtube_service", lambda: object())
    monkeypatch.setattr(upload_youtube, "write_quota_ledger_row", lambda estimate: {"guard": {"block": False}})
    monkeypatch.setattr(upload_youtube, "duplicate_slot_uploaded", lambda slot: {})
    monkeypatch.setattr(upload_youtube, "duplicate_uploaded", lambda intent: {})
    monkeypatch.setattr(upload_youtube, "_current_publish_slot", lambda: ("17:00", "2026-07-01T17:00Z"))
    monkeypatch.setattr(
        upload_youtube, "_existing_channel_upload_titles", lambda youtube: {duplicate["title"].lower(): duplicate}
    )
    monkeypatch.setattr(upload_youtube, "write_upload_intent", lambda intent: write_upload_intent(intent, intents_path))
    monkeypatch.setattr(upload_youtube, "_record_published_clip", lambda meta, video_id: None)
    monkeypatch.setattr(
        upload_youtube,
        "upload_video",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("upload called")),
    )

    assert upload_youtube.main() is None

    assert not meta_file.exists()
    marker = json.loads((videos / "short-test.done").read_text(encoding="utf-8"))
    assert marker["video_id"] == "OLDVID12345"
    assert marker["adopted_existing_upload"]["source"] == "youtube_api.uploads_playlist"
    rows = read_intents(intents_path)
    assert [row["status"] for row in rows] == ["prepared", "uploaded"]
    assert rows[1]["video_id"] == "OLDVID12345"


def test_upload_main_skips_channel_title_duplicate_when_video_is_already_tracked(tmp_path, monkeypatch):
    videos = tmp_path / "_videos"
    videos.mkdir()
    video = videos / "short-repeat.mp4"
    video.write_bytes(b"fake")
    title = "Chickens keep their view steady while walking"
    (videos / "already.done").write_text(
        json.dumps({"video_id": "OLDVID12345", "title": title}),
        encoding="utf-8",
    )
    meta_file = videos / "short-repeat.json"
    meta_file.write_text(
        json.dumps({"video": str(video), "title": title, "story_id": "story-2"}),
        encoding="utf-8",
    )
    intents_path = tmp_path / "_data" / "upload_intents.jsonl"
    duplicate = {
        "video_id": "OLDVID12345",
        "title": title,
        "published_at": "2026-07-01T17:26:31Z",
        "source": "youtube_intelligence.uploads",
    }

    monkeypatch.setenv("REQUIRE_UPLOAD_ON_PUBLISH", "1")
    monkeypatch.setattr(upload_youtube, "VIDEOS_DIR", videos)
    monkeypatch.setattr(upload_youtube, "get_youtube_service", lambda: object())
    monkeypatch.setattr(upload_youtube, "write_quota_ledger_row", lambda estimate: {"guard": {"block": False}})
    monkeypatch.setattr(upload_youtube, "duplicate_slot_uploaded", lambda slot: {})
    monkeypatch.setattr(upload_youtube, "_current_publish_slot", lambda: ("18:00", "2026-07-01T18:00Z"))
    monkeypatch.setattr(upload_youtube, "_existing_channel_upload_titles", lambda youtube: {title.lower(): duplicate})
    monkeypatch.setattr(upload_youtube, "write_upload_intent", lambda intent: write_upload_intent(intent, intents_path))
    monkeypatch.setattr(
        upload_youtube,
        "upload_video",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("upload called")),
    )

    assert upload_youtube.main() is None

    assert not meta_file.exists()
    assert not (videos / "short-repeat.done").exists()
    rows = read_intents(intents_path)
    assert [row["status"] for row in rows] == ["skipped_duplicate"]
    assert rows[0]["skip_reason"] == "channel_title_duplicate_already_tracked"
