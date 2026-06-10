"""Retention-first diagnostics for Shorts stories.

This module is intentionally deterministic and offline. It gives the
automation a local "retention surgeon" that can explain why a Short may
lose viewers early and what to fix before remaking or publishing a
similar angle.
"""
from __future__ import annotations

import re

from utils.growth_engine import analyze_retention


WEAK_OPENERS = {
    "did you know", "today", "in this video", "this animal", "animals are",
    "welcome", "according to", "scientists say",
}
PAYOFF_VERBS = {
    "remember", "recognize", "escape", "survive", "hide", "hunt", "heal",
    "use", "uses", "plan", "plans", "love", "loves", "see", "sees",
    "hear", "hears", "change", "changes", "protect", "protects",
    "choose", "chooses", "catch", "catches", "talk", "calls",
}


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text or "")


def _first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip(), maxsplit=1)
    return parts[0].strip() if parts else ""


def diagnose(story: dict) -> dict:
    growth = analyze_retention(story)
    title = str(story.get("seo_title") or story.get("title") or "")
    hook = str(story.get("hook") or _first_sentence(str(story.get("script") or "")))
    script = str(story.get("script") or "")
    category = str(story.get("category") or "")
    words = _words(script)
    hook_words = _words(hook)
    lower_hook = hook.lower().strip()

    score = 100
    issues: list[str] = []
    fixes: list[str] = []
    strengths: list[str] = []

    if not hook:
        score -= 35
        issues.append("missing_hook")
        fixes.append("Start with one concrete animal action and a payoff.")
    elif len(hook_words) > 12:
        score -= 12
        issues.append("hook_too_long")
        fixes.append("Cut the first sentence to 4-12 words.")
    else:
        strengths.append("short_hook")

    if any(lower_hook.startswith(prefix) for prefix in WEAK_OPENERS):
        score -= 14
        issues.append("weak_opener")
        fixes.append("Remove generic openers; start with the animal and what changes.")

    if hook and not any(verb in lower_hook.split() for verb in PAYOFF_VERBS):
        score -= 12
        issues.append("missing_payoff_verb")
        fixes.append("Add an action verb such as remember, escape, heal, use, or choose.")
    else:
        strengths.append("payoff_action")

    title_words = [w.lower() for w in _words(title)[:4]]
    hook_prefix = [w.lower() for w in hook_words[:4]]
    if title_words and hook_prefix and len(set(title_words) & set(hook_prefix)) >= 3:
        score -= 8
        issues.append("hook_repeats_title")
        fixes.append("Let the hook advance the title instead of repeating it.")

    has_payoff = any(term in script.lower() for term in ("because", "that's why", "that is why", "payoff"))
    if len(words) < 45:
        if len(words) >= 26 and has_payoff:
            score -= 6
            issues.append("script_tight_but_usable")
            fixes.append("Add one optional visual beat only if the video feels rushed.")
        else:
            score -= 18
            issues.append("script_too_short")
            fixes.append("Add one visual detail and one because/payoff sentence.")
    elif len(words) > 125:
        score -= 10
        issues.append("script_too_long")
        fixes.append("Trim to one animal, one mechanism, one payoff.")
    else:
        strengths.append("shorts_length")

    if not has_payoff:
        score -= 8
        issues.append("missing_because")
        fixes.append("Add a simple because/that-is-why payoff.")
    else:
        strengths.append("clear_explanation")

    if category in {"cats", "farm"} and len(words) > 95:
        score -= 5
        issues.append("high_velocity_category_needs_tighter_cut")
        fixes.append("Keep this category especially tight because current retention is fragile.")

    score = round(score * 0.45 + int(growth.get("score", 0)) * 0.55)
    score = max(0, min(100, score))
    if score >= 82:
        verdict = "ready"
    elif score >= 66:
        verdict = "tighten"
    else:
        verdict = "rewrite"
    return {
        "score": score,
        "growth_retention": growth,
        "verdict": verdict,
        "issues": issues,
        "fixes": fixes[:5],
        "strengths": strengths,
        "suggested_hook": suggest_hook(story, issues),
    }


def suggest_hook(story: dict, issues: list[str] | None = None) -> str:
    title = str(story.get("seo_title") or story.get("title") or "").strip()
    category = str(story.get("category") or "animal")
    animal = ""
    for token in _words(title):
        if token.lower() not in {"why", "this", "that", "really", "secret", "secrets"}:
            animal = token
            break
    animal = animal or category.rstrip("s") or "animal"
    hook = str(story.get("hook") or "").strip()
    lower = hook.lower()
    if hook and not any(lower.startswith(prefix) for prefix in WEAK_OPENERS):
        return hook[:96]
    return f"{animal.capitalize()} do this for one hidden reason."


def remake_brief(item: dict) -> dict:
    diagnosis = diagnose(item)
    return {
        "retention_surgery": diagnosis,
        "rewrite_instructions": [
            "Open with the animal plus outcome in the first two seconds.",
            "Remove setup; explain only the mechanism viewers can see or imagine.",
            "Keep the remake shorter than the original if retention was below 62%.",
            "Change the thumbnail promise, not just the wording.",
        ],
    }
