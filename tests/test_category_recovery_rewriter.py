from utils.agency_gate import evaluate_story
from utils.category_recovery_rewriter import recover_story


def test_recover_cat_story_uses_natural_recovery_title():
    story = {
        "id": "cat-1",
        "category": "cats",
        "seo_title": "Why cats purr - it's not just happiness",
        "hook": "Why do cats purr?",
        "script": "Why do cats purr? Cats purr for many reasons and it is not just happiness.",
        "experiments": {"hook_style": "question"},
    }
    updated, changed = recover_story(story)
    assert changed is True
    assert "with their" not in updated["seo_title"]
    assert updated["experiments"]["hook_style"] == "outcome_first"
    assert updated["story_format"] in {"animal_memory", "body_superpower"}
    assert len(updated["script"].split()) <= 95


def test_recovered_cat_story_passes_category_gate():
    story = {
        "id": "cat-2",
        "category": "cats",
        "seo_title": "Cats love boxes",
        "hook": "Cats love boxes.",
        "script": "Cats love boxes because tight spaces can feel safer than open rooms.",
        "source": "Pexels",
        "source_url": "https://www.pexels.com/video/cat-in-box/",
        "source_license": "Pexels License",
    }
    updated, _ = recover_story(story)
    verdict = evaluate_story(updated, rewrite_ids=set(), recovery_plans={
        "cats": {"allowed_formats": ["myth_buster", "body_superpower", "animal_memory"]}
    })
    assert verdict["approved"] is True


def test_recovered_dog_story_passes_category_gate():
    story = {
        "id": "dog-1",
        "category": "dogs",
        "seo_title": "Why dogs wag tails - it is not just happiness",
        "title": "dog wagging tail in snow",
        "hook": "Why do dogs wag tails?",
        "script": "Why do dogs wag tails? Dogs wag tails for many reasons.",
        "source": "Pexels",
        "source_url": "https://www.pexels.com/video/dog-wagging-tail/",
        "source_license": "Pexels License",
    }
    updated, changed = recover_story(story)
    assert changed is True
    assert "dog" in updated["script"].lower() or "dogs" in updated["script"].lower()
    verdict = evaluate_story(updated, rewrite_ids=set(), recovery_plans={
        "dogs": {"allowed_formats": ["myth_buster", "body_superpower", "animal_memory"]}
    })
    assert verdict["approved"] is True
