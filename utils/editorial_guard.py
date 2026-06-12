"""Final editorial safety checks for autonomous Shorts copy."""

from __future__ import annotations

import re

ENCODING_SCARS = ("Ã", "â€™", "â€œ", "â€", "ðŸ", "�")

MOJIBAKE_SCARS = ("\u00e2\u20ac", "\u00f0\u0178", "\ufffd")

ANIMAL_WORDS = {
    "ant",
    "ants",
    "bear",
    "bears",
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
    "dolphin",
    "dolphins",
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
    "wolf",
    "wolves",
}

SINGULAR_SUBJECTS = (
    "ant",
    "bear",
    "bee",
    "beetle",
    "bird",
    "butterfly",
    "cat",
    "chicken",
    "cow",
    "dog",
    "dolphin",
    "dragonfly",
    "duck",
    "duckling",
    "elephant",
    "fox",
    "goat",
    "horse",
    "lion",
    "macaw",
    "mantis",
    "monkey",
    "mushroom",
    "octopus",
    "orangutan",
    "owl",
    "parrot",
    "penguin",
    "plant",
    "seal",
    "shark",
    "snake",
    "storm",
    "tiger",
    "turtle",
    "volcano",
    "whale",
    "wolf",
)

NON_ANIMAL_CATEGORIES = {
    "earth_from_space",
    "ecosystems",
    "forests",
    "fungi",
    "geology",
    "plants",
    "rare_phenomena",
    "rivers",
    "volcanoes",
    "weather",
}

NON_ANIMAL_BODY_TERMS = (
    "body cue",
    "body posture",
    "faces",
    "paws",
    "tail",
    "beak",
    "feather",
    "feathers",
    "hoof",
    "hooves",
)

