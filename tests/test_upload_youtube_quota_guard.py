import json

import pytest

pytest.importorskip("googleapiclient")

import upload_youtube


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
