"""Tests for free public YouTube performance snapshots."""

from scripts.analyze_channel import _engagement_score, build_snapshot


def test_engagement_score_weights_comments():
    assert _engagement_score({"viewCount": "100", "likeCount": "10", "commentCount": "5"}) == 20


def test_snapshot_aggregates_series_and_experiments():
    markers = [
        {
            "video_id": "abc",
            "title": "Octopus",
            "url": "https://youtube.com/shorts/abc",
            "category": "ocean",
            "series": "Ocean Mysteries",
            "hook": "Octopuses use tools.",
            "experiments": {"hook_style": "outcome_first"},
            "narrator_voice": "en-US-JennyNeural",
            "humanity": {"score": 81, "label": "human"},
            "studio_polish": {"applied": True},
            "studio_state": "polished",
        }
    ]
    stats = {"abc": {"statistics": {"viewCount": "200", "likeCount": "20", "commentCount": "5"}}}
    snapshot, observations = build_snapshot(markers, stats)
    assert snapshot["total_views"] == 200
    assert snapshot["shorts_tracked"] == 1
    assert snapshot["series_avg_engagement"]["Ocean Mysteries"] == 15
    assert snapshot["category_avg_growth_score"]["ocean"] > 0
    assert snapshot["format_avg_growth_score"]["animal_intelligence"] > 0
    assert snapshot["avg_humanity_score"] == 81
    assert snapshot["humanity_label_counts"] == {"human": 1}
    assert snapshot["studio_polished_count"] == 1
    assert snapshot["studio_state_counts"] == {"polished": 1}
    assert snapshot["top_performers"][0]["humanity_label"] == "human"
    assert snapshot["top_performers"][0]["studio_polished"] is True
    assert snapshot["production_recommendations"]["hot_categories"] == ["ocean"]
    assert snapshot["production_recommendations"]["hot_formats"] == ["animal_intelligence"]
    assert snapshot["learning_profile"]["winning_categories"] == ["ocean"]
    assert "animal_intelligence" in snapshot["learning_profile"]["winning_formats"]
    assert snapshot["production_recommendations"]["learning_profile"]["winning_categories"] == ["ocean"]
    assert snapshot["performance_matrix"]["category"]["ocean"]["n"] == 1
    assert snapshot["winner_loser_map"]["winners"]["category"]["value"] == "ocean"
    assert snapshot["weekly_brief"]["best_category"] == "ocean"
    assert snapshot["production_recommendations"]["production_mix"]["exploit"] >= 50
    assert observations[0]["experiments"]["hook_style"] == "outcome_first"
    assert observations[0]["narrator_voice"] == "en-US-JennyNeural"
    assert observations[0]["growth_score"] > 0
    assert observations[0]["story_format"] == "animal_intelligence"
    assert observations[0]["humanity_score"] == 81


def test_snapshot_includes_optional_retention_metrics():
    markers = [{"video_id": "abc", "category": "ocean", "series": "Ocean Mysteries"}]
    stats = {"abc": {"statistics": {"viewCount": "100", "likeCount": "5"}}}
    retention = {
        "abc": {
            "averageViewPercentage": 82.5,
            "averageViewDuration": 24.3,
            "subscribersGained": 7,
        }
    }
    snapshot, observations = build_snapshot(markers, stats, retention)
    assert snapshot["avg_view_percentage"] == 82.5
    assert snapshot["avg_view_pct"] == 82.5
    assert snapshot["avg_engagement_score"] == 5
    assert snapshot["subscribers_gained"] == 7
    assert snapshot["category_avg_view_pct"]["ocean"] == 82.5
    assert snapshot["below_60_pct"] == []
    assert snapshot["below_62_pct"] == []
    assert snapshot["top_performers"][0]["view_pct"] == 82.5
    assert snapshot["top_performers"][0]["growth_score"] > 0
    assert observations[0]["score"] == observations[0]["growth_score"]
    assert observations[0]["subscribers_gained"] == 7
    assert observations[0]["retention_tier"] == "excellent"
    assert snapshot["learning_profile"]["retention_tiers"]["excellent"] == 1
    assert snapshot["remake_candidates"][0]["action"].startswith("remake")


def test_snapshot_tracks_below_sixty_percent_retention():
    markers = [{"video_id": "abc", "category": "cats"}]
    stats = {"abc": {"statistics": {"viewCount": "50"}}}
    retention = {"abc": {"averageViewPercentage": 42.0}}
    snapshot, _ = build_snapshot(markers, stats, retention)
    assert snapshot["below_60_pct"] == ["abc"]
    assert snapshot["below_62_pct"] == ["abc"]
    assert snapshot["learning_profile"]["avoid_repeating_video_ids"] == ["abc"]


def test_snapshot_does_not_recommend_malformed_top_titles():
    markers = [
        {"video_id": "bad1", "title": "Lions use their ears to use", "category": "wildlife"},
        {"video_id": "bad2", "title": "Birds This black bird's ear tufts aren't ears at all", "category": "birds"},
        {"video_id": "good", "title": "Dolphins recognize signals through call", "category": "ocean"},
    ]
    stats = {
        "bad1": {"statistics": {"viewCount": "500", "likeCount": "50"}},
        "bad2": {"statistics": {"viewCount": "400", "likeCount": "40"}},
        "good": {"statistics": {"viewCount": "300", "likeCount": "30"}},
    }

    snapshot, _ = build_snapshot(markers, stats)
    recs = snapshot["production_recommendations"]

    assert "Lions use their ears to use" not in recs["double_down_titles"]
    assert "Birds This black bird's ear tufts aren't ears at all" not in recs["double_down_titles"]
    assert recs["double_down_titles"] == ["Dolphins recognize signals through call"]
    assert "lions" not in recs["exploit_keywords"]
    assert "dolphins" in recs["exploit_keywords"]
    assert "lions" not in snapshot["learning_profile"]["winning_title_keywords"]
    assert "dolphins" in snapshot["learning_profile"]["winning_title_keywords"]