ROBOTIC_TITLE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("robotic_use_loop", r"\b[a-z]+s?\s+use\s+(their|its)\s+[a-z]+\s+to\s+use\b"),
    ("robotic_rely_loop", r"\b[a-z]+s?\s+rely\s+on\s+[a-z\s]+\s+to\s+rely\b"),
    (
        "robotic_because_of_this",
        r"\bbecause of this\s+(ears|eyes|feet|hooves|feathers|cue|body|movement|call|tail|nose|beak|paws|wings|wing)\b",
    ),
    ("robotic_not_random_title", r"\bwhy\s+[a-z]+\s+[a-z]+\s+is not random\b"),
    ("robotic_not_accident_title", r"\bnot doing this by accident\b"),
    ("generic_watch_cue", r"\bwatch the cue when\b"),
    ("generic_visible_cue", r"\bone visible cue for a reason\b"),
    ("generic_signal_cue", r"\bsignal cue\b"),
    ("generic_detail_clue_title", r"\bturn the detail into the clue\b"),
    ("generic_next_move_movement", r"\breveal the next move through movement\b"),
    (
        "generic_body_posture_template",
        r"\b(?:rely on body posture|recognize faces through body posture|signal the next move with body posture|through body cue)\b",
    ),
    (
        "generic_detail_template",
        r"\b(?:signal the next move with detail|watch the detail when|the detail that explains)\b",
    ),
    ("generic_movement_template", r"\b(?:signal the next move with movement|rely on movement to signal)\b"),
    ("generic_false_face_memory", r"\brecognize faces through (?!face|eye)[a-z-]+(?:\s+[a-z-]+)?\b"),
    (
        "generic_signal_through_body_cue",
        r"\brecognize signals through (?:body cue|body posture|ear position|eye contact|face shape|feeding cue|fin movement|first movement|flipper movement|hand movement|head movement|tail position|wing movement|wing position|beak movement|ear|ears|eye|eyes|face|faces|feet|fin|fins|flipper|flippers|hand|hands|head|hoof|hooves|leg|legs|nose|paw|paws|tail|wing|wings)\b",
    ),
    (
        "generic_rely_to_signal_cue",
        r"\brely on (?:the )?(?:body cue|body posture|ear position|eye contact|face shape|feeding cue|fin movement|first movement|flipper movement|hand movement|head movement|tail position|wing movement|wing position|beak movement|ear|ears|eye|eyes|face|faces|feet|fin|fins|flipper|flippers|hand|hands|head|hoof|hooves|leg|legs|nose|paw|paws|tail|wing|wings) to signal\b",
    ),
    (
        "generic_next_move_cue",
        r"\bsignal the next move with (?:body cue|body posture|ear position|eye contact|face shape|feeding cue|fin movement|first movement|flipper movement|hand movement|head movement|tail position|wing movement|wing position|beak movement|ear|ears|eye|eyes|face|faces|feet|fin|fins|flipper|flippers|hand|hands|head|hoof|hooves|leg|legs|nose|paw|paws|tail|wing|wings)\b",
    ),
    ("generic_movement_changes_title", r"\bthis (?:(?:first )?movement|first move) changes what [a-z]+s? do next\b"),
    ("generic_first_movement_reason", r"\brely on (?:the )?first movement for a reason\b"),
    (
        "generic_first_move_title",
        r"\b(?:read the moment from one first move|react differently when the first move appears|rely on (?:the )?first movement to [a-z]+)\b",
    ),
    ("awkward_ear_movement_changes", r"\bwhen the ear movement changes\b"),
    ("awkward_this_ear_position_changes", r"\bthis ear position changes what [a-z]+s? do next\b"),
    ("awkward_head_cue_title", r"\bhead cue\b"),
    ("generic_hiding_plain_sight", r"\bhiding in plain sight\b"),
    ("stitched_category_title", r"^\s*[a-z]+s?\s+this\s+[a-z]"),
    ("truncated_heres_title", r"\b(here'?s|here is)\s*$"),
    (
        "bad_plural_verb",
        r"\b[a-z]+s\s+(gives|turns|makes|changes|reveals|uses|relies|recognizes|remembers|signals|hunts|grows|moves)\b",
    ),
    (
        "bad_singular_subject_verb",
        r"\b("
        + "|".join(SINGULAR_SUBJECTS)
        + r")\s+(turn|rely|recognize|reveal|show|change|use|remember|signal|hunt|grow|move|fake|trick|protect|survive)\b",
    ),
    ("bad_domain_plural", r"\b(earths|weathers|wildlifes)\b"),
)

