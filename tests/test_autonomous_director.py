from utils.autonomous_director import (
    append_sequels,
    build_director,
    build_sequel_story,
    quota_budget,
    sequel_candidates,
    subscriber_conversion,
    traffic_source_insight,
)


def _latest():
    return {
        "total_views": 2000,
        "subscribers_gained": 4,
        "category_avg_growth_score": {"farm": 400, "birds": 120},
        "format_avg_growth_score": {"animal_memory": 300, "single_fact": 100},
        "top_performers": [{
            "video_id": "abc",
            "title": "Ducklings know math before they can swim",
            "views": 1200,
            "growth_score": 500,
            "category": "farm",
            "story_format": "animal_memory",
        }],
    }


def test_subscriber_conversion_scores_per_1000_views():
    out = subscriber_conversion({"total_views": 2000, "subscribers_gained": 4})
    assert out["subs_per_1000_views"] == 2.0
    assert out["state"] == "strong"


def test_traffic_source_insight_reads_ok_report():
    out = traffic_source_insight({
        "analytics_reports": [{
            "id": "traffic_source",
            "status": "ok",
            "sample": [
                {"insightTrafficSourceType": "YT_SHORTS", "views": 100},
                {"insightTrafficSourceType": "SEARCH", "views": 10},
            ],
        }]
    })
    assert out["state"] == "ready"
    assert out["dominant_source"] == "YT_SHORTS"


def test_quota_budget_warns_on_missing_token():
    out = quota_budget({
        "coverage_score": 40,
        "issues": ["youtube_token_missing"],
        "analytics_reports": [{"id": "country", "status": "not_authorized"}],
    })
    assert out["state"] == "watch"
    assert out["risk_score"] >= 35


def test_sequel_factory_builds_and_dedupes():
    candidates = sequel_candidates(_latest())
    assert candidates[0]["source_video_id"] == "abc"
    story = build_sequel_story(candidates[0])
    assert story["id"].startswith("sequel-")
    assert story["sequel_of"]["video_id"] == "abc"
    assert "hiding in plain sight" not in story["seo_title"].lower()
    updated, created = append_sequels({"stories": []}, candidates)
    assert len(created) == 1
    updated2, created2 = append_sequels(updated, candidates)
    assert len(created2) == 0
    assert len(updated2["stories"]) == 1


def test_build_director_makes_operating_decisions():
    director = build_director(
        latest=_latest(),
        youtube_intelligence={
            "coverage_score": 80,
            "issues": [],
            "analytics_reports": [{
                "id": "traffic_source",
                "status": "ok",
                "sample": [{"insightTrafficSourceType": "YT_SHORTS", "views": 100}],
            }],
        },
        health={"score": 100},
        ops={"paused_topics": [{"category": "cats"}]},
        fact_ledger={"risk_score": 20},
    )
    assert director["state"] == "autonomous_ready"
    assert director["category_priorities"][0]["value"] == "farm"
    assert director["sequel_candidates"]
    assert any("Double down" in item for item in director["decisions"])
