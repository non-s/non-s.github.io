"""Tests for utils/script_quality.py — pure heuristic, no network."""

from __future__ import annotations

from utils.script_quality import (
    check_banned_phrases,
    check_hook_opens_strong,
    check_length,
    check_human_voice,
    check_script_starts_with_hook,
    check_templated_narration,
    check_title_diverges_from_source,
    check_transformation_present,
    evaluate,
    should_block,
)


# ── banned phrases ───────────────────────────────────────────────


def test_banned_phrase_crucial_is_flagged():
    issues = check_banned_phrases("This is crucial for the economy.")
    assert any(i.code == "ai_tell" for i in issues)
    assert "crucial" in issues[0].message.lower()


def test_banned_phrase_pivotal_is_flagged():
    issues = check_banned_phrases("A pivotal moment for the country.")
    assert any(i.code == "ai_tell" for i in issues)


def test_banned_phrase_delve_is_flagged():
    issues = check_banned_phrases("Let's delve into the latest data.")
    assert issues


def test_banned_phrase_repeat_only_counted_once():
    issues = check_banned_phrases("Crucial here. Crucial there. Crucial everywhere.")
    assert len([i for i in issues if i.code == "ai_tell"]) == 1


def test_clean_script_has_no_banned_phrases():
    issues = check_banned_phrases("This octopus changed colour and texture near the coral reef.")
    assert issues == []


def test_low_human_voice_is_flagged():
    issues = check_human_voice(
        "Animals have fascinating adaptations in the animal kingdom. "
        "This remarkable creature plays a vital role in nature."
    )
    assert any(i.code == "low_human_voice" for i in issues)


def test_human_voice_passes_with_host_detail():
    issues = check_human_voice(
        "Chickens remember your face. I love this detail: they watch eyes "
        "and voices, then act differently around strangers."
    )
    assert issues == []


def test_templated_rescue_narration_is_blocked():
    script = (
        "Bees reveal one visible signal. Watch the wing movement, because bees use it to send a clear signal "
        "before the next move. The payoff appears before the final move. That is why viewers can replay the "
        "first second and catch the hidden cue before it pays off again."
    )

    issues = check_templated_narration(script)

    assert any(i.code == "templated_narration" and i.severity == "block" for i in issues)


def test_fact_specific_narration_is_not_template_blocked():
    script = (
        "Bees dance directions inside the hive. Watch the wing and body vibration: the waggle points "
        "nestmates toward food by encoding direction and distance. That tiny motion is a map, not random "
        "buzzing. Would you follow the dance?"
    )

    assert check_templated_narration(script) == []


# ── hook openers ─────────────────────────────────────────────────


def test_weak_hook_today_is_flagged():
    issues = check_hook_opens_strong("Today the octopus changed colour")
    assert any(i.code == "weak_hook" for i in issues)


def test_weak_hook_according_to_is_flagged():
    issues = check_hook_opens_strong("According to the source, the owl turned.")
    assert any(i.code == "weak_hook" for i in issues)


def test_weak_hook_hi_everyone_is_flagged():
    issues = check_hook_opens_strong("Hi everyone, animal fact today.")
    assert any(i.code == "weak_hook" for i in issues)


def test_strong_hook_passes():
    issues = check_hook_opens_strong("This octopus changes colour in seconds.")
    assert issues == []


def test_animal_action_hook_passes():
    issues = check_hook_opens_strong("Chickens remember your face.")
    assert issues == []


def test_vague_hook_without_outcome_is_flagged():
    issues = check_hook_opens_strong("People talked about the matter.")
    assert any(i.code == "vague_hook" for i in issues)


def test_missing_hook_is_block_severity():
    issues = check_hook_opens_strong("")
    assert any(i.code == "missing_hook" and i.severity == "block" for i in issues)


# ── script starts with hook ──────────────────────────────────────


def test_script_must_start_with_hook():
    issues = check_script_starts_with_hook(
        hook="The octopus changed colour",
        script="In another clip, the octopus changed colour...",
    )
    assert any(i.code == "script_hook_mismatch" for i in issues)


