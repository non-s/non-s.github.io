from utils.scale_blueprint import build_scale_blueprint, classify_video_action, studio_baseline


def _objective():
    return {
        "baseline": {
            "views": 30314,
            "engaged_views": 10500,
            "subscribers_gained": 37,
            "total_subscribers": 46,
            "monthly_audience": 9800,
            "stayed_to_watch_rate": 0.318,
            "swipe_away_rate": 0.682,
            "new_viewer_rate": 0.998,
            "casual_viewer_rate": 0.002,
            "recurring_viewer_rate_upper_bound": 0.001,
            "shorts_feed_view_rate": 0.962,
            "youtube_search_view_rate": 0.017,
            "mobile_watch_time_rate": 0.813,
        },
        "targets": {
            "stayed_to_watch_floor": 0.4,
            "recurring_viewer_rate_floor": 0.02,
            "subs_per_1000_views_floor": 1.5,
        },
    }


def _latest():
    return {
        "total_views": 24940,
        "subscribers_gained": 37,
        "avg_view_percentage": 59.5,
        "shorts_tracked": 37,
        "category_avg_view_pct": {"farm": 66.4, "wildlife": 58.2},
        "category_avg_growth_score": {"farm": 240, "wildlife": 172},
        "top_performers": [
            {
                "video_id": "winner",
                "title": "Chickens have another signal hiding in plain sight",
                "views": 1930,
                "view_pct": 80.33,
                "subscribers_gained": 1,
                "views_per_hour": 18,
            },
            {
                "video_id": "leaky",
                "title": "Baby goats love bottle feeding",
                "views": 1957,
                "view_pct": 35.65,
                "subscribers_gained": 0,
                "views_per_hour": 8,
            },
        ],
    }


def test_studio_baseline_prefers_operator_snapshot():
    out = studio_baseline(_latest(), _objective(), {})

    assert out["views"] == 30314
    assert out["engaged_view_rate"] == 0.3464
    assert out["subs_per_1000_views"] == 1.221
    assert out["mobile_watch_time_rate"] == 0.813


def test_classify_video_action_splits_sequel_and_remake():
    winner = classify_video_action(_latest()["top_performers"][0])
    leaky = classify_video_action(_latest()["top_performers"][1])

    assert winner["action"] == "make_sequel_now"
    assert leaky["action"] == "remake_opening"


def test_build_scale_blueprint_flags_real_channel_bottlenecks():
    out = build_scale_blueprint(
        latest=_latest(),
        channel_success={"audience_loop": {"state": "blind_spot"}},
        objective=_objective(),
        queue_audit={"mechanism_clusters": {"ear_signal": 4}},
        next_shorts={"items": [{"category": "farm"}, {"category": "wildlife"}]},
    )

    assert out["phase"] == "discovery_spike_to_loyalty"
    assert out["dashboard_summary"]["top_bottleneck"] == "first_second"
    assert any(item["id"] == "recurring_audience" for item in out["bottlenecks"])
    assert any("frame-zero" in command for command in out["production_commands"])
    assert out["series_lanes"][0]["lane"] == "Farmyard Minds"
