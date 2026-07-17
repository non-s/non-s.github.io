from unittest.mock import MagicMock

import scripts.delete_channel_videos as delete_channel_videos


def test_delete_videos_reports_success_per_id():
    youtube = MagicMock()

    results = delete_channel_videos.delete_videos(youtube, ["abc", "def"])

    assert results == {"abc": True, "def": True}
    assert youtube.videos().delete.call_count == 2


def test_delete_videos_reports_failure_without_stopping_others():
    youtube = MagicMock()
    youtube.videos().delete().execute.side_effect = [Exception("boom"), None]

    results = delete_channel_videos.delete_videos(youtube, ["bad", "good"])

    assert results == {"bad": False, "good": True}


def test_main_requires_at_least_one_video_id(monkeypatch, capsys):
    monkeypatch.setattr(delete_channel_videos.sys, "argv", ["delete_channel_videos.py"])

    assert delete_channel_videos.main() == 2
    assert "Usage" in capsys.readouterr().err


def test_main_returns_zero_when_all_deletes_succeed(monkeypatch):
    monkeypatch.setattr(delete_channel_videos.sys, "argv", ["delete_channel_videos.py", "abc"])
    monkeypatch.setattr(delete_channel_videos, "get_youtube_service", lambda: MagicMock())

    assert delete_channel_videos.main() == 0


def test_main_returns_one_when_a_delete_fails(monkeypatch):
    monkeypatch.setattr(delete_channel_videos.sys, "argv", ["delete_channel_videos.py", "abc"])
    fake_youtube = MagicMock()
    fake_youtube.videos().delete().execute.side_effect = Exception("boom")
    monkeypatch.setattr(delete_channel_videos, "get_youtube_service", lambda: fake_youtube)

    assert delete_channel_videos.main() == 1
