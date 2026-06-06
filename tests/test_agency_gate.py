from utils.agency_gate import evaluate_story, filter_candidates, recovery_allows


def _story(**extra):
    base = {
        "id": "story-1",
        "title": "Cats remember faces",
        "hook": "Cats remember your face.",
        "script": (
            "Cats remember your face. Watch their eyes because familiar "
            "people change how they move through the room. That is why "
            "one quiet voice can calm the whole moment."
        ),
        "category": "cats",
        "story_format": "animal_memory",
        "experiments": {"hook_style": "outcome_first"},
    }
    base.update(extra)
    return base


def test_agency_gate_holds_rewrite_ids():
    verdict = evaluate_story(_story(id="bad"), rewrite_ids={"bad"}, recovery_plans={})
    assert verdict["approved"] is False
    assert "retention_rewrite_required" in verdict["reasons"]


def test_recovery_allows_tight_approved_format():
    plan = {"allowed_formats": ["animal_memory"]}
    assert recovery_allows(_story(), plan) is True


def test_recovery_blocks_wrong_format():
    plan = {"allowed_formats": ["body_superpower"]}
    assert recovery_allows(_story(story_format="cute_behavior"), plan) is False


def test_filter_candidates_splits_approved_and_held():
    approved, held = filter_candidates(
        [_story(id="a"), _story(id="b")],
        rewrite_ids={"b"},
        recovery_plans={},
    )
    assert [item["id"] for item in approved] == ["a"]
    assert [item["id"] for item in held] == ["b"]
    assert held[0]["agency_gate"]["state"] == "held"
