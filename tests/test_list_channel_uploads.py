import json

import scripts.list_channel_uploads as list_channel_uploads


def test_main_prints_uploads_as_json(monkeypatch, capsys):
    monkeypatch.setattr(list_channel_uploads, "get_youtube_service", lambda: object())
    uploads = [{"video_id": "abc", "title": "Test", "published_at": "2026-07-17T00:00:00Z"}]
    monkeypatch.setattr(list_channel_uploads, "_fetch_recent_channel_uploads", lambda youtube, limit=200: uploads)

    assert list_channel_uploads.main() == 0

    out = capsys.readouterr().out
    assert json.loads(out) == uploads
