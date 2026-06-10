from utils.editorial_rules import EditorialRulebook, evaluate_story_package


def test_editorial_rulebook_approves_specific_visual_package():
    story = {
        "category": "ocean",
        "title": "Octopus changes skin before it attacks",
        "hook": "This octopus changes skin seconds before it attacks",
        "script": "The skin changes because the animal is signaling before the strike.",
    }
    package = {
        "first_frame_text": "Skin changes",
        "hook": story["hook"],
        "visual_motion_score": 0.82,
        "contrast_score": 0.9,
        "caption_chars_per_second": 11,
        "payoff_time_s": 9,
        "loop_score": 0.72,
        "cta_count": 1,
        "novelty_score": 0.76,
    }

    out = evaluate_story_package(story, package, {"recent_hooks": []})

    assert out["approved"] is True
    assert out["score"] >= 72
    assert out["recommended_format"] == "mechanism_reveal"


def test_editorial_rulebook_blocks_generic_duplicate_package():
    story = {
        "category": "wildlife",
        "title": "Amazing animal fact",
        "hook": "You will not believe this amazing animal",
        "script": "This is amazing and incredible.",
    }
    package = {
        "first_frame_text": "This animal is amazing now",
        "hook": story["hook"],
        "visual_motion_score": 0.2,
        "contrast_score": 0.4,
        "caption_chars_per_second": 22,
        "payoff_time_s": 22,
        "loop_score": 0.12,
        "cta_count": 2,
        "novelty_score": 0.2,
    }
    context = {
        "recent_hooks": ["You will not believe this amazing animal"],
        "recent_subjects": ["wildlife"],
    }

    out = EditorialRulebook().evaluate(story, package, context)

    assert out["approved"] is False
    assert "hook overlaps too closely with recent uploads" in out["violations"]
    assert "CTA burden is too high" in out["violations"]
    assert out["score"] < 72
