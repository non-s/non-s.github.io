from pathlib import Path

from utils.growth_strategy import category_weights, rank_for_growth, score_story


def test_category_weights_are_bounded():
    weights = category_weights({"category_weights": {"farm": 9, "ocean": 0.1}})
    assert weights["farm"] == 2.5
    assert weights["ocean"] == 0.5


def test_score_story_uses_editorial_and_category_weight():
    story = {
        "category": "farm",
        "score": 9,
        "editorial": {"approved": True, "score": 80},
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
        "editorial": {"approved": True, "score": 75},
    }
    strategy = {
        "category_weights": {"farm": 1.0},
        "format_weights": {"animal_memory": 1.6},
        "exploit_keywords": ["chickens"],
    }
    assert score_story(story, strategy) > score_story(story, {"category_weights": {"farm": 1.0}})


def test_rank_for_growth_keeps_approved_stories_first():
    candidates = [
        {"category": "farm", "score": 10, "editorial": {"approved": False, "score": 90}},
        {"category": "cats", "score": 7, "editorial": {"approved": True, "score": 70}},
    ]
    ranked = rank_for_growth(candidates, {"category_weights": {"farm": 2.5, "cats": 1.0}})
    assert ranked[0]["category"] == "cats"
    assert "growth_priority" in ranked[0]
