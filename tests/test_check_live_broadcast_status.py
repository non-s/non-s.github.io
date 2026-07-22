from unittest.mock import MagicMock

import scripts.check_live_broadcast_status as check_live_broadcast_status


def test_find_active_broadcasts_filters_by_lifecycle_status():
    youtube = MagicMock()
    youtube.liveBroadcasts().list().execute.return_value = {
        "items": [
            {"id": "live-1", "status": {"lifeCycleStatus": "live"}, "snippet": {"title": "A"}},
            {"id": "ready-1", "status": {"lifeCycleStatus": "ready"}, "snippet": {"title": "B"}},
            {"id": "complete-1", "status": {"lifeCycleStatus": "complete"}, "snippet": {"title": "C"}},
        ]
    }

    broadcasts = check_live_broadcast_status.find_active_broadcasts(youtube)

    assert [b["id"] for b in broadcasts] == ["live-1", "ready-1"]


def test_main_prints_nothing_found_message(monkeypatch, capsys):
    fake_youtube = MagicMock()
    fake_youtube.liveBroadcasts().list().execute.return_value = {"items": []}
    monkeypatch.setattr(check_live_broadcast_status, "get_youtube_service", lambda: fake_youtube)

    assert check_live_broadcast_status.main() == 0
    assert "No active" in capsys.readouterr().out


def test_main_prints_title_and_description(monkeypatch, capsys):
    fake_youtube = MagicMock()
    fake_youtube.liveBroadcasts().list().execute.return_value = {
        "items": [
            {
                "id": "abc123",
                "status": {"lifeCycleStatus": "live"},
                "snippet": {"title": "My New Title", "description": "My New Description"},
            }
        ]
    }
    monkeypatch.setattr(check_live_broadcast_status, "get_youtube_service", lambda: fake_youtube)

    assert check_live_broadcast_status.main() == 0
    out = capsys.readouterr().out
    assert "My New Title" in out
    assert "My New Description" in out
    assert "abc123" in out
