from datetime import datetime, timedelta, timezone

from utils.fresh_upload_sentinel import build_fresh_upload_watchlist

NOW = datetime(2026, 6, 10, 12, tzinfo=timezone.utc)


def _marker(video_id: str, hours_old: float, **overrides):
    marker = {
        "video_id": video_id,
        "title": "Mushrooms release spores from hidden gills",
        "category": "fungi",
        "series": "Hidden Network",
        "uploaded_at": (NOW - timedelta(hours=hours_old)).isoformat(),
        "publish_score": {
            "opening_retention": {
                "score": 100,
                "state": "retention_ready",
            }
        },
    }
    marker.update(overrides)
    return marker


def _early_row(video_id: str, age_hours: float, views: int):
    return {
        "video_id": video_id,
        "title": "Mushrooms release spores from hidden gills",
        "age_hours": age_hours,
        "views": views,
        "views_per_hour": views / max(age_hours, 1),
        "checkpoints": {
            "1h": {"views": {"value": min(views, 5), "source": "estimated", "age_hours": age_hours}},
            "6h": {"views": {"value": views, "source": "estimated", "age_hours": age_hours}},
            "24h": {"views": {"value": views, "source": "estimated", "age_hours": age_hours}},
        },
    }


def test_fresh_upload_waits_for_first_hour_before_intervention():
    payload = build_fresh_upload_watchlist([_marker("fresh", 0.5)], now=NOW)

    item = payload["items"][0]

    assert item["state"] == "awaiting_1h"
    assert item["priority"] == "low"
    assert item["next_checkpoint"]["label"] == "1h"
    assert item["next_checkpoint"]["state"] == "pending"


def test_fresh_upload_due_checkpoint_requests_analytics_pull():
    payload = build_fresh_upload_watchlist(
        [_marker("due", 1.25)],
        early_performance={"videos": {"due": _early_row("due", 1.25, 0)}},
        now=NOW,
    )

    item = payload["items"][0]

    assert item["state"] == "analytics_due"
    assert item["priority"] == "high"
    assert item["next_checkpoint"]["state"] == "due"


def test_warning_signal_becomes_repair_candidate():
    payload = build_fresh_upload_watchlist(
        [_marker("risk", 8)],
        early_performance={"videos": {"risk": _early_row("risk", 8, 10)}},
        early_warning={
            "risk_of_dying_early": [
                {
                    "video_id": "risk",
                    "title": "Mushrooms release spores from hidden gills",
                    "action": "TITLE_AUTO_REPAIR_TRIGGER",
                }
            ]
        },
        now=NOW,
    )

    item = payload["items"][0]

    assert item["state"] == "repair_candidate"
    assert item["action"] == "TITLE_AUTO_REPAIR_TRIGGER"
    assert payload["counts"]["repair_candidates"] == 1


def test_old_uploads_drop_outside_watch_window():
    payload = build_fresh_upload_watchlist([_marker("old", 100)], now=NOW)

    assert payload["items"] == []
    assert payload["counts"]["tracked"] == 0
