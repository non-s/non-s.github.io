from utils.growth_strategy import (
    category_weights,
    is_paused_category,
    ops_guardian_enforced,
    paused_categories,
    rank_for_growth,
    score_story,
)


def test_category_weights_are_bounded():
    weights = category_weights({"category_weights": {"farm": 9, "ocean": 0.1}})
    assert weights["farm"] == 2.5
    assert weights["ocean"] == 0.5


def test_score_story_uses_editorial_and_category_weight():
    story = {
        "category": "farm",
        "score": 9,
        "editorial": {"approved": True, "score": 80, "humanity": {"score": 86}},
    }
    boosted = score_story(story, {"category_weights": {"farm": 1.5}})
    plain = score_story(story, {"category_weights": {"farm": 1.0}})
    assert boosted > plain


def test_score_story_uses_format_weight_and_exploit_keywords():
    story = {
        "category": "farm",
        "story_format": "animal_memory",
        "title": "Chickens remember faces",
        "hook": "Chickens remember your face.",
        "score": 8,
        "editorial": {"approved": True, "score": 75, "humanity": {"score": 78}},
    }
    strategy = {
        "category_weights": {"farm": 1.0},
        "format_weights": {"animal_memory": 1.6},
        "exploit_keywords": ["chickens"],
    }
    assert score_story(story, strategy) > score_story(story, {"category_weights": {"farm": 1.0}})


def test_rank_for_growth_keeps_approved_stories_first():
    candidates = [
        {"category": "farm", "score": 10, "editorial": {"approved": False, "score": 90, "humanity": {"score": 95}}},
        {"category": "cats", "score": 7, "editorial": {"approved": True, "score": 70, "humanity": {"score": 70}}},
    ]
    ranked = rank_for_growth(candidates, {"category_weights": {"farm": 2.5, "cats": 1.0}})
    assert ranked[0]["category"] == "cats"
    assert "growth_priority" in ranked[0]


def test_score_story_rewards_signature_humanity():
    base = {
        "category": "cats",
        "score": 8,
        "editorial": {"approved": True, "score": 72, "humanity": {"score": 62}},
    }
    signature = {
        **base,
        "editorial": {"approved": True, "score": 72, "humanity": {"score": 92}},
    }
    assert score_story(signature, {"category_weights": {"cats": 1.0}}) > score_story(
        base, {"category_weights": {"cats": 1.0}}
    )


def test_paused_category_reduces_growth_priority(tmp_path, monkeypatch):
    ops = tmp_path / "ops.json"
    ops.write_text('{"paused_topics":[{"category":"cats"}]}', encoding="utf-8")
    monkeypatch.setattr("utils.growth_strategy.OPS_FILE", ops)
    story = {
        "category": "cats",
        "score": 8,
        "editorial": {"approved": True, "score": 80, "humanity": {"score": 85}},
    }
    paused = score_story(story, {"category_weights": {"cats": 1.0}})
    monkeypatch.setattr("utils.growth_strategy.OPS_FILE", tmp_path / "missing.json")
    normal = score_story(story, {"category_weights": {"cats": 1.0}})
    assert paused < normal
    assert paused_categories(ops)["cats"]["category"] == "cats"
    assert is_paused_category("Cats", ops) is True


def test_ops_guardian_enforced_reads_boolean_env():
    assert ops_guardian_enforced({}) is True
    assert ops_guardian_enforced({"OPS_GUARDIAN_ENFORCE": "1"}) is True
    assert ops_guardian_enforced({"OPS_GUARDIAN_ENFORCE": "true"}) is True
    assert ops_guardian_enforced({"OPS_GUARDIAN_ENFORCE": "0"}) is False
