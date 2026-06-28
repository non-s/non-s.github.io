from datetime import datetime, timezone

from utils.fresh_upload_actions import build_fresh_upload_actions

NOW = datetime(2026, 6, 10, 12, tzinfo=timezone.utc)


def _watch_item(video_id: str, state: str, checkpoint_state: str, **overrides):
    item = {
        "video_id": video_id,
        "title": "Mushrooms release spores from hidden gills",
        "url": f"https://www.youtube.com/shorts/{video_id}",
        "state": state,
        "priority": "high" if state in {"analytics_due", "repair_candidate"} else "low",
        "age_hours": 1.25,
        "current_views": 5,
        "opening_retention_score": 100,
        "next_checkpoint": {
            "label": "1h",
            "state": checkpoint_state,
            "due_at": "2026-06-10T11:00:00+00:00",
            "target_views": 20,
        },
        "action": "Run the analytics pull before making a creative decision.",
        "hypothesis": "The next checkpoint is due, but the system still needs a fresh measured sample.",
    }
    item.update(overrides)
    return item


def test_fresh_upload_actions_prioritizes_due_measurement_before_watch():
    payload = build_fresh_upload_actions(
        {
            "generated_at": NOW.isoformat(),
            "items": [
                _watch_item("watch", "awaiting_1h", "pending", priority="low"),
                _watch_item("due", "analytics_due", "due"),
            ],
        },
        now=NOW,
    )

    first = payload["items"][0]

    assert payload["free_only"] is True
    assert first["video_id"] == "due"
    assert first["lane"] == "measurement"
    assert first["automation_safe"] is True
    assert "Check the 1h sample first" in first["recommended_action"]


def test_overdue_checkpoint_becomes_urgent():
    payload = build_fresh_upload_actions(
        {"items": [_watch_item("overdue", "analytics_due", "overdue")]},
        now=NOW,
    )

    action = payload["items"][0]

    assert action["priority"] == "urgent"
    assert payload["counts"]["urgent"] == 1


def test_repair_candidate_requires_manual_review_and_uses_sentinel_action():
    payload = build_fresh_upload_actions(
        {
            "items": [
                _watch_item(
                    "repair",
                    "repair_candidate",
                    "observed",
                    action="TITLE_AUTO_REPAIR_TRIGGER",
                    hypothesis="Observed velocity is weak enough to prepare a package intervention.",
                )
            ]
        },
        now=NOW,
    )

    action = payload["items"][0]

    assert action["lane"] == "package_rescue"
    assert action["recommended_action"] == "TITLE_AUTO_REPAIR_TRIGGER"
    assert action["manual_approval_required"] is True
    assert payload["counts"]["manual_review"] == 1


def test_action_builder_survives_malformed_numeric_fields():
    payload = build_fresh_upload_actions(
        {
            "items": [
                _watch_item(
                    "messy",
                    "watch",
                    "pending",
                    age_hours="",
                    current_views="not-a-number",
                    opening_retention_score=None,
                    next_checkpoint={
                        "label": "6h",
                        "state": "pending",
                        "due_at": "2026-06-10T18:00:00+00:00",
                        "target_views": "unknown",
                    },
                )
            ]
        },
        now=NOW,
    )

    action = payload["items"][0]

    assert action["age_hours"] == 0
    assert action["current_views"] == 0
    assert action["target_views"] == 0
