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


def test_mission_control_sanitizes_bad_learning_keywords_and_review_titles():
    out = build_mission_control(
        latest={
            "learning_profile": {
                "winning_title_keywords": ["chickens", "another", "signal", "hiding", "plain", "sight", "ducks"],
            },
            "top_performers": [
                {
                    "video_id": "bad",
                    "title": "Chickens have another signal hiding in plain sight",
                },
                {
                    "video_id": "good",
                    "title": "Chickens remember faces and hold grudges",
                },
                {
                    "video_id": "duck",
                    "title": "Mallard ducks fake injuries to trick predators",
                },
            ],
        },
        comments={},
        queue={"pending": 5, "approved": 4, "states": {}},
    )

    assert "chickens" in out["priority_topics"]
    assert "ducks" in out["priority_topics"]
    assert "hiding" not in out["priority_topics"]
    assert out["review_queue"][0]["title"] == "bad (title needs repair: generic_hiding_plain_sight)"
    assert out["review_queue"][0]["title_issues"] == ["generic_hiding_plain_sight"]
