from utils.retention_rewriter import rewrite_queue, rewrite_story
from utils.retention_surgeon import diagnose


def _weak_story():
    return {
        "id": "weak-dog",
        "seo_title": "Why dogs wag tails - it is not just happiness",
        "title": "dogs wagging tails",
        "hook": "Dogs wag tails for snacks.",
        "script": "Dogs wag tails for snacks. They wag more when they expect food.",
        "category": "dogs",
    }


def test_rewrite_story_improves_retention_score_and_keeps_animal():
    story = _weak_story()
    before = diagnose(story)
    updated, changed = rewrite_story(story)
    after = diagnose(updated)
    assert changed is True
    assert after["score"] > before["score"]
    assert "dog" in updated["script"].lower()
    assert updated["retention_rewrite_applied"]["method"] == "local_retention_rewriter"


def test_rewrite_queue_updates_matching_ids_only():
    queue = {"stories": [_weak_story(), {**_weak_story(), "id": "other"}]}
    updated, changed = rewrite_queue(queue, {"weak-dog"})
    assert len(changed) == 1
    rewritten = [s for s in updated["stories"] if s["id"] == "weak-dog"][0]
    other = [s for s in updated["stories"] if s["id"] == "other"][0]
    assert rewritten.get("retention_rewrite_applied")
    assert not other.get("retention_rewrite_applied")
