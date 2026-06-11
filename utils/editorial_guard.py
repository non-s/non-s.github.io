"""Final editorial safety checks for autonomous Shorts copy."""

from __future__ import annotations

import re

ENCODING_SCARS = ("Ã", "â€™", "â€œ", "â€", "ðŸ", "�")

ANIMAL_WORDS = {
    "ant",
    "ants",
    "bee",
    "bees",
    "bird",
    "birds",
    "cat",
    "cats",
    "chicken",
    "chickens",
    "cow",
    "cows",
    "deer",
    "dog",
    "dogs",
    "duck",
    "ducks",
    "duckling",
    "ducklings",
    "elephant",
    "elephants",
    "goat",
    "goats",
    "horse",
    "horses",
    "lion",
    "lions",
    "macaw",
    "macaws",
    "monkey",
    "monkeys",
    "orangutan",
    "orangutans",
    "owl",
    "owls",
    "penguin",
    "penguins",
    "shark",
    "sharks",
    "sheep",
    "snake",
    "snakes",
    "tiger",
    "tigers",
    "whale",
    "whales",
}

SINGULAR_SUBJECTS = (
    "ant", "bear", "bee", "beetle", "bird", "butterfly", "cat",
    "chicken", "cow", "dog", "dolphin", "dragonfly", "duck",
    "duckling", "elephant", "fox", "goat", "horse", "lion", "macaw",
    "mantis", "monkey", "mushroom", "octopus", "orangutan", "owl",
    "parrot", "penguin", "plant", "seal", "shark", "snake", "storm",
    "tiger", "turtle", "volcano", "whale", "wolf",
)

NON_ANIMAL_CATEGORIES = {
    "earth_from_space", "ecosystems", "forests", "fungi", "geology",
    "plants", "rare_phenomena", "rivers", "volcanoes", "weather",
}

NON_ANIMAL_BODY_TERMS = (
    "body cue", "body posture", "faces", "paws", "tail", "beak",
    "feather", "feathers", "hoof", "hooves",
)

ROBOTIC_TITLE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("robotic_use_loop", r"\b[a-z]+s?\s+use\s+(their|its)\s+[a-z]+\s+to\s+use\b"),
    ("robotic_because_of_this", r"\bbecause of this\s+(ears|eyes|feet|hooves|feathers|cue|body|movement|call|tail|nose|beak|paws|wings|wing)\b"),
    ("robotic_not_random_title", r"\bwhy\s+[a-z]+\s+[a-z]+\s+is not random\b"),
    ("robotic_not_accident_title", r"\bnot doing this by accident\b"),
    ("generic_watch_cue", r"\bwatch the cue when\b"),
    ("generic_visible_cue", r"\bone visible cue for a reason\b"),
    ("generic_hiding_plain_sight", r"\bhiding in plain sight\b"),
    ("bad_plural_verb", r"\b[a-z]+s\s+(gives|turns|makes|changes|reveals|uses|relies|recognizes|remembers|signals|hunts|grows|moves)\b"),
    (
        "bad_singular_subject_verb",
        r"\b(" + "|".join(SINGULAR_SUBJECTS) + r")\s+(turn|rely|recognize|reveal|show|change|use|remember|signal|hunt|grow|move|fake|trick|protect|survive)\b",
    ),
    ("bad_domain_plural", r"\b(earths|weathers|wildlifes)\b"),
)

ROBOTIC_TEXT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("robotic_use_loop", r"\buse\s+(their|its)\s+[a-z]+\s+to\s+use\b"),
    ("robotic_not_random_line", r"\b(the\s+)?(cue|body|movement|ears|eyes|feet|hooves|feathers)\s+is not random\b"),
    ("bad_because_changes", r"\bbecause the\s+[a-z]+\s+changes\b"),
    ("generic_payoff_filler", r"\bthat is why this moment matters before the payoff\b"),
)


def _text(story: dict, fields: tuple[str, ...]) -> str:
    return " ".join(str(story.get(field) or "") for field in fields)


def _stacked_animals(title: str) -> bool:
    words = re.findall(r"[A-Za-z]+", title.lower())
    return len(words) >= 2 and words[0] in ANIMAL_WORDS and words[1] in ANIMAL_WORDS


def editorial_issues(story: dict, *, include_script: bool = True) -> list[str]:
    """Return copy issues that should hold or rewrite a candidate."""
    title = _text(story, ("seo_title", "title")).strip()
    body_fields = ("seo_title", "title", "hook", "thumbnail_text")
    if include_script:
        body_fields = body_fields + ("script", "description")
    body = _text(story, body_fields)
    title_lower = title.lower()
    body_lower = body.lower()
    issues: list[str] = []
    if any(marker in body for marker in ENCODING_SCARS):
        issues.append("encoding_artifact")
    if _stacked_animals(title):
        issues.append("stacked_animal_title")
    for name, pattern in ROBOTIC_TITLE_PATTERNS:
        if re.search(pattern, title_lower):
            issues.append(name)
    for name, pattern in ROBOTIC_TEXT_PATTERNS:
        if re.search(pattern, body_lower):
            issues.append(name)
    category = str(story.get("category") or "").lower()
    if category in NON_ANIMAL_CATEGORIES and any(term in body_lower for term in NON_ANIMAL_BODY_TERMS):
        issues.append("non_animal_body_language")
    if re.search(r"\b[a-z]+s?\s+remember\s+because of this\b", title_lower):
        issues.append("robotic_memory_title")
    return sorted(set(issues))


def editorial_verdict(story: dict, *, include_script: bool = True) -> dict:
    issues = editorial_issues(story, include_script=include_script)
    return {
        "approved": not issues,
        "state": "approved" if not issues else "held",
        "issues": issues,
    }
