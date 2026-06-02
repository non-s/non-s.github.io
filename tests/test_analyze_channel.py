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
        "experiments": {"hook_style": "outcome_first"},
    }]
    stats = {"abc": {"statistics": {"viewCount": "200", "likeCount": "20", "commentCount": "5"}}}
    snapshot, observations = build_snapshot(markers, stats)
    assert snapshot["total_views"] == 200
    assert snapshot["shorts_tracked"] == 1
    assert snapshot["series_avg_engagement"]["Ocean Mysteries"] == 15
    assert observations[0]["experiments"]["hook_style"] == "outcome_first"
