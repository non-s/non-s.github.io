from datetime import datetime, timedelta, timezone

from utils.early_performance import (
    build_early_performance,
    build_early_warning,
    build_winner_patterns,
)


def _marker(video_id: str, hours_old: float, views: int, **overrides):
    now = datetime(2026, 6, 10, 12, tzinfo=timezone.utc)
    marker = {
        "video_id": video_id,
        "title": "Mushrooms turn roots into signals",
        "hook": "Watch the roots before the forest changes.",
        "thumbnail_text": "ROOT SIGNAL",
        "cta_prompt": "Want more nature that feels like science fiction but is real?",
        "category": "fungi",
        "story_format": "hidden_network",
        "series": "Hidden Network",
        "uploaded_at": (now - timedelta(hours=hours_old)).isoformat(),
        "analytics": {
            "views": views,
            "likes": 20,
            "comments": 3,
            "subscribersGained": 2,
        },
    }
    marker.update(overrides)
    return marker


def test_early_performance_scores_velocity_and_breakout():
    now = datetime(2026, 6, 10, 12, tzinfo=timezone.utc)
    early = build_early_performance(
        [
            _marker("fast", 6, 1200),
            _marker("mature", 30, 6000),
            _marker("slow", 30, 400),
        ],
        now=now,
    )

    fast = early["videos"]["fast"]

    assert fast["early_velocity_score"] > 0
    assert "pass_5000" in fast["breakout_probability"]
    assert early["top_velocity"][0]["video_id"] in {"fast", "mature"}


def test_acceleration_uses_snapshots_to_detect_second_wave():
    now = datetime(2026, 6, 10, 12, tzinfo=timezone.utc)
    previous = {
        "videos": {
            "wave": {
                "snapshots": [{"at": "x", "age_hours": 24, "views": 1000, "likes": 10, "comments": 0, "subscribers": 0}]
            }
        }
    }
    early = build_early_performance([_marker("wave", 30, 2200)], previous=previous, now=now)

    assert early["videos"]["wave"]["acceleration"]["state"] in {"accelerating", "second_wave"}


def test_winner_patterns_and_warning_are_actionable():
    now = datetime(2026, 6, 10, 12, tzinfo=timezone.utc)
    previous = {
        "videos": {
            "winner": {
                "snapshots": [{"at": "x", "age_hours": 6, "views": 1400, "likes": 15, "comments": 2, "subscribers": 1}]
            },
            "dead": {
                "snapshots": [{"at": "x", "age_hours": 24, "views": 290, "likes": 4, "comments": 0, "subscribers": 0}]
            },
        }
    }
    early = build_early_performance(
        [
            _marker("winner", 12, 2500),
            _marker("dead", 30, 300, category="dogs", series="Pet Signals", story_format="single_fact"),
        ],
        previous=previous,
        now=now,
    )

    patterns = build_winner_patterns(early)
    warning = build_early_warning(early)

    assert patterns["winning_categories"]["fungi"] >= 1
    assert warning["remake_candidates"][0]["video_id"] == "dead"


def test_estimated_old_video_stays_on_low_confidence_watchlist():
    now = datetime(2026, 6, 10, 12, tzinfo=timezone.utc)
    early = build_early_performance(
        [
            _marker("old", 30, 300, category="dogs", series="Pet Signals", story_format="single_fact"),
        ],
        now=now,
    )

    warning = build_early_warning(early)

    assert warning["remake_candidates"] == []
    assert warning["risk_of_dying_early"] == []


def test_early_warning_repairs_malformed_breakout_before_sequence():
    now = datetime(2026, 6, 10, 12, tzinfo=timezone.utc)
    previous = {
        "videos": {
            "bad-title": {
                "snapshots": [{"at": "x", "age_hours": 24, "views": 4200, "likes": 20, "comments": 3, "subscribers": 1}]
            }
        }
    }
    early = build_early_performance(
        [
            _marker("bad-title", 30, 6000, title="Lions use their ears to use"),
        ],
        previous=previous,
        now=now,
    )

    warning = build_early_warning(early)

    assert all(item["video_id"] != "bad-title" for item in warning["sequence_candidates"])
    repair = next(item for item in warning["remake_candidates"] if item["video_id"] == "bad-title")
    assert repair["action"] == "repair title/package before scaling angle"
    assert "robotic_use_loop" in repair["title_issues"]
