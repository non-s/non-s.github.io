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
