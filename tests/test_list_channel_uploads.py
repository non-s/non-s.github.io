import json
from unittest.mock import MagicMock

import scripts.list_channel_uploads as list_channel_uploads


def test_main_prints_uploads_as_json(monkeypatch, capsys):
    monkeypatch.setattr(list_channel_uploads, "get_youtube_service", lambda: object())
    uploads = [{"video_id": "abc", "title": "Test", "published_at": "2026-07-17T00:00:00Z"}]
    monkeypatch.setattr(list_channel_uploads, "_fetch_recent_channel_uploads", lambda youtube, limit=200: uploads)
    monkeypatch.setattr(list_channel_uploads, "_attach_statistics", lambda youtube, uploads: None)

    assert list_channel_uploads.main() == 0

    out = capsys.readouterr().out
    assert json.loads(out) == uploads


def test_attach_statistics_merges_view_like_comment_counts_by_id():
    uploads = [{"video_id": "abc"}, {"video_id": "def"}, {"video_id": "no-stats-returned"}]
    youtube = MagicMock()
    youtube.videos.return_value.list.return_value.execute.return_value = {
        "items": [
            {"id": "abc", "statistics": {"viewCount": "150", "likeCount": "12", "commentCount": "3"}},
            {"id": "def", "statistics": {"viewCount": "9"}},
        ]
    }

    list_channel_uploads._attach_statistics(youtube, uploads)

    assert uploads[0]["view_count"] == 150
    assert uploads[0]["like_count"] == 12
    assert uploads[0]["comment_count"] == 3
    assert uploads[1] == {"video_id": "def", "view_count": 9, "like_count": 0, "comment_count": 0}
    assert uploads[2] == {"video_id": "no-stats-returned", "view_count": 0, "like_count": 0, "comment_count": 0}


def test_attach_statistics_batches_at_50_ids_per_call():
    uploads = [{"video_id": f"id{i}"} for i in range(120)]
    youtube = MagicMock()
    youtube.videos.return_value.list.return_value.execute.return_value = {"items": []}

    list_channel_uploads._attach_statistics(youtube, uploads)

    assert youtube.videos.return_value.list.call_count == 3
