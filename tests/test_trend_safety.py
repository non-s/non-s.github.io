from utils.trend_safety import enrich_topics, score_topic


def test_trend_safety_flags_risky_topic():
    out = score_topic(
        {
            "trend_score": 80,
            "terms": ["attack", "viral"],
            "top_titles": ["Dog attack sparks public safety debate"],
        }
    )
    assert out["risk_score"] > 0
    assert out["posture"] == "handle_with_care"


def test_trend_safety_rewards_educational_opportunity():
    out = score_topic(
        {
            "trend_score": 80,
            "terms": ["rare", "sighting", "study"],
            "top_titles": ["Rare whale sighting helps researchers study behavior"],
        }
    )
    assert out["opportunity_score"] >= 70
    assert out["posture"] == "greenlight"


def test_enrich_topics_attaches_safety_payload():
    topics = enrich_topics(
        [
            {"animal": "dog", "trend_score": 30, "terms": ["attack"], "top_titles": ["dog attack"]},
            {"animal": "whale", "trend_score": 80, "terms": ["rare"], "top_titles": ["rare whale"]},
        ]
    )
    assert "trend_safety" in topics[0]
    assert topics[0]["animal"] == "whale"
