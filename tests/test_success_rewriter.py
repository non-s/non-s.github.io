from utils.agency_gate import success_allows
from utils.editorial_guard import editorial_issues
from utils.success_rewriter import _word_count, rewrite_queue, rewrite_story


def _story(**extra):
    base = {
        "id": "a",
        "category": "dogs",
        "seo_title": "What a dog's tail says before the bark that most people miss",
        "title": "dogs playing outside",
        "hook": "What does the tail mean?",
        "script": "What does the tail mean? Why does it move? The secret is simple. " * 20,
        "thumbnail_text": "TAIL SECRET",
        "experiments": {"hook_style": "question"},
    }
    base.update(extra)
    return base


def test_success_rewriter_removes_question_overload_and_secret():
    updated, changed = rewrite_story(
        _story(),
        ["success_question_overload", "overused_phrase_pressure", "success_script_too_long"],
    )
    assert changed
    body = " ".join(str(updated.get(key) or "") for key in ("seo_title", "hook", "script", "thumbnail_text"))
    assert body.count("?") < 2
    assert "secret" not in body.lower()
    assert _word_count(updated["script"]) <= 105
    assert updated["success_rewrite"]["before"]["script_words"] > updated["success_rewrite"]["after"]["script_words"]


def test_success_rewriter_makes_duplicate_story_distinctive():
    updated, changed = rewrite_story(_story(), ["duplicate_angle_rewrite_required"])
    assert changed
    assert "tail says before the bark" not in updated["seo_title"].lower()
    assert updated["experiments"]["hook_style"] == "outcome_first"
    assert updated["hook"].startswith("Watch")


def test_rewritten_story_can_pass_phrase_and_question_success_gate():
    story = _story(category="birds", experiments={"hook_style": "outcome_first"})
    updated, _ = rewrite_story(
        story,
        ["success_question_overload", "overused_phrase_pressure", "success_script_too_long"],
    )
    ok, reasons = success_allows(
        updated,
        {"retention": {"phrase_pressure": [{"phrase": "secret", "uses": 12}]}},
    )
    assert ok, reasons


def test_rewrite_queue_repairs_gate_verdict_without_external_rewrite_id():
    queue = {"stories": [_story(script="Birds watch the tail cue before the move " * 20)]}

    updated, changed = rewrite_queue(queue, set(), {"a": ["success_script_too_long"]})

    assert len(changed) == 1
    assert _word_count(updated["stories"][0]["script"]) <= 105


def test_success_rewriter_repairs_recovery_format_and_hook_gate():
    story = _story(
        category="forests",
        seo_title="Forests use cool canopy before they cover",
        title="Forests use cool canopy before they cover",
        hook="Why does the canopy matter?",
        script="Why does the canopy matter? Forests cover the ground with shade before heat builds.",
        thumbnail_text="CANOPY",
        story_format="earth_engine",
        experiments={},
    )
    plan = {"retention": {"recovery_categories": [{"category": "forests"}]}}
    before_ok, before_reasons = success_allows(story, plan)

    updated, changed = rewrite_story(story, ["success_recovery_format_required", "success_recovery_hook_required"])
    after_ok, after_reasons = success_allows(updated, plan)

    assert not before_ok
    assert "success_recovery_format_required" in before_reasons
    assert "success_recovery_hook_required" in before_reasons
    assert changed
    assert after_ok, after_reasons
    assert updated["title"] == updated["seo_title"]
    assert updated["story_format"] == "body_superpower"
    assert updated["experiments"]["hook_style"] == "outcome_first"
    assert _word_count(updated["script"]) <= 95
    assert updated["success_recovery"]["visible"] in {"shadow line", "leaf shade", "canopy layers"}
    assert editorial_issues(updated) == []


def test_rewrite_queue_repairs_success_recovery_gate_without_external_rewrite_id():
    queue = {
        "stories": [
            _story(
                category="plants",
                seo_title="Plants turn light into food",
                title="Plants turn light into food",
                story_format="plant_mechanism",
                experiments={},
            )
        ]
    }

    updated, changed = rewrite_queue(
        queue,
        set(),
        {"a": ["success_recovery_format_required", "success_recovery_hook_required"]},
    )

    assert len(changed) == 1
    story = updated["stories"][0]
    assert story["story_format"] == "body_superpower"
    assert story["experiments"]["hook_style"] == "outcome_first"
