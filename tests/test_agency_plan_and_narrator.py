from utils.agency_plan import build_plan
from utils.narrator_optimizer import category_voice_hint, narrator_report


def test_agency_plan_builds_seven_days():
    plan = build_plan(
        latest={"avg_view_pct": 55, "production_recommendations": {"hot_categories": ["farm", "birds"]}},
        health={"agency": {"decisions": {"publish_now": 30}}},
        ops={"paused_topics": [{"category": "cats"}]},
        trend={
            "topics": [
                {"category": "cats", "animal": "cat", "trend_safety": {"posture": "greenlight"}},
                {"category": "ocean", "animal": "whale", "trend_safety": {"posture": "greenlight"}},
            ]
        },
    )
    assert len(plan["days"]) == 7
    assert plan["status"] == "aggressive_growth"
    assert plan["days"][0]["avoid"] == ["cats"]
    assert plan["days"][0]["trend_category"] == "ocean"
    assert plan["days"][0]["trend_animal"] == "whale"
    assert plan["blocked_trends"] == [{"category": "cats", "animal": "cat", "reason": "paused_category"}]
    assert all(day["focus"] != "cats" for day in plan["days"])


def test_narrator_report_picks_winner_with_samples():
    report = narrator_report(
        [
            {"narrator_voice": "aria", "growth_score": 100, "view_pct": 70},
            {"narrator_voice": "aria", "growth_score": 120, "view_pct": 80},
            {"narrator_voice": "guy", "growth_score": 40, "view_pct": 50},
        ]
    )
    assert report["winner"] == "aria"
    assert category_voice_hint("ocean", report) == "aria"


def test_category_voice_hint_has_defaults():
    assert category_voice_hint("primates", {}) == "guy"