ROBOTIC_TEXT_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        "operator_meta_language",
        r"\b(?:previous [a-z]+ short worked because|this sequel keeps|same proven pattern|winning shape|"
        r"original topic pulled attention|this remake cuts|proven wild brief topic)\b",
    ),
    ("robotic_use_loop", r"\buse\s+(their|its)\s+[a-z]+\s+to\s+use\b"),
    ("robotic_rely_loop", r"\brely\s+on\s+[a-z\s]+\s+to\s+rely\b"),
    ("robotic_not_random_line", r"\b(the\s+)?(cue|body|movement|ears|eyes|feet|hooves|feathers)\s+is not random\b"),
    ("bad_because_changes", r"\bbecause the\s+[a-z]+\s+changes\b"),
    ("generic_signal_cue", r"\bsignal cue\b"),
    ("generic_detail_clue_title", r"\bturn the detail into the clue\b"),
    ("generic_next_move_movement", r"\breveal the next move through movement\b"),
    (
        "generic_body_posture_template",
        r"\b(?:rely on body posture|recognize faces through body posture|signal the next move with body posture|through body cue)\b",
    ),
    (
        "generic_detail_template",
        r"\b(?:signal the next move with detail|watch the detail when|the detail that explains)\b",
    ),
    ("generic_movement_template", r"\b(?:signal the next move with movement|rely on movement to signal)\b"),
    ("generic_false_face_memory", r"\brecognize faces through (?!face|eye)[a-z-]+(?:\s+[a-z-]+)?\b"),
    (
        "generic_signal_through_body_cue",
        r"\brecognize signals through (?:body cue|body posture|ear position|eye contact|face shape|feeding cue|fin movement|first movement|flipper movement|hand movement|head movement|tail position|wing movement|wing position|beak movement|ear|ears|eye|eyes|face|faces|feet|fin|fins|flipper|flippers|hand|hands|head|hoof|hooves|leg|legs|nose|paw|paws|tail|wing|wings)\b",
    ),
    (
        "generic_rely_to_signal_cue",
        r"\brely on (?:the )?(?:body cue|body posture|ear position|eye contact|face shape|feeding cue|fin movement|first movement|flipper movement|hand movement|head movement|tail position|wing movement|wing position|beak movement|ear|ears|eye|eyes|face|faces|feet|fin|fins|flipper|flippers|hand|hands|head|hoof|hooves|leg|legs|nose|paw|paws|tail|wing|wings) to signal\b",
    ),
    (
        "generic_next_move_cue",
        r"\bsignal the next move with (?:body cue|body posture|ear position|eye contact|face shape|feeding cue|fin movement|first movement|flipper movement|hand movement|head movement|tail position|wing movement|wing position|beak movement|ear|ears|eye|eyes|face|faces|feet|fin|fins|flipper|flippers|hand|hands|head|hoof|hooves|leg|legs|nose|paw|paws|tail|wing|wings)\b",
    ),
    ("generic_movement_changes_title", r"\bthis (?:(?:first )?movement|first move) changes what [a-z]+s? do next\b"),
    ("generic_first_movement_reason", r"\brely on (?:the )?first movement for a reason\b"),
    (
        "generic_first_move_title",
        r"\b(?:read the moment from one first move|react differently when the first move appears|rely on (?:the )?first movement to [a-z]+)\b",
    ),
    ("awkward_ear_movement_changes", r"\bwhen the ear movement changes\b"),
    ("awkward_this_ear_position_changes", r"\bthis ear position changes what [a-z]+s? do next\b"),
    ("generic_payoff_filler", r"\bthat is why this moment matters before the payoff\b"),
)


def _text(story: dict, fields: tuple[str, ...]) -> str:
    return " ".join(str(story.get(field) or "") for field in fields)


def _stacked_animals(title: str) -> bool:
    words = re.findall(r"[A-Za-z]+", title.lower())
    return len(words) >= 2 and words[0] in ANIMAL_WORDS and words[1] in ANIMAL_WORDS


def _animal_forms(word: str) -> set[str]:
    irregular = {
        "wolves": "wolf",
        "wolf": "wolves",
    }
    forms = {word}
    if word in irregular:
        forms.add(irregular[word])
    if word.endswith("ies"):
        forms.add(word[:-3] + "y")
    elif word.endswith("ves"):
        forms.add(word[:-3] + "f")
    elif word.endswith("ses"):
        forms.add(word[:-2])
    elif word.endswith("s"):
        forms.add(word[:-1])
    return forms | {f"{item}s" for item in list(forms) if not item.endswith("s")}


def _repeated_leading_animal(title: str) -> bool:
    words = re.findall(r"[A-Za-z]+", title.lower())
    if len(words) < 4 or words[0] not in ANIMAL_WORDS:
        return False
    forms = _animal_forms(words[0])
    return any(word in forms for word in words[1:])


def editorial_issues(story: dict, *, include_script: bool = True) -> list[str]:
    """Return copy issues that should hold or rewrite a candidate."""
    title = str(story.get("seo_title") or story.get("title") or "").strip()
    body_fields = ("seo_title", "title", "hook", "thumbnail_text")
    if include_script:
        body_fields = body_fields + ("script", "description", "yt_description")
    body = _text(story, body_fields)
    title_lower = title.lower()
    body_lower = body.lower()
    issues: list[str] = []
    if any(marker in body for marker in ENCODING_SCARS + MOJIBAKE_SCARS):
        issues.append("encoding_artifact")
    if _stacked_animals(title):
        issues.append("stacked_animal_title")
    if _repeated_leading_animal(title):
        issues.append("stitched_repeated_animal_title")
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
