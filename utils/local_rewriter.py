"""Deterministic rescue rewrites before rejecting usable animal footage."""
from __future__ import annotations

import re

from utils.packaging import extract_action, extract_animal, extract_cue
from utils.story_intelligence import classify_format
from utils.editorial_guard import editorial_issues

ANIMAL_TAG_WORDS = {
    "ant", "ants", "bear", "bears", "bee", "bees", "beetle", "beetles",
    "bird", "birds", "butterfly", "butterflies", "cat", "cats",
    "chicken", "chickens", "cow", "cows", "deer", "dog", "dogs",
    "dolphin", "dolphins", "dragonfly", "dragonflies", "duck", "ducks",
    "duckling", "ducklings", "elephant", "elephants", "fox", "foxes",
    "goat", "goats", "horse", "horses", "lion", "lions", "macaw",
    "macaws", "mantis", "mantises", "monkey", "monkeys", "octopus",
    "octopuses", "orangutan", "orangutans", "owl", "owls", "parrot",
    "parrots", "penguin", "penguins", "seal", "seals", "shark",
    "sharks", "sheep", "snake", "snakes", "tiger", "tigers", "turtle",
    "turtles", "whale", "whales", "wolf", "wolves",
}


def _animal(text: str) -> str:
    normalised = re.sub(r"[-_/]+", " ", text or "")
    for word in re.findall(r"[A-Za-z][A-Za-z']+", normalised):
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


def _plural_subject(animal: str) -> str:
    lower = _lower_subject(animal)
    irregular = {
        "deer": "Deer",
        "sheep": "Sheep",
        "earth": "Earth systems",
        "weather": "Weather patterns",
        "wildlife": "Wildlife",
        "wolf": "Wolves",
        "fox": "Foxes",
        "octopus": "Octopuses",
        "fungus": "Fungi",
        "cactus": "Cacti",
        "goose": "Geese",
        "mouse": "Mice",
        "butterfly": "Butterflies",
    }
    if lower in irregular:
        return irregular[lower]
    if lower.endswith("s"):
        return _subject(animal)
    if lower.endswith("ch") or lower.endswith("sh"):
        return f"{_subject(animal)}es"
    if lower.endswith("y"):
        return f"{_subject(animal)[:-1]}ies"
    return f"{_subject(animal)}s"


def _lower_plural_subject(animal: str) -> str:
    return _plural_subject(animal).lower()


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
    if action in {"show", "watch", "cue", "use", "changes", "change", ""}:
        if fmt == "animal_memory":
            return "recognize"
        if fmt == "body_superpower":
            return "survive"
        return "signal"
    return action


def _usable_cue(cue: str) -> str:
    cue = (cue or "").lower().strip()
    if cue in {"", "cue"}:
        return "body cue"
    return {
        "ears": "ear position",
        "eyes": "eye contact",
        "feet": "footwork",
        "hooves": "hoof movement",
        "feathers": "feather position",
        "movement": "movement",
        "body": "body posture",
        "call": "call",
    }.get(cue, cue)


def _benefit(action: str, fmt: str) -> str:
    if fmt == "animal_memory":
        return "recognize familiar faces faster"
    if action in {"escape", "hide", "protect", "survive"}:
        return "stay safe when the moment changes"
    if action in {"hunt", "trick", "signal", "call"}:
        return "send a clear signal before the next move"
    return "solve one visible problem in the scene"


def _clean_tags(existing: object, subject: str, category: str) -> list[str]:
    tags: list[str] = []
    for tag in existing if isinstance(existing, list) else []:
        text = str(tag or "").strip()
        words = {word.lower() for word in re.findall(r"[A-Za-z]+", text)}
        if text and not (words & ANIMAL_TAG_WORDS):
            tags.append(text)
    preferred = [subject.lower(), category.lower(), "animal facts"]
    out: list[str] = []
    for tag in preferred + tags:
        clean = re.sub(r"\s+", " ", str(tag or "")).strip()
        if clean and clean.lower() not in {item.lower() for item in out}:
            out.append(clean)
    return out[:8]


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
        "encoding_artifact", "stacked_animal_title", "robotic_use_loop",
        "robotic_because_of_this", "robotic_not_random_title",
        "robotic_not_accident_title",
        "generic_watch_cue", "generic_visible_cue",
        "generic_hiding_plain_sight", "robotic_not_random_line",
        "generic_payoff_filler", "robotic_memory_title",
        "bad_plural_verb", "bad_because_changes",
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
    subject = _plural_subject(animal)
    lower_subject = _lower_plural_subject(animal)
    benefit = _benefit(action, fmt)
    if fmt == "animal_memory":
        title = f"{subject} recognize faces through {cue}"
        hook = f"{subject} recognize a familiar signal before they react."
    elif fmt == "body_superpower":
        title = f"{subject} rely on {cue} to {action}"
        hook = f"{subject} rely on {cue} before the move."
    else:
        title = f"{subject} reveal the next move through {cue}"
        hook = f"{subject} reveal the next move through one visible signal."
    script = (
        f"{hook} Watch the {cue} first. "
        f"In this clip, {lower_subject} use that detail to {benefit}. "
        f"The body gives away the story before the final move, so the payoff is visible on the replay."
    )
    out.update({
        "seo_title": title[:60],
        "title": title[:60],
        "hook": hook,
        "script": script,
        "lead": script[:400],
        "thumbnail_text": f"{subject.upper()} {cue.upper()}"[:28],
        "yt_tags": _clean_tags(out.get("yt_tags"), lower_subject, str(out.get("category") or "")),
        "local_rewrite": {"applied": True, "reasons": reasons, "method": "deterministic_rescue"},
    })
    if editorial_issues(out):
        return story, False
    return out, True
