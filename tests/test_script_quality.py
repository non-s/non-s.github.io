"""Tests for utils/script_quality.py — pure heuristic, no network."""
from __future__ import annotations

from utils.script_quality import (
    check_banned_phrases,
    check_hook_opens_strong,
    check_length,
    check_script_starts_with_hook,
    check_title_diverges_from_headline,
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
    issues = check_banned_phrases(
        "The Fed cut interest rates by 50 basis points after the meeting."
    )
    assert issues == []


# ── hook openers ─────────────────────────────────────────────────

def test_weak_hook_today_is_flagged():
    issues = check_hook_opens_strong("Today the Fed announced rates")
    assert any(i.code == "weak_hook" for i in issues)


def test_weak_hook_according_to_is_flagged():
    issues = check_hook_opens_strong("According to Reuters, the bank failed.")
    assert any(i.code == "weak_hook" for i in issues)


def test_weak_hook_hi_everyone_is_flagged():
    issues = check_hook_opens_strong("Hi everyone, breaking news today.")
    assert any(i.code == "weak_hook" for i in issues)


def test_strong_hook_passes():
    issues = check_hook_opens_strong("The Fed just cut rates by 50 basis points.")
    assert all(i.code != "weak_hook" for i in issues)


def test_vague_hook_without_outcome_is_flagged():
    issues = check_hook_opens_strong("People talked about the matter.")
    assert any(i.code == "vague_hook" for i in issues)


def test_missing_hook_is_block_severity():
    issues = check_hook_opens_strong("")
    assert any(i.code == "missing_hook" and i.severity == "block" for i in issues)


# ── script starts with hook ──────────────────────────────────────

def test_script_must_start_with_hook():
    issues = check_script_starts_with_hook(
        hook="The Fed cut rates",
        script="In other news, the Fed cut rates by 50bps...",
    )
    assert any(i.code == "script_hook_mismatch" for i in issues)


def test_script_starts_correctly():
    issues = check_script_starts_with_hook(
        hook="The Fed cut rates.",
        script="The Fed cut rates. Inflation isn't done yet...",
    )
    assert issues == []


# ── transformation ───────────────────────────────────────────────

def test_low_transformation_is_flagged():
    src = ("the federal reserve cut interest rates by fifty basis points "
           "powell said inflation cooling markets reacted")
    # Same words rearranged — high overlap.
    script = "powell cut rates fifty basis points markets reacted inflation cooling federal reserve said"
    issues = check_transformation_present(script, src)
    assert any(i.code == "low_transformation" for i in issues)


def test_high_transformation_passes():
    src = "Federal Reserve raised rates today by fifty basis points said Powell."
    script = ("Bottom line: tighter money means a recession is much more "
              "likely now. Mortgage applications already collapsing two days "
              "in a row. Watch credit-card delinquencies next.")
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
    issues = check_title_diverges_from_headline(
        "Fed cuts rates", "Fed cuts rates"
    )
    assert any(i.code == "seo_title_unchanged" for i in issues)


def test_different_seo_title_passes():
    issues = check_title_diverges_from_headline(
        "Fed just cut rates — markets won", "Fed cuts interest rates today"
    )
    assert issues == []


# ── evaluate ────────────────────────────────────────────────────

def test_evaluate_clean_story_gets_high_grade():
    story = {
        "hook":   "The Fed just cut rates 50bps.",
        "script": ("The Fed just cut rates 50bps. Inflation isn't done yet. "
                   "Markets had this priced in 6 weeks ago — Powell's "
                   "catching up. Mortgage rates won't follow as fast. "
                   "Watch credit-card delinquencies next. " * 2),
        "description": "Federal Reserve announces rate decision today.",
        "seo_title":   "Fed cut rates — but inflation isn't done",
        "raw_title":   "Federal Reserve announces rate decision",
    }
    grade, issues = evaluate(story)
    assert grade >= 8


def test_evaluate_slop_story_gets_low_grade():
    story = {
        "hook":   "Today the Fed announced rates.",
        "script": "Crucial economic news today. The Fed delved into "
                  "pivotal rate policy.",
        "description": "Federal Reserve announces rate decision",
        "seo_title": "Federal Reserve announces rate decision",
        "raw_title": "Federal Reserve announces rate decision",
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
