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
            "orangutan", "orangutans", "monkey", "monkeys", "donkey", "donkeys",
            "shark", "sharks", "bee", "bees",
            "butterfly", "butterflies", "ant", "ants", "beetle", "beetles",
            "mantis", "mantises", "dragonfly", "dragonflies", "snake",
            "snakes", "chameleon", "chameleons", "turtle", "turtles",
        }:
            return word.capitalize()
    return "Animals"


def _subject(animal: str) -> str:
    return animal[:1].upper() + animal[1:] if animal else "Animals"


def _lower_subject(animal: str) -> str:
    return (animal or "animals").lower()


def _plural(animal: str) -> bool:
    lower = _lower_subject(animal)
    return lower == "sheep" or lower.endswith("s")


def _verb(animal: str, base: str) -> str:
    if _plural(animal):
        return base
    if base.endswith("ch") or base.endswith("sh"):
        return f"{base}es"
    if base.endswith("y"):
        return f"{base[:-1]}ies"
    return f"{base}s"


def _usable_action(action: str, fmt: str) -> str:
    action = (action or "").lower().strip()
    if action in {"show", "watch", "cue", ""}:
        if fmt == "animal_memory":
            return "remember"
        if fmt == "body_superpower":
            return "use"
        return "signal"
    return action


def _usable_cue(cue: str) -> str:
    cue = (cue or "").lower().strip()
    return "body" if cue in {"", "cue"} else cue


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
    fmt = classify_format(text)
    cue = _usable_cue(extract_cue(out))
    action = _usable_action(extract_action(out), fmt)
    subject = _subject(animal)
    lower_subject = _lower_subject(animal)
    action_phrase = _verb(animal, action)
    if fmt == "animal_memory":
        title = f"{subject} remember faces by watching the {cue}"
        hook = f"{subject} remember by using one visible {cue}."
    elif fmt == "body_superpower":
        title = f"{subject} use their {cue} to {action}"
        hook = f"{subject} use their {cue} to {action} for a clear reason."
    else:
        title = f"{subject} {action_phrase} because of this {cue}"
        hook = f"{subject} {action_phrase} with one visible {cue}."
    script = (
        f"{hook} Watch the {cue} first, because that is where the story starts. "
        f"The {cue} is not random: it helps {lower_subject} solve one clear problem. "
        f"That is why this moment matters before the payoff. Follow for one animal signal a day."
    )
    out.update({
        "seo_title": title[:60],
        "title": title[:60],
        "hook": hook,
        "script": script,
        "lead": script[:400],
        "thumbnail_text": f"{subject.upper()} {cue.upper()}"[:28],
        "local_rewrite": {"applied": True, "reasons": reasons, "method": "deterministic_rescue"},
    })
    return out, True
