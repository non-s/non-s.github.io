from utils.agency_gate import success_allows
from utils.success_rewriter import rewrite_queue, rewrite_story, _word_count


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
