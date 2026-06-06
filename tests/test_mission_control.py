"""Tests for the Wild Brief mission-control synthesis."""
from utils.mission_control import build_mission_control


def test_mission_control_prioritizes_viewer_requests_and_queue_risk():
    out = build_mission_control(
        latest={
            "learning_profile": {"winning_title_keywords": ["camouflage"]},
            "production_recommendations": {"hot_categories": ["ocean"]},
        },
        comments={
            "requested_animals": ["shark"],
            "content_prompts": ["Answer this viewer question: Can you do sharks?"],
        },
        queue={
            "pending": 10,
            "approved": 1,
            "states": {"cooldown_subject": 5},
        },
    )
    assert out["status"] == "action_required"
    assert out["priority_topics"][:3] == ["shark", "camouflage", "ocean"]
    assert out["next_tasks"][0]["priority"] == "high"


def test_mission_control_steady_when_no_risk():
    out = build_mission_control(
        latest={"production_recommendations": {"hot_categories": ["cats"]}},
        comments={},
        queue={"pending": 5, "approved": 4, "states": {}},
    )
    assert out["status"] == "steady"
    assert "cats" in out["priority_topics"]
