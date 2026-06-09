"""Deterministic rescue rewrites before rejecting usable animal footage."""
from __future__ import annotations

import re

from utils.story_intelligence import classify_format


def _animal(text: str) -> str:
    for word in re.findall(r"[A-Za-z][A-Za-z'-]+", text or ""):
        low = word.lower().replace("'s", "")
        if low in {
            "cow", "cows", "duck", "ducks", "chicken", "chickens", "deer",
            "horse", "horses", "tiger", "tigers", "penguin", "penguins",
            "goat", "goats", "wolf", "wolves", "bear", "bears", "bird",
            "birds", "owl", "owls", "cat", "cats", "dog", "dogs",
        }:
            return word.capitalize()
    return "Animals"


def rescue_story(story: dict, reasons: list[str]) -> tuple[dict, bool]:
    """Return a locally rewritten story when the issue is editorial, not visual."""
    reasons = list(reasons)
    if "off_topic_visual" in reasons or "script_subject_mismatch" in reasons:
        return story, False
    if not any(reason in reasons for reason in (
        "repetitive_title_template", "generic_script_template", "script_word_loop",
        "duplicate_script",
    )):
        return story, False
    out = dict(story)
    text = " ".join(str(out.get(k) or "") for k in ("title", "seo_title", "hook", "script", "category"))
    animal = _animal(text)
    fmt = classify_format(text)
    if fmt == "animal_memory":
        title = f"{animal} remember one detail viewers miss"
        hook = f"{animal} remember more than most viewers expect."
    elif fmt == "body_superpower":
        title = f"{animal} use one body trick to survive"
        hook = f"{animal} use one body trick for a clear reason."
    else:
        title = f"{animal} show one behavior with a hidden payoff"
        hook = f"{animal} show one behavior with a hidden payoff."
    script = (
        f"{hook} Watch the visible cue first, because that is where the story starts. "
        f"The movement is not random: it helps the animal solve one simple problem. "
        f"One animal, one cue, one payoff. Follow for one animal signal a day."
    )
    out.update({
        "seo_title": title[:60],
        "title": out.get("title") or title,
        "hook": hook,
        "script": script,
        "lead": script[:400],
        "thumbnail_text": "VISIBLE PAYOFF",
        "local_rewrite": {"applied": True, "reasons": reasons, "method": "deterministic_rescue"},
    })
    return out, True
