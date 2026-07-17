from unittest.mock import MagicMock

import scripts.end_live_broadcast as end_live_broadcast


def test_find_active_broadcast_ids_filters_by_lifecycle_status():
    youtube = MagicMock()
    youtube.liveBroadcasts().list().execute.return_value = {
        "items": [
            {"id": "live-1", "status": {"lifeCycleStatus": "live"}},
            {"id": "ready-1", "status": {"lifeCycleStatus": "ready"}},
            {"id": "testing-1", "status": {"lifeCycleStatus": "testing"}},
            {"id": "complete-1", "status": {"lifeCycleStatus": "complete"}},
            {"id": "created-1", "status": {"lifeCycleStatus": "created"}},
        ]
    }

    ids = end_live_broadcast.find_active_broadcast_ids(youtube)

    assert ids == ["live-1", "ready-1", "testing-1"]


def test_end_broadcasts_reports_success_per_id():
    youtube = MagicMock()

    results = end_live_broadcast.end_broadcasts(youtube, ["abc", "def"])

    assert results == {"abc": True, "def": True}
    assert youtube.liveBroadcasts().transition.call_count == 2


def test_end_broadcasts_falls_back_to_delete_when_transition_is_invalid():
    """Checked live: a broadcast stuck in "ready" that never received
    valid stream data can't transition straight to "complete" (YouTube
    returns reason "invalidTransition") -- delete is the only way to
    clear it."""
    youtube = MagicMock()
    youtube.liveBroadcasts().transition().execute.side_effect = Exception("invalidTransition")

    results = end_live_broadcast.end_broadcasts(youtube, ["stuck-ready"])

    assert results == {"stuck-ready": True}
    youtube.liveBroadcasts().delete.assert_called_with(id="stuck-ready")


def test_end_broadcasts_reports_failure_without_stopping_others():
    youtube = MagicMock()
    youtube.liveBroadcasts().transition().execute.side_effect = Exception("boom")
    youtube.liveBroadcasts().delete().execute.side_effect = [Exception("still broken"), None]

    results = end_live_broadcast.end_broadcasts(youtube, ["bad", "good"])

    assert results == {"bad": False, "good": True}


def test_main_returns_zero_and_noop_when_nothing_active(monkeypatch, capsys):
    fake_youtube = MagicMock()
    fake_youtube.liveBroadcasts().list().execute.return_value = {"items": []}
    monkeypatch.setattr(end_live_broadcast, "get_youtube_service", lambda: fake_youtube)

    assert end_live_broadcast.main() == 0
    assert "nothing to end" in capsys.readouterr().out
    fake_youtube.liveBroadcasts().transition.assert_not_called()


def test_main_returns_zero_when_all_ends_succeed(monkeypatch):
    fake_youtube = MagicMock()
    fake_youtube.liveBroadcasts().list().execute.return_value = {
        "items": [{"id": "abc", "status": {"lifeCycleStatus": "live"}}]
    }
    monkeypatch.setattr(end_live_broadcast, "get_youtube_service", lambda: fake_youtube)

    assert end_live_broadcast.main() == 0


def test_main_returns_one_when_an_end_fails(monkeypatch):
    fake_youtube = MagicMock()
    fake_youtube.liveBroadcasts().list().execute.return_value = {
        "items": [{"id": "abc", "status": {"lifeCycleStatus": "live"}}]
    }
    fake_youtube.liveBroadcasts().transition().execute.side_effect = Exception("boom")
    fake_youtube.liveBroadcasts().delete().execute.side_effect = Exception("still broken")
    monkeypatch.setattr(end_live_broadcast, "get_youtube_service", lambda: fake_youtube)

    assert end_live_broadcast.main() == 1
