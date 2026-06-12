import json

from scripts.weekly_growth_review import build_review


def test_weekly_growth_review_includes_reach_summary(tmp_path):
    analytics = tmp_path / "_data" / "analytics"
    analytics.mkdir(parents=True)
    next_shorts = tmp_path / "_data" / "next_shorts.json"
    next_shorts.write_text(json.dumps({"items": [{"id": "keep"}]}), encoding="utf-8")
    (analytics / "video_metrics.jsonl").write_text(
        json.dumps(
            {
                "pulled_at": "2026-06-10",
                "video_id": "abc",
                "title": "Octopus",
                "category": "ocean",
                "format": "mechanism",
                "metrics": {"average_view_percentage": 70, "views": 100, "engaged_views": 80},
                "derived": {"replay_rate_proxy": 0.2},
                "variants": {"loop_style": "callback"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (analytics / "studio_reach_daily.jsonl").write_text(
        json.dumps(
            {
                "row_type": "studio_reach_daily",
                "video_id": "abc",
                "title": "Octopus",
                "metrics": {"views": 100, "stayed_to_watch": 70, "swiped_away": 30, "stayed_to_watch_rate": 0.7},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    review = build_review(tmp_path)

    assert review["reach_summary"]["stayed_to_watch_rate"] == 0.7
    assert review["reach_goal"]["state"] == "healthy"
    assert (analytics / "weekly_summary.json").exists()
    assert (analytics / "weekly_next_recommendations.json").exists()
    assert json.loads(next_shorts.read_text(encoding="utf-8"))["items"][0]["id"] == "keep"
    assert "Shorts Reach" in next((tmp_path / "_data" / "reports").glob("weekly-growth-*.md")).read_text()
