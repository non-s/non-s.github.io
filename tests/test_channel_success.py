from utils.channel_success import (
    audience_loop,
    build_success_plan,
    first_24h_engine,
    retention_command_center,
    series_system,
    audience_recurrence_engine,
    studio_reach_engine,
    subscriber_engine,
)


def _latest():
    return {
        "total_views": 10000,
        "subscribers_gained": 5,
        "avg_view_pct": 52.5,
        "shorts_tracked": 19,
        "below_60_pct": [{"title": "Weak hook"}],
        "category_avg_view_pct": {"birds": 72, "cats": 37, "farm": 55},
        "category_avg_growth_score": {"farm": 240, "birds": 210, "cats": 90},
        "series_avg_engagement": {"Sky Intelligence": 80},
        "top_performers": [{
            "video_id": "abc",
            "title": "Chickens remember faces",
            "views": 1000,
            "views_per_hour": 45,
            "growth_score": 250,
            "view_pct": 64,
        }, {
            "video_id": "def",
            "title": "Cats land quietly",
            "views": 500,
            "growth_score": 120,
            "view_pct": 38,
        }],
    }


def test_retention_command_center_splits_categories():
    out = retention_command_center(_latest(), {"repeated_phrases": {"secret": 8}})
    assert out["state"] == "needs_retention_work"
    assert out["scale_categories"][0]["category"] == "birds"
    assert out["recovery_categories"][0]["category"] == "cats"
    assert out["phrase_pressure"][0]["phrase"] == "secret"


def test_subscriber_engine_uses_per_1000_target():
    out = subscriber_engine({"total_views": 10000, "subscribers_gained": 5})
    assert out["subs_per_1000_views"] == 0.5
    assert out["state"] == "needs_conversion_work"
    assert out["commands"]


def test_audience_loop_has_fallback_when_no_comments():
    out = audience_loop({"comments_sampled": 0})
    assert out["state"] == "blind_spot"
    assert any("animal" in prompt.lower() for prompt in out["prompts"])


def test_first_24h_engine_splits_winners_and_reworks():
    out = first_24h_engine(_latest())
    assert out["state"] == "winner_found"
    assert out["winners"][0]["video_id"] == "abc"
    assert out["rework"][0]["video_id"] == "def"


def test_first_24h_engine_reworks_malformed_metric_winners():
    latest = _latest()
    latest["top_performers"] = [{
        "video_id": "bad",
        "title": "Lions use their ears to use",
        "views": 2000,
        "views_per_hour": 80,
        "growth_score": 300,
        "view_pct": 70,
    }]

    out = first_24h_engine(latest)

    assert out["winners"] == []
    assert out["rework"][0]["video_id"] == "bad"
    assert out["rework"][0]["rework_reason"] == "repair title/package before scaling"
    assert "robotic_use_loop" in out["rework"][0]["title_issues"]


def test_series_system_marks_paused_lanes_as_recovery():
    out = series_system(_latest(), {"paused_topics": [{"category": "cats"}]})
    pet_lane = next(item for item in out["lanes"] if item["series"] == "Pet Signals")
    assert pet_lane["state"] == "recovery"


def test_build_success_plan_returns_operating_actions():
    out = build_success_plan(
        latest=_latest(),
        comments={"comments_sampled": 0},
        health={"score": 92},
        autonomous={"quota_budget": {"state": "watch"}},
        fact_ledger={"risk_score": 100, "repeated_phrases": {"secret": 8}},
        ops={"paused_topics": [{"category": "cats"}]},
    )
    assert out["state"] == "growth_building"
    assert out["success_score"] < 80
    assert out["retention"]["gap_to_floor"] > 0
    assert out["studio_reach"]["state"] == "needs_first_second_work"
    assert out["audience_recurrence"]["state"] == "needs_recurrence_work"
    assert out["next_actions"]


def test_studio_reach_engine_uses_operator_baseline_when_import_is_empty():
    objective = {
        "baseline": {"stayed_to_watch_rate": 0.318, "swipe_away_rate": 0.682},
        "targets": {"stayed_to_watch_floor": 0.4, "swipe_away_ceiling": 0.6},
    }

    out = studio_reach_engine({"summary": {"rows": 0, "stayed_to_watch_rate": 0}}, objective)

    assert out["source"] == "operator_baseline"
    assert out["stayed_to_watch_rate"] == 0.318
    assert out["state"] == "needs_first_second_work"


def test_audience_recurrence_engine_flags_new_viewer_leak():
    objective = {
        "baseline": {
            "monthly_audience": 9800,
            "subscribers_gained": 37,
            "new_viewer_rate": 0.998,
            "recurring_viewer_rate_upper_bound": 0.001,
        },
        "targets": {
            "new_viewer_subscribe_rate_floor": 0.005,
            "recurring_viewer_rate_floor": 0.02,
        },
    }

    out = audience_recurrence_engine(objective)

    assert out["new_viewer_subscribe_rate"] < out["new_viewer_subscribe_rate_floor"]
    assert out["recurring_viewer_rate"] < out["recurring_viewer_rate_floor"]
    assert "follow for one animal signal" in " ".join(out["commands"]).lower()

