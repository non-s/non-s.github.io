"""Deterministic rescue rewrites before rejecting usable animal footage."""

from __future__ import annotations

import re

from utils.packaging import extract_action, extract_animal, extract_cue
from utils.story_intelligence import classify_format
from utils.editorial_guard import editorial_issues

ANIMAL_TAG_WORDS = {
    "ant",
    "ants",
    "bear",
    "bears",
    "bee",
    "bees",
    "beetle",
    "beetles",
    "bird",
    "birds",
    "butterfly",
    "butterflies",
    "cat",
    "cats",
    "chicken",
    "chickens",
    "cow",
    "cows",
    "deer",
    "dog",
    "dogs",
    "dolphin",
    "dolphins",
    "dragonfly",
    "dragonflies",
    "duck",
    "ducks",
    "duckling",
    "ducklings",
    "elephant",
    "elephants",
    "fox",
    "foxes",
    "goat",
    "goats",
    "horse",
    "horses",
    "lion",
    "lions",
    "macaw",
    "macaws",
    "mantis",
    "mantises",
    "monkey",
    "monkeys",
    "octopus",
    "octopuses",
    "orangutan",
    "orangutans",
    "owl",
    "owls",
    "parrot",
    "parrots",
    "penguin",
    "penguins",
    "seal",
    "seals",
    "shark",
    "sharks",
    "sheep",
    "snake",
    "snakes",
    "tiger",
    "tigers",
    "turtle",
    "turtles",
    "whale",
    "whales",
    "wolf",
    "wolves",
}

FALLBACK_CUES = {
    "ant": "antenna movement",
    "ants": "antenna movement",
    "bear": "tail position",
    "bears": "tail position",
    "bee": "wing movement",
    "bees": "wing movement",
    "beetle": "antenna movement",
    "beetles": "antenna movement",
    "bird": "wing position",
    "birds": "wing position",
    "butterfly": "wing movement",
    "butterflies": "wing movement",
    "cat": "ear position",
    "cats": "ear position",
    "chicken": "head movement",
    "chickens": "head movement",
    "cow": "ear position",
    "cows": "ear position",
    "deer": "ear position",
    "dog": "tail position",
    "dogs": "tail position",
    "dolphin": "fin movement",
    "dolphins": "fin movement",
    "dragonfly": "wing movement",
    "dragonflies": "wing movement",
    "duck": "wing position",
    "ducks": "wing position",
    "duckling": "wing position",
    "ducklings": "wing position",
    "elephant": "ear movement",
    "elephants": "ear movement",
    "fox": "tail position",
    "foxes": "tail position",
    "goat": "ear position",
    "goats": "ear position",
    "horse": "ear position",
    "horses": "ear position",
    "lion": "ear position",
    "lions": "ear position",
    "macaw": "beak movement",
    "macaws": "beak movement",
    "mantis": "front-leg movement",
    "mantises": "front-leg movement",
    "monkey": "hand movement",
    "monkeys": "hand movement",
    "octopus": "arm movement",
    "octopuses": "arm movement",
    "orangutan": "hand movement",
    "orangutans": "hand movement",
    "owl": "eye contact",
    "owls": "eye contact",
    "parrot": "beak movement",
    "parrots": "beak movement",
    "penguin": "flipper movement",
    "penguins": "flipper movement",
    "seal": "whisker movement",
    "seals": "whisker movement",
    "shark": "fin movement",
    "sharks": "fin movement",
    "sheep": "ear position",
    "snake": "head movement",
    "snakes": "head movement",
    "tiger": "ear position",
    "tigers": "ear position",
    "turtle": "head movement",
    "turtles": "head movement",
    "whale": "fin movement",
    "whales": "fin movement",
    "wolf": "tail position",
    "wolves": "tail position",
}


