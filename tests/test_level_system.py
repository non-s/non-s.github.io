from utils.level_system import build_level_system


def test_level_system_identifies_final_publish_supply_boss():
    payload = build_level_system(
        health={
            "score": 67,
            "state": "needs_work",
            "queue": {
                "pending": 11,
                "publish_ready": 0,
                "held_reasons": {
                    "queue_prune:rewrite": 10,
                    "packaging:missing_visible_cue": 5,
                },
            },
        },
        dry_run={
            "eligible_count": 0,
            "objective_reasons": {"agency_gate:success_recovery_hook_required": 4},
        },
        next_shorts={"items": [], "editorial_mix": {"items": [{"id": "strong"}]}},
        queue_audit={"pending": 11, "states": {"publish_ready": 1}},
        scale_blueprint={
            "baseline": {
                "views": 30314,
                "stayed_to_watch_rate": 0.318,
                "avg_view_percentage": 57.0,
            }
        },
        upload_intents=[{"status": "uploaded", "video_id": "abc123"}],
    )

    assert payload["current_level"]["number"] == 2
    assert payload["current_level"]["name"] == "Publish supply engine"
    assert payload["boss"]["id"] == "final_publish_supply_empty"
    assert payload["next_upgrade"]["free_only"] is True
    assert payload["metrics"]["apparent_publish_ready"] == 1
    assert payload["metrics"]["operational_publish_ready"] == 0
    assert payload["action_plan"][0]["priority"] == "P0"


def test_level_system_does_not_relock_launch_after_successful_uploads():
    payload = build_level_system(
        health={
            "score": 55,
            "state": "needs_work",
            "queue": {"pending": 10, "publish_ready": 0, "held_reasons": {"queue_prune:rewrite": 8}},
        },
        dry_run={"eligible_count": 1, "scale_ready_count": 0},
        next_shorts={"items": [], "editorial_mix": {"items": []}},
        queue_audit={"pending": 10, "states": {"publish_ready": 2}},
        scale_blueprint={"baseline": {"views": 30314, "stayed_to_watch_rate": 0.318, "avg_view_percentage": 57.0}},
        upload_intents=[{"status": "uploaded", "video_id": "abc123"}],
    )

    assert payload["current_level"]["number"] == 2
    assert payload["boss"]["id"] == "publish_ready_reserve_low"


def test_level_system_advances_after_supply_and_retention_are_cleared():
    payload = build_level_system(
        health={
            "score": 95,
            "state": "excellent",
            "queue": {"pending": 24, "publish_ready": 6, "held_reasons": {}},
            "comments": {"comments_sampled": 44},
        },
        dry_run={"eligible_count": 2, "scale_ready_count": 1},
        next_shorts={"items": [{"id": "a"}, {"id": "b"}]},
        queue_audit={"pending": 24, "states": {"publish_ready": 6}},
        scale_blueprint={
            "baseline": {
                "views": 60000,
                "stayed_to_watch_rate": 0.44,
                "avg_view_percentage": 66.0,
                "recurring_viewer_rate": 0.025,
                "youtube_search_view_rate": 0.06,
                "total_subscribers": 120,
                "subs_per_1000_views": 1.8,
            }
        },
        crosspost_pack={"items": [{"id": "x"}, {"id": "y"}, {"id": "z"}]},
        upload_intents=[{"status": "uploaded", "video_id": "abc123"}],
    )

    assert payload["current_level"]["number"] == 6
    assert payload["boss"]["id"] == "monetization_runway_gap"
    assert payload["levels"][1]["status"] == "cleared"
    assert payload["levels"][4]["status"] == "cleared"
