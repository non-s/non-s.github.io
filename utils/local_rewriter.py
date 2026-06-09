"""Deterministic rescue rewrites before rejecting usable animal footage."""
from __future__ import annotations

import re

from utils.packaging import extract_action, extract_animal, extract_cue
from utils.story_intelligence import classify_format


def _animal(text: str) -> str:
    for word in re.findall(r"[A-Za-z][A-Za-z'-]+", text or ""):
        low = word.lower().replace("'s", "")
        if low in {
            "cow", "cows", "duck", "ducks", "chicken", "chickens", "deer",
            "horse", "horses", "tiger", "tigers", "penguin", "penguins",
            "goat", "goats", "wolf", "wolves", "bear", "bears", "bird",
            "birds", "owl", "owls", "cat", "cats", "dog", "dogs",
            "lion", "lions", "elephant", "elephants", "dolphin", "dolphins",
            "whale", "whales", "octopus", "octopuses", "seal", "seals",
            "fox", "foxes", "sheep", "parrot", "parrots", "macaw", "macaws",
            "orangutan", "orangutans", "monkey", "monkeys", "bee", "bees",
            "butterfly", "butterflies", "ant", "ants", "beetle", "beetles",
            "mantis", "mantises", "dragonfly", "dragonflies", "snake",
            "snakes", "chameleon", "chameleons", "turtle", "turtles",
        }:
            return word.capitalize()
    return "Animals"


def rescue_story(story: dict, reasons: list[str]) -> tuple[dict, bool]:
    """Return a locally rewritten story when the issue is editorial, not visual."""
    reasons = list(reasons)
    if "off_topic_visual" in reasons:
        return story, False
    if not any(reason in reasons for reason in (
        "repetitive_title_template", "generic_script_template", "script_word_loop",
        "duplicate_script", "rewrite_packaging", "missing_visible_cue",
        "missing_action_word", "title_needs_stronger_shape",
        "animal_not_immediately_clear", "no_action_promise",
        "payoff_not_explicit", "missing_visual_cue",
        "generic_creator_language", "hook_shape_weak", "title_shape_weak",
        "script_subject_mismatch",
    )):
        return story, False
    out = dict(story)
    text = " ".join(str(out.get(k) or "") for k in ("title", "seo_title", "hook", "script", "category"))
    visual_text = " ".join(str(out.get(k) or "") for k in ("source_url", "url", "raw_title", "title", "category"))
    animal = _animal(visual_text)
    if animal == "Animals":
        animal = extract_animal(out)
    if animal.lower() == "animal":
        animal = _animal(text)
    cue = extract_cue(out)
    action = extract_action(out)
    fmt = classify_format(text)
    if fmt == "animal_memory":
        title = f"{animal} remember because of this {cue}"
        hook = f"{animal} remember by using one visible {cue}."
    elif fmt == "body_superpower":
        title = f"{animal} use their {cue} to {action}"
        hook = f"{animal} use their {cue} to {action} for a clear reason."
    else:
        title = f"Watch the {cue} when {animal.lower()} {action}"
        hook = f"{animal} {action} with one visible {cue}."
    script = (
        f"{hook} Watch the {cue} first, because that is where the story starts. "
        f"The {cue} is not random: it helps {animal.lower()} solve one clear problem. "
        f"That is why this moment matters before the payoff. Follow for one animal signal a day."
    )
    out.update({
        "seo_title": title[:60],
        "title": out.get("title") or title,
        "hook": hook,
        "script": script,
        "lead": script[:400],
        "thumbnail_text": f"WATCH THE {cue.upper()}"[:28],
        "local_rewrite": {"applied": True, "reasons": reasons, "method": "deterministic_rescue"},
    })
    return out, True