def _animal(text: str) -> str:
    normalised = re.sub(r"[-_/]+", " ", text or "")
    for word in re.findall(r"[A-Za-z][A-Za-z']+", normalised):
        low = word.lower().replace("'s", "")
        if low in {
            "cow",
            "cows",
            "duck",
            "ducks",
            "duckling",
            "ducklings",
            "chicken",
            "chickens",
            "deer",
            "horse",
            "horses",
            "tiger",
            "tigers",
            "penguin",
            "penguins",
            "goat",
            "goats",
            "wolf",
            "wolves",
            "bear",
            "bears",
            "bird",
            "birds",
            "owl",
            "owls",
            "cat",
            "cats",
            "dog",
            "dogs",
            "lion",
            "lions",
            "elephant",
            "elephants",
            "dolphin",
            "dolphins",
            "whale",
            "whales",
            "octopus",
            "octopuses",
            "seal",
            "seals",
            "fox",
            "foxes",
            "sheep",
            "parrot",
            "parrots",
            "macaw",
            "macaws",
            "orangutan",
            "orangutans",
            "monkey",
            "monkeys",
            "donkey",
            "donkeys",
            "shark",
            "sharks",
            "bee",
            "bees",
            "butterfly",
            "butterflies",
            "ant",
            "ants",
            "beetle",
            "beetles",
            "mantis",
            "mantises",
            "dragonfly",
            "dragonflies",
            "snake",
            "snakes",
            "chameleon",
            "chameleons",
            "turtle",
            "turtles",
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
    if action in {"show", "watch", "cue", "use", "changes", "change", "rely", ""}:
        if fmt == "animal_memory":
            return "recognize"
        if fmt == "body_superpower":
            return "survive"
        return "signal"
    return action


def _fallback_cue(animal: str) -> str:
    return FALLBACK_CUES.get(_lower_subject(animal), "first movement")


def _usable_cue(cue: str, animal: str = "") -> str:
    cue = (cue or "").lower().strip()
    if cue in {"", "cue", "movement", "first movement", "body", "body cue", "body posture", "detail"}:
        return _fallback_cue(animal)
    return {
        "ears": "ear position",
        "ear": "ear position",
        "eyes": "eye contact",
        "tail": "tail position",
        "paw": "paw position",
        "paws": "paw position",
        "wing": "wing position",
        "wings": "wing position",
        "feet": "footwork",
        "hooves": "hoof movement",
        "feathers": "feather position",
        "head": "head movement",
        "hand": "hand movement",
        "hands": "hand movement",
        "fin": "fin movement",
        "fins": "fin movement",
        "beak": "beak movement",
        "flipper": "flipper movement",
        "flippers": "flipper movement",
        "antenna": "antenna movement",
        "antennae": "antenna movement",
        "whisker": "whisker movement",
        "whiskers": "whisker movement",
        "movement": "movement",
        "body": "body posture",
        "call": "call",
    }.get(cue, cue)


def _benefit(action: str, fmt: str) -> str:
    if fmt == "animal_memory":
        return "recognize familiar signals faster"
    if action in {"escape", "hide", "protect", "survive"}:
        return "stay safe when the moment changes"
    if action in {"hunt", "trick", "signal", "call"}:
        return "send a clear signal before the next move"
    return "solve one visible problem in the scene"


def _source_context(story: dict) -> str:
    related = story.get("sequel_of") or story.get("remake_of") or {}
    if not isinstance(related, dict):
        related = {}
    return " ".join(
        str(value or "")
        for value in (
            related.get("title"),
            story.get("source_title"),
            story.get("raw_title"),
            story.get("title"),
            story.get("seo_title"),
            story.get("category"),
        )
    )


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


def _cue_moment(cue: str) -> str:
    cue = str(cue or "").lower().strip()
    return {
        "ear position": "their ears shift",
        "ear movement": "their ears move",
        "ear": "their ears shift",
        "ears": "their ears shift",
        "head movement": "their heads move",
        "head": "their heads move",
        "fin movement": "their fins shift",
        "fin": "their fins shift",
        "fins": "their fins shift",
        "hand movement": "their hands move",
        "hand": "their hands move",
        "hands": "their hands move",
        "tail position": "their tails lift",
        "tail": "their tails lift",
        "wing movement": "their wings move",
        "wing position": "their wings shift",
        "wing": "their wings move",
        "wings": "their wings move",
        "paw": "their paws move",
        "paws": "their paws move",
        "beak movement": "their beaks move",
        "beak": "their beaks move",
        "flipper movement": "their flippers shift",
        "flipper": "their flippers shift",
        "flippers": "their flippers shift",
        "first movement": "the first move appears",
        "feeding cue": "the feeding cue appears",
        "object group": "the object group changes",
        "number cue": "the number cue appears",
    }.get(cue, f"the {cue} changes")


def _cue_signal(cue: str) -> str:
    cue = str(cue or "").lower().strip()
    return {
        "ear position": "ear shift",
        "ear movement": "ear shift",
        "ear": "ear shift",
        "ears": "ear shift",
        "head movement": "head movement",
        "head": "head movement",
        "fin movement": "fin cue",
        "fin": "fin cue",
        "fins": "fin cue",
        "hand movement": "hand cue",
        "hand": "hand cue",
        "hands": "hand cue",
        "tail position": "tail lift",
        "tail": "tail lift",
        "wing movement": "wing beat",
        "wing position": "wing angle",
        "wing": "wing beat",
        "wings": "wing beat",
        "paws": "paw cue",
        "paw": "paw cue",
        "beak movement": "beak cue",
        "beak": "beak cue",
        "flipper movement": "flipper cue",
        "flipper": "flipper cue",
        "flippers": "flipper cue",
        "first movement": "first move",
        "feeding cue": "feeding cue",
        "object group": "object group",
        "number cue": "number cue",
    }.get(cue, cue or "first cue")


def rescue_story(story: dict, reasons: list[str]) -> tuple[dict, bool]:
    """Return a locally rewritten story when the issue is editorial, not visual."""
    reasons = list(reasons)
    if "off_topic_visual" in reasons:
        return story, False
    if not any(
        reason in reasons
        for reason in (
            "repetitive_title_template",
            "generic_script_template",
            "script_word_loop",
            "duplicate_script",
            "rewrite_packaging",
            "missing_visible_cue",
            "missing_action_word",
            "title_needs_stronger_shape",
            "animal_not_immediately_clear",
            "no_action_promise",
            "payoff_not_explicit",
            "missing_visual_cue",
            "generic_creator_language",
            "hook_shape_weak",
            "title_shape_weak",
            "script_subject_mismatch",
            "encoding_artifact",
            "stacked_animal_title",
            "robotic_use_loop",
            "robotic_because_of_this",
            "robotic_not_random_title",
            "robotic_not_accident_title",
            "generic_watch_cue",
            "generic_visible_cue",
            "generic_visual_cue_language",
            "generic_signal_cue",
            "generic_detail_clue_title",
            "generic_next_move_movement",
            "generic_body_posture_template",
            "generic_detail_template",
            "generic_movement_template",
            "generic_false_face_memory",
            "generic_signal_through_body_cue",
            "generic_rely_to_signal_cue",
            "generic_next_move_cue",
            "generic_movement_changes_title",
            "generic_first_movement_reason",
            "generic_first_move_title",
            "awkward_ear_movement_changes",
            "awkward_this_ear_position_changes",
            "awkward_head_cue_title",
            "generic_clickbait_language",
            "generic_hiding_plain_sight",
            "robotic_not_random_line",
            "generic_payoff_filler",
            "robotic_memory_title",
            "bad_plural_verb",
            "bad_singular_subject_verb",
            "bad_because_changes",
            "truncated_heres_title",
            "stitched_category_title",
            "stitched_repeated_animal_title",
            "script_length_risk",
            "robotic_rely_loop",
        )
    ):
        return story, False
    out = dict(story)
    text = " ".join(str(out.get(k) or "") for k in ("title", "seo_title", "hook", "script", "category"))
    visual_text = " ".join(
        str(value or "")
        for value in (
            out.get("source_url"),
            out.get("url"),
            out.get("source_title"),
            out.get("raw_title"),
            _source_context(out),
            out.get("title"),
            out.get("category"),
        )
    )
    animal = _animal(visual_text)
    if animal == "Animals":
        animal = extract_animal(out)
    if animal.lower() == "animal":
        animal = _animal(text)
    fmt = classify_format(text)
    cue = _usable_cue(extract_cue(out), animal)
    action = _usable_action(extract_action(out), fmt)
    subject = _plural_subject(animal)
    lower_subject = _lower_plural_subject(animal)
    benefit = _benefit(action, fmt)
    if fmt == "animal_memory":
        if cue in {"face", "faces", "face cue", "eye contact", "eyes"}:
            title = f"{subject} remember familiar faces by sight"
            hook = f"{subject} recognize familiar faces."
        else:
            title = f"{subject} react differently when {_cue_moment(cue)}"
            hook = f"{subject} read one visible signal."
    elif fmt == "body_superpower":
        if action == "signal":
            title = f"{subject} read the moment from one {_cue_signal(cue)}"
            hook = f"{subject} read one visible signal."
        else:
            title = f"{subject} rely on {cue} to {action}"
            hook = f"{subject} rely on {cue}."
    else:
        title = f"{subject} read the moment from one {_cue_signal(cue)}"
        hook = f"{subject} reveal one visible signal."
    script = (
        f"{hook} Watch {cue}, because {lower_subject} use it to {benefit}. "
        f"The payoff appears before the final move. "
        f"That is why viewers can replay the first second and catch the hidden cue before it pays off again."
    )
    out.update(
        {
            "seo_title": title[:60],
            "title": title[:60],
            "hook": hook,
            "script": script,
            "lead": script[:400],
            "thumbnail_text": f"{subject.upper()} {cue.upper()}"[:28],
            "yt_tags": _clean_tags(out.get("yt_tags"), lower_subject, str(out.get("category") or "")),
            "local_rewrite": {"applied": True, "reasons": reasons, "method": "deterministic_rescue"},
        }
    )
    if editorial_issues(out):
        return story, False
    return out, True
