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
    early = build_early_performance([
        _marker("fast", 6, 1200),
        _marker("mature", 30, 6000),
        _marker("slow", 30, 400),
    ], now=now)

    fast = early["videos"]["fast"]

    assert fast["early_velocity_score"] > 0
    assert "pass_5000" in fast["breakout_probability"]
    assert early["top_velocity"][0]["video_id"] in {"fast", "mature"}


def test_acceleration_uses_snapshots_to_detect_second_wave():
    now = datetime(2026, 6, 10, 12, tzinfo=timezone.utc)
    previous = {
        "videos": {
            "wave": {
                "snapshots": [
                    {"at": "x", "age_hours": 24, "views": 1000, "likes": 10, "comments": 0, "subscribers": 0}
                ]
            }
        }
    }
    early = build_early_performance([_marker("wave", 30, 2200)], previous=previous, now=now)

    assert early["videos"]["wave"]["acceleration"]["state"] in {"accelerating", "second_wave"}


def test_winner_patterns_and_warning_are_actionable():
    now = datetime(2026, 6, 10, 12, tzinfo=timezone.utc)
    early = build_early_performance([
        _marker("winner", 12, 2500),
        _marker("dead", 30, 300, category="dogs", series="Pet Signals", story_format="single_fact"),
    ], now=now)

    patterns = build_winner_patterns(early)
    warning = build_early_warning(early)

    assert patterns["winning_categories"]["fungi"] >= 1
    assert warning["remake_candidates"][0]["video_id"] == "dead"