def test_script_starts_correctly():
    issues = check_script_starts_with_hook(
        hook="The octopus changed colour.",
        script="The octopus changed colour. Its skin texture shifted too...",
    )
    assert issues == []


# ── transformation ───────────────────────────────────────────────


def test_low_transformation_is_flagged():
    src = (
        "the octopus changed colour and skin texture against the coral "
        "reef while its camouflage became harder to notice"
    )
    # Same words rearranged — high overlap.
    script = "octopus colour skin texture coral reef camouflage changed harder notice"
    issues = check_transformation_present(script, src)
    assert any(i.code == "low_transformation" for i in issues)


def test_high_transformation_passes():
    src = "The octopus changed colour and texture while hiding near a coral reef."
    script = (
        "Bottom line: this disguise is more than a colour swap. Tiny "
        "muscles reshape the skin surface while specialised cells "
        "control the pattern underneath."
    )
    assert check_transformation_present(script, src) == []


# ── length ───────────────────────────────────────────────────────


def test_too_short_script_is_blocked():
    issues = check_length("Five words only here yes.")
    assert any(i.code == "script_too_short" and i.severity == "block" for i in issues)


def test_too_long_script_is_warned():
    issues = check_length("word " * 200)
    assert any(i.code == "script_too_long" for i in issues)


def test_empty_script_is_blocked():
    issues = check_length("")
    assert any(i.code == "empty_script" for i in issues)


def test_good_length_passes():
    text = " ".join(["word"] * 100)
    assert check_length(text) == []


# ── seo title diverges ──────────────────────────────────────────


def test_identical_seo_title_flagged():
    issues = check_title_diverges_from_source("Octopus changes colour", "Octopus changes colour")
    assert any(i.code == "seo_title_unchanged" for i in issues)


def test_different_seo_title_passes():
    issues = check_title_diverges_from_source("Octopus camouflage works in seconds", "Octopus changes colour today")
    assert issues == []


def test_missing_raw_title_does_not_self_compare():
    story = {
        "hook": "Chickens remember your face.",
        "script": "Chickens remember your face. I love this detail: they watch eyes and voices, then act differently around strangers.",
        "description": "A clip of chickens walking in a farmyard.",
        "seo_title": "Chickens remember faces",
    }
    _, issues = evaluate(story)
    assert all(i.code != "seo_title_unchanged" for i in issues)


# ── evaluate ────────────────────────────────────────────────────


def test_evaluate_clean_story_gets_high_grade():
    story = {
        "hook": "This octopus changes colour in seconds.",
        "script": (
            "This octopus changes colour in seconds. Its camouflage "
            "is more than a colour swap. Tiny muscles reshape the "
            "skin while specialised cells shift the pattern. "
            "Watch how it disappears against the reef. " * 2
        ),
        "description": "Octopus camouflage changes near a coral reef.",
        "seo_title": "Octopus camouflage works in seconds",
        "raw_title": "Octopus changes colour near reef",
    }
    grade, issues = evaluate(story)
    assert grade >= 8


def test_evaluate_slop_story_gets_low_grade():
    story = {
        "hook": "Today this octopus changed colour.",
        "script": "Crucial animal fact today. This octopus delved into " "a pivotal camouflage moment.",
        "description": "Octopus camouflage changes near a coral reef",
        "seo_title": "Octopus camouflage changes near a coral reef",
        "raw_title": "Octopus camouflage changes near a coral reef",
    }
    grade, issues = evaluate(story)
    assert grade < 6
    # Multiple separate signals fire.
    assert any(i.code == "weak_hook" for i in issues)
    assert any(i.code == "ai_tell" for i in issues)
    assert any(i.code == "seo_title_unchanged" for i in issues)


def test_should_block_on_block_severity():
    from utils.script_quality import Issue

    assert should_block([Issue("missing_hook", "block", "x")])


def test_should_block_on_six_warns():
    from utils.script_quality import Issue

    warns = [Issue("ai_tell", "warn", f"x{i}") for i in range(6)]
    assert should_block(warns)


def test_should_not_block_on_few_warns():
    from utils.script_quality import Issue

    warns = [Issue("ai_tell", "warn", "x")]
    assert not should_block(warns)
