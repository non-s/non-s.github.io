from utils.visual_learning import build_visual_learning, visual_profile_key


def test_visual_profile_key_reads_primary_bucket():
    assert (
        visual_profile_key({"visual_ctr": {"profile": {"primary": "close_subject|feed_bright|high_contrast"}}})
        == "close_subject|feed_bright|high_contrast"
    )


def test_build_visual_learning_picks_supported_winner():
    out = build_visual_learning(
        [
            {
                "visual_profile": "close_subject|feed_bright|high_contrast",
                "growth_score": 200,
                "average_view_percentage": 70,
                "views": 1000,
                "visual_ctr_score": 85,
            },
            {
                "visual_profile": "close_subject|feed_bright|high_contrast",
                "growth_score": 220,
                "average_view_percentage": 72,
                "views": 1100,
                "visual_ctr_score": 88,
            },
            {
                "visual_profile": "weak_subject|dark_or_washed|flat_contrast",
                "growth_score": 80,
                "average_view_percentage": 40,
                "views": 300,
                "visual_ctr_score": 35,
            },
        ]
    )

    assert out["winner"] == "close_subject|feed_bright|high_contrast"
    assert out["profiles"][0]["mean_growth_score"] == 210


def test_build_visual_learning_does_not_lock_unknown_profile():
    out = build_visual_learning(
        [
            {"visual_profile": "unknown", "growth_score": 999},
            {"visual_profile": "unknown", "growth_score": 900},
        ]
    )

    assert out["winner"] == ""
