"""Tests for free public YouTube performance snapshots."""
from scripts.analyze_channel import _engagement_score, build_snapshot


def test_engagement_score_weights_comments():
    assert _engagement_score({"viewCount": "100", "likeCount": "10", "commentCount": "5"}) == 20


def test_snapshot_aggregates_series_and_experiments():
    markers = [{
        "video_id": "abc",
        "title": "Octopus",
        "url": "https://youtube.com/shorts/abc",
        "category": "ocean",
        "series": "Ocean Mysteries",
        "hook": "Octopuses use tools.",
        "experiments": {"hook_style": "outcome_first"},
    }]
    stats = {"abc": {"statistics": {"viewCount": "200", "likeCount": "20", "commentCount": "5"}}}
    snapshot, observations = build_snapshot(markers, stats)
    assert snapshot["total_views"] == 200
    assert snapshot["shorts_tracked"] == 1
    assert snapshot["series_avg_engagement"]["Ocean Mysteries"] == 15
    assert snapshot["category_avg_growth_score"]["ocean"] > 0
    assert snapshot["format_avg_growth_score"]["animal_intelligence"] > 0
    assert snapshot["production_recommendations"]["hot_categories"] == ["ocean"]
    assert snapshot["production_recommendations"]["hot_formats"] == ["animal_intelligence"]
    assert observations[0]["experiments"]["hook_style"] == "outcome_first"
    assert observations[0]["growth_score"] > 0
    assert observations[0]["story_format"] == "animal_intelligence"


def test_snapshot_includes_optional_retention_metrics():
    markers = [{"video_id": "abc", "category": "ocean", "series": "Ocean Mysteries"}]
    stats = {"abc": {"statistics": {"viewCount": "100", "likeCount": "5"}}}
    retention = {"abc": {
        "averageViewPercentage": 82.5,
        "averageViewDuration": 24.3,
        "subscribersGained": 7,
    }}
    snapshot, observations = build_snapshot(markers, stats, retention)
    assert snapshot["avg_view_percentage"] == 82.5
    assert snapshot["avg_view_pct"] == 82.5
    assert snapshot["avg_engagement_score"] == 5
    assert snapshot["subscribers_gained"] == 7
    assert snapshot["category_avg_view_pct"]["ocean"] == 82.5
    assert snapshot["below_60_pct"] == []
    assert snapshot["top_performers"][0]["view_pct"] == 82.5
    assert snapshot["top_performers"][0]["growth_score"] > 0
    assert observations[0]["score"] == observations[0]["growth_score"]
    assert observations[0]["subscribers_gained"] == 7


def test_snapshot_tracks_below_sixty_percent_retention():
    markers = [{"video_id": "abc", "category": "cats"}]
    stats = {"abc": {"statistics": {"viewCount": "50"}}}
    retention = {"abc": {"averageViewPercentage": 42.0}}
    snapshot, _ = build_snapshot(markers, stats, retention)
    assert snapshot["below_60_pct"] == ["abc"]
