from utils.agency_gate import evaluate_story, filter_candidates, recovery_allows, success_allows


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
        "source": "Pexels",
        "source_url": "https://www.pexels.com/video/cat-1/",
        "source_license": "Pexels License",
    }
    base.update(extra)
    return base


def test_agency_gate_holds_rewrite_ids():
    verdict = evaluate_story(
        _story(id="bad"),
        rewrite_ids={"bad"},
        recovery_plans={},
        duplicate_ids=set(),
        success_plan={},
    )
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
        duplicate_ids=set(),
        success_plan={},
    )
    assert [item["id"] for item in approved] == ["a"]
    assert [item["id"] for item in held] == ["b"]
    assert held[0]["agency_gate"]["state"] == "held"


def test_agency_gate_holds_duplicate_angles():
    verdict = evaluate_story(
        _story(id="copy"),
        rewrite_ids=set(),
        recovery_plans={},
        duplicate_ids={"copy"},
        success_plan={},
    )
    assert verdict["approved"] is False
    assert "duplicate_angle_rewrite_required" in verdict["reasons"]


def test_success_gate_blocks_overused_phrase_pressure():
    ok, reasons = success_allows(
        _story(title="Cats have a secret signal"),
        {"retention": {"phrase_pressure": [{"phrase": "secret", "uses": 12}]}},
    )
    assert ok is False
    assert "overused_phrase_pressure" in reasons


def test_success_gate_blocks_recovery_category_with_weak_shape():
    ok, reasons = success_allows(
        _story(
            category="dogs",
            story_format="cute_behavior",
            experiments={"hook_style": "question"},
        ),
        {"retention": {"recovery_categories": [{"category": "dogs"}]}},
    )
    assert ok is False
    assert "success_recovery_format_required" in reasons
    assert "success_recovery_hook_required" in reasons


def test_agency_gate_holds_robotic_copy_and_missing_license():
    verdict = evaluate_story(
        _story(
            title="Lions use their ears to use",
            seo_title="Lions use their ears to use",
            source_license="",
        ),
        rewrite_ids=set(),
        recovery_plans={},
        duplicate_ids=set(),
        success_plan={},
    )

    assert verdict["approved"] is False
    assert "editorial_robotic_use_loop" in verdict["reasons"]
    assert "rights_missing_source_license" in verdict["reasons"]
