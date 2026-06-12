from datetime import datetime, timezone

from utils.content_agency import agency_score, agency_snapshot, rank_for_agency


def _story(**overrides):
    base = {
        "title": "Dogs remember faces after one meeting",
        "hook": "Dogs remember your face after one meeting.",
        "script": (
            "Dogs remember your face after one meeting. Their eyes track "
            "small gestures, and familiar voices can calm them quickly."
        ),
        "category": "dogs",
        "score": 9,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "story_format": "animal_memory",
        "editorial": {
            "approved": True,
            "score": 84,
            "humanity": {"score": 90},
        },
        "trend_context": {
            "animal": "dog",
            "trend_score": 86,
            "mentions": 4,
        },
        "hook_audit": {"score": 90},
        "title_audit": {"score": 88},
    }
    base.update(overrides)
    return base


def test_agency_score_rewards_quality_trend_and_learning():
    strong = _story()
    weak = _story(
        category="cats",
        score=4,
        editorial={"approved": False, "score": 48, "humanity": {"score": 45}},
        trend_context={},
    )
    strategy = {
        "category_weights": {"dogs": 1.6, "cats": 0.7},
        "format_weights": {"animal_memory": 1.4},
        "exploit_keywords": ["dogs"],
    }
    assert agency_score(strong, strategy=strategy)["score"] > agency_score(weak, strategy=strategy)["score"]
    assert agency_score(strong, strategy=strategy)["decision"] in {
        "publish_now",
        "strong_candidate",
    }


def test_rank_for_agency_attaches_decision_and_sorts():
    candidates = [
        _story(title="Cats sleep through danger", category="cats", trend_context={}),
        _story(title="Dogs remember faces after one meeting", category="dogs"),
    ]
    ranked = rank_for_agency(
        candidates,
        {
            "category_weights": {"dogs": 1.8, "cats": 0.5},
            "format_weights": {"animal_memory": 1.2},
        },
    )
    assert ranked[0]["category"] == "dogs"
    assert "agency" in ranked[0]
    assert ranked[0]["agency"]["score"] >= ranked[1]["agency"]["score"]


def test_agency_snapshot_summarises_queue():
    snap = agency_snapshot([_story(), _story(category="ocean", trend_context={})])
    assert snap["average_score"] > 0
    assert snap["top"]
    assert sum(snap["decisions"].values()) == 2
