from utils.trend_bridge import build_topic_candidates


def test_topic_candidates_expose_freshness_fields():
    rows = [
        {"topic": "Octopus skin", "source": "rss", "score": 70, "observed_at": "2026-06-10T00:00:00+00:00"},
        {"topic": "octopus skin", "source": "trends", "score": 85, "observed_at": "2026-06-11T00:00:00+00:00"},
    ]

    out = build_topic_candidates(rows)[0]

    assert out["signal_count"] == 2
    assert out["latest_observed_at"].startswith("2026-06-11")
    assert out["signal_window"] == "fresh"
    assert out["freshness_score"] == out["score"]
