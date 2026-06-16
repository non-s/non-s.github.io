"""Senior YouTube operator heuristics for every Short.

This is not artificial consciousness. It is a deterministic executive
producer layer: every video must have a viewer promise, a retention path,
a replay reason, and a post-publish learning plan before it ships.
"""

from __future__ import annotations

import re
from collections import Counter

from utils.story_intelligence import audit_hook, audit_title, classify_format

ACTION_WORDS = {
    "fake",
    "protect",
    "escape",
    "remember",
    "recognize",
    "call",
    "hear",
    "hide",
    "slide",
    "hunt",
    "plan",
    "trick",
    "use",
    "warn",
    "follow",
    "choose",
    "save",
    "signal",
    "learn",
    "change",
    "disappear",
    "blend",
    "erupt",
    "glow",
    "flow",
    "form",
    "grow",
    "freeze",
    "melt",
    "restore",
    "recover",
    "connect",
    "communicate",
    "build",
    "built",
    "collapse",
    "coordinate",
    "count",
    "dance",
    "explode",
    "rely",
    "aim",
    "carry",
    "carries",
    "cover",
    "covered",
    "fly",
    "leave",
    "lay",
    "wear",
    "cool",
    "compare",
    "detect",
    "feel",
    "imprint",
    "judge",
    "lock",
    "make",
    "measure",
    "read",
    "record",
    "reveal",
    "sample",
    "sense",
    "send",
    "smell",
    "stabilize",
    "store",
    "steer",
    "taste",
    "track",
    "trap",
    "wash",
}
WEAK_WORDS = {"secret", "another", "amazing", "incredible", "interesting", "thing"}
GENERIC_CUE_WORDS = {"body", "cue", "movement"}
VISIBLE_CUE_WORDS = {
    "eyes",
    "ears",
    "tail",
    "beak",
    "wing",
    "wings",
    "feet",
    "paw",
    "paws",
    "horn",
    "horns",
    "sound",
    "call",
    "stripe",
    "feathers",
    "movement",
    "cue",
    "body",
    "skin",
    "texture",
    "colour",
    "color",
    "nose",
    "face",
    "head",
    "hoof",
    "hooves",
    "fin",
    "fins",
    "gill",
    "gills",
    "antenna",
    "antennae",
    "pupil",
    "pupils",
    "hand",
    "hands",
    "arm",
    "arms",
    "leg",
    "legs",
    "flipper",
    "flippers",
    "whisker",
    "whiskers",
    "leaf",
    "leaves",
    "roots",
    "bark",
    "canopy",
    "mushroom",
    "mycelium",
    "lava",
    "crater",
    "ash",
    "cloud",
    "lightning",
    "wave",
    "current",
    "glacier",
    "rock",
    "rings",
    "reef",
    "coral",
    "sky",
    "ice",
    "air",
    "bubbles",
    "dance",
    "decoy",
    "display",
    "electric",
    "heat",
    "map",
    "nest",
    "pore",
    "pores",
    "scent",
    "scale",
    "scales",
    "tongue",
    "vision",
}

BROKEN_PACKAGING_PATTERNS = (
    re.compile(r"\b(?:use|uses|using)\b[^.!?]{0,48}\bto use\b", re.I),
    re.compile(r"\bbecause of this\s+(?:ears|eyes|feet|hooves|wings|fins|gills|horns|paws|leaves|roots)\b", re.I),
    re.compile(r"\b(?:sheep|deer|fish|moose)\s+(?:uses|signals|remembers|hears|hunts)\b", re.I),
)
GENERIC_PACKAGING_PATTERNS = (
    re.compile(r"\bsignal cue\b", re.I),
    re.compile(r"\bturn the detail into the clue\b", re.I),
    re.compile(r"\breveal the next move through movement\b", re.I),
    re.compile(
        r"\b(?:rely on body posture|recognize faces through body posture|signal the next move with body posture|through body cue)\b",
        re.I,
    ),
    re.compile(r"\b(?:signal the next move with detail|watch the detail when|the detail that explains)\b", re.I),
    re.compile(r"\b(?:signal the next move with movement|rely on movement to signal)\b", re.I),
    re.compile(r"\b(?:rely on|through|watch|use|with)\s+(?:the\s+)?(?:first\s+)?movement\b", re.I),
    re.compile(
        r"\b(?:rely on|through|watch|use|with)\s+(?:the\s+)?"
        r"(?:antenna|beak|ear|fin|flipper|hand|head|tail|whisker|wing)\s+movement\b",
        re.I,
    ),
    re.compile(r"\brecognize faces through (?!face|eye)[a-z-]+(?:\s+[a-z-]+)?\b", re.I),
    re.compile(
        r"\brecognize signals through (?:body cue|body posture|ear position|eye contact|face shape|feeding cue|fin movement|first movement|flipper movement|hand movement|head movement|tail position|wing movement|wing position|beak movement|ear|ears|eye|eyes|face|faces|feet|fin|fins|flipper|flippers|hand|hands|head|hoof|hooves|leg|legs|nose|paw|paws|tail|wing|wings)\b",
        re.I,
    ),
    re.compile(
        r"\brely on (?:the )?(?:body cue|body posture|ear position|eye contact|face shape|feeding cue|fin movement|first movement|flipper movement|hand movement|head movement|tail position|wing movement|wing position|beak movement|ear|ears|eye|eyes|face|faces|feet|fin|fins|flipper|flippers|hand|hands|head|hoof|hooves|leg|legs|nose|paw|paws|tail|wing|wings) to signal\b",
        re.I,
    ),
    re.compile(
        r"\bsignal the next move with (?:body cue|body posture|ear position|eye contact|face shape|feeding cue|fin movement|first movement|flipper movement|hand movement|head movement|tail position|wing movement|wing position|beak movement|ear|ears|eye|eyes|face|faces|feet|fin|fins|flipper|flippers|hand|hands|head|hoof|hooves|leg|legs|nose|paw|paws|tail|wing|wings)\b",
        re.I,
    ),
    re.compile(r"\bthis (?:(?:first )?movement|first move) changes what [a-z]+s? do next\b", re.I),
    re.compile(r"\brely on (?:the )?first movement for a reason\b", re.I),
    re.compile(
        r"\b(?:read the moment from one first move|react differently when the first move appears|rely on (?:the )?first movement to [a-z]+)\b",
        re.I,
    ),
    re.compile(r"\bwhen the ear movement changes\b", re.I),
    re.compile(r"\bthis ear position changes what [a-z]+s? do next\b", re.I),
    re.compile(
        r"\b(?:before the payoff|one visible signal|payoff appears before the final move|"
        r"final move|hidden cue|replay the first second)\b",
        re.I,
    ),
)
OPERATOR_META_PATTERNS = (
    re.compile(r"\bprevious [a-z]+ short worked because\b", re.I),
    re.compile(r"\bthis sequel keeps\b", re.I),
    re.compile(r"\bsame proven pattern\b", re.I),
    re.compile(r"\bwinning shape\b", re.I),
    re.compile(r"\boriginal topic pulled attention\b", re.I),
    re.compile(r"\bthis remake cuts\b", re.I),
    re.compile(r"\bproven wild brief topic\b", re.I),
)
NATURE_CATEGORIES = {
    "earth_from_space",
    "ecosystems",
    "forests",
    "fungi",
    "geology",
    "ocean",
    "oceans",
    "plants",
    "rare_phenomena",
    "rivers",
    "tree",
    "trees",
    "volcanoes",
    "weather",
}
NATURE_SUBJECT_LABELS = {
    "atmosphere": "atmosphere",
    "biodiversity": "biodiversity",
    "conservation": "recovery",
    "coral": "coral",
    "earth": "earth",
    "ecosystem": "ecosystem",
    "ecosystems": "ecosystem",
    "forest": "forest",
    "forests": "forest",
    "fungi": "fungal",
    "geology": "geology",
    "glacier": "glacier",
    "lava": "lava",
    "mountain": "mountain",
    "mountains": "mountain",
    "mushroom": "mushroom",
    "mushrooms": "mushroom",
    "mycelium": "mycelium",
    "ocean": "ocean",
    "plant": "plant",
    "plants": "plant",
    "reef": "reef",
    "river": "river",
    "rivers": "river",
    "rock": "rock",
    "rocks": "rock",
    "storm": "storm",
    "storms": "storm",
    "tree": "tree",
    "trees": "tree",
    "volcano": "volcano",
    "volcanoes": "volcano",
    "weather": "weather",
}


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]+", text or "")


def _token_count(text: str) -> int:
    return len([token for token in re.split(r"\s+", str(text or "").strip()) if token])


def _contains_any(text: str, words: set[str]) -> bool:
    lower = (text or "").lower()
    return any(re.search(r"\b" + re.escape(word) + r"\b", lower) for word in words)


def _specific_visible_cue_count(text: str) -> int:
    lower = (text or "").lower()
    specific_cues = VISIBLE_CUE_WORDS - GENERIC_CUE_WORDS
    return sum(1 for word in specific_cues if re.search(r"\b" + re.escape(word) + r"\b", lower))


def _packaging_language_risks(title: str, hook: str, script: str, thumb: str) -> list[str]:
    title_text = str(title or "").strip()
    all_text = " ".join(str(part or "").strip() for part in (title, hook, script, thumb))
    risks: list[str] = []

    if any(pattern.search(title_text) for pattern in BROKEN_PACKAGING_PATTERNS):
        risks.append("malformed_packaging_language")

    lower_title = title_text.lower()
    if re.search(r"\b(?:watch the cue|this cue|the cue)\b", lower_title) and _specific_visible_cue_count(all_text) == 0:
        risks.append("generic_visual_cue_language")
    if any(pattern.search(all_text) for pattern in GENERIC_PACKAGING_PATTERNS):
        risks.append("generic_visual_cue_language")
    if any(pattern.search(all_text) for pattern in OPERATOR_META_PATTERNS):
        risks.append("operator_meta_language")

    title_words = _words(title_text)
    if title_words and title_words[0][0].islower() and title_words[0].lower() not in {"a", "an", "the"}:
        risks.append("title_not_editorial_case")

    return risks


def _has_clear_payoff(script: str) -> bool:
    lower = str(script or "").lower()
    payoff_markers = (
        "because",
        "that's why",
        "that is why",
        "which means",
        "that lets",
        "that helps",
        "detail helps",
        "so the payoff",
        "so the final",
        "so the replay",
    )
    return any(marker in lower for marker in payoff_markers)


def _first_sentence(text: str) -> str:
    return re.split(r"[.!?]\s+", str(text or "").strip(), maxsplit=1)[0]


def _subject_from_text(text: str, category: str = "") -> str:
    subjects = (
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
        "bat",
        "bats",
        "eagle",
        "eagles",
        "fish",
        "fox",
        "foxes",
        "gecko",
        "geckos",
        "gorilla",
        "gorillas",
        "hedgehog",
        "hedgehogs",
        "iguana",
        "iguanas",
        "leopard",
        "leopards",
        "lemur",
        "lemurs",
        "lizard",
        "lizards",
        "macaque",
        "macaques",
        "pig",
        "pigs",
        "seal",
        "seals",
        "turtle",
        "turtles",
        "walrus",
        "walruses",
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
        "parrot",
        "parrots",
        "macaw",
        "macaws",
        "octopus",
        "octopuses",
        "donkey",
        "donkeys",
        "sheep",
        "snake",
        "snakes",
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
        "chameleon",
        "chameleons",
        "orangutan",
        "orangutans",
        "monkey",
        "monkeys",
        "plant",
        "plants",
        "tree",
        "trees",
        "forest",
        "forests",
        "fungi",
        "mushroom",
        "mushrooms",
        "mycelium",
        "ocean",
        "coral",
        "reef",
        "river",
        "rivers",
        "mountain",
        "mountains",
        "glacier",
        "volcano",
        "volcanoes",
        "lava",
        "storm",
        "storms",
        "lightning",
        "aurora",
        "eclipse",
        "rock",
        "rocks",
        "mineral",
        "minerals",
        "ecosystem",
        "ecosystems",
        "earth",
        "atmosphere",
        "conservation",
        "biodiversity",
        "fossil",
    )
    for token in _words(text.lower()):
        if token in subjects:
            return token
    return category or "nature"


def _viewer_promise(subject: str, story_format: str, category: str) -> str:
    lower_subject = str(subject or "nature").strip().lower()
    lower_category = str(category or "").strip().lower()
    format_label = str(story_format or "nature signal").replace("_", " ")
    category_text = lower_category.replace("_", " ")
    category_forms = {lower_category, category_text, category_text.rstrip("s"), lower_category.rstrip("s"), "nature"}
    is_nature = lower_subject in NATURE_SUBJECT_LABELS or (
        lower_category in NATURE_CATEGORIES and lower_subject in category_forms
    )
    if is_nature:
        detail = NATURE_SUBJECT_LABELS.get(lower_subject, lower_category.replace("_", " ") or "nature")
        if format_label in {
            "animal intelligence",
            "animal memory",
            "body superpower",
            "cute behavior",
            "survival trick",
        }:
            return f"See the {detail} detail that changes the whole scene."
        return f"See why this {detail} {format_label} matters."
    if format_label == "cute behavior":
        return f"See why this visible behavior matters for {subject}."
    return f"See why {subject} {format_label} matters."


def creator_premortem(story: dict) -> dict:
    title = str(story.get("seo_title") or story.get("title") or "")
    hook = str(story.get("hook") or "")
    script = str(story.get("script") or "")
    thumb = str(story.get("thumbnail_text") or "")
    category = str(story.get("category") or "")
    text = f"{title} {hook} {script} {thumb}"
    subject = _subject_from_text(text, category)
    story_format = str(story.get("story_format") or classify_format(text))
    hook_audit = audit_hook(hook)
    title_audit = audit_title(title)

    score = 44
    strengths: list[str] = []
    risks: list[str] = []
    commands: list[str] = []

    first = _first_sentence(script or hook)
    if subject and subject in first.lower():
        score += 8
        strengths.append("subject_visible_in_first_sentence")
    else:
        score -= 8
        risks.append("subject_not_immediately_clear")
        commands.append("Open with the visible subject before the behavior.")

    if _contains_any(text, ACTION_WORDS):
        score += 10
        strengths.append("action_driven_promise")
    else:
        score -= 10
        risks.append("no_action_promise")
        commands.append("Add a visible action verb: fake, protect, escape, remember, call, or use.")

    if _contains_any(text, VISIBLE_CUE_WORDS):
        score += 8
        strengths.append("visible_cue_for_viewer")
    else:
        score -= 6
        risks.append("missing_visual_cue")
        commands.append("Name the visual cue the viewer should watch in the first second.")

    if _has_clear_payoff(script):
        score += 9
        strengths.append("clear_payoff")
    else:
        score -= 9
        risks.append("payoff_not_explicit")
        commands.append("Give the viewer a because/that-is-why payoff.")

    script_words = len(script.split())
    if 42 <= script_words <= 95:
        score += 8
        strengths.append("shorts_length_fit")
    else:
        score -= 8
        risks.append("script_length_risk")

    if 2 <= _token_count(thumb) <= 5:
        score += 5
        strengths.append("thumbnail_text_scannable")
    else:
        score -= 5
        risks.append("thumbnail_text_not_scannable")

    if hook_audit.score >= 74:
        score += 6
    else:
        score -= 6
        risks.append("hook_shape_weak")
    if title_audit.score >= 74:
        score += 5
    else:
        score -= 5
        risks.append("title_shape_weak")

    weak_hits = [word for word in WEAK_WORDS if re.search(r"\b" + re.escape(word) + r"\b", text.lower())]
    if weak_hits:
        score -= min(10, len(weak_hits) * 3)
        risks.append("generic_creator_language")
        commands.append("Replace generic curiosity words with a specific behavior or body cue.")

    language_risks = _packaging_language_risks(title, hook, script, thumb)
    if language_risks:
        score -= min(22, 9 + (len(language_risks) - 1) * 5)
        risks.extend(language_risks)
        commands.append("Rewrite the title like a human editor: subject, visible action, and one clean payoff.")
    if "operator_meta_language" in language_risks:
        commands.append("Remove internal channel strategy language from the viewer script.")

    replay_reason = "watch_the_cue_again" if _contains_any(text, VISIBLE_CUE_WORDS) else "weak"
    viewer_promise = _viewer_promise(subject, story_format, category)
    satisfaction_bet = (
        "The viewer gets one visible nature cue and one reason, fast."
        if str(category or "").strip().lower() in NATURE_CATEGORIES
        and str(subject or "").strip().lower() in NATURE_SUBJECT_LABELS
        else "The viewer gets one visible behavior and one reason, fast."
    )
    score = max(0, min(100, score))
    state = "publish_minded" if score >= 78 else ("rewrite_before_publish" if score >= 60 else "do_not_publish")
    return {
        "score": score,
        "state": state,
        "animal": subject,
        "subject": subject,
        "story_format": story_format,
        "viewer_promise": viewer_promise,
        "satisfaction_bet": satisfaction_bet,
        "replay_reason": replay_reason,
        "retention_path": [
            "0-1s: visible subject and outcome",
            "1-4s: visible cue",
            "4-18s: mechanism",
            "last 2s: payoff and follow signal",
        ],
        "risks": list(dict.fromkeys(risks)),
        "strengths": list(dict.fromkeys(strengths)),
        "commands": list(dict.fromkeys(commands)),
    }


def publish_brain(meta: dict) -> dict:
    brain = creator_premortem(meta)
    score = brain["score"]
    if meta.get("has_captions"):
        score += 5
    else:
        brain["risks"].append("silent_viewer_loss")
    if meta.get("has_broll"):
        score += 5
    else:
        brain["risks"].append("motion_signal_missing")
    visual = meta.get("visual_qa") or {}
    if visual.get("checked") and not visual.get("approved"):
        score -= 25
        brain["risks"].append("first_frame_not_competitive")
    publish_score = meta.get("publish_score") or {}
    if float(publish_score.get("score", 0) or 0) >= 80:
        score += 6
    score = max(0, min(100, round(score, 1)))
    hard_fail = (
        visual.get("checked")
        and not visual.get("approved")
        or (not meta.get("has_captions") and not meta.get("has_broll"))
    )
    state = (
        "ship"
        if score >= 78 and brain["state"] != "do_not_publish"
        else ("hold" if hard_fail and score < 62 else "rewrite")
    )
    return {
        **brain,
        "score": score,
        "state": state,
        "post_publish_plan": {
            "1h": "Check views per hour and early swipe/retention proxy.",
            "6h": "If views move but retention lags, generate hook rewrite.",
            "24h": "Classify as scale, rewrite_hook, pause_topic, or watch.",
        },
    }


def channel_brain_summary(items: list[dict]) -> dict:
    states = Counter(str((item.get("youtube_brain") or {}).get("state") or "unknown") for item in items)
    risks = Counter(risk for item in items for risk in ((item.get("youtube_brain") or {}).get("risks") or []))
    avg = 0.0
    scores = [float((item.get("youtube_brain") or {}).get("score", 0) or 0) for item in items]
    if scores:
        avg = round(sum(scores) / len(scores), 2)
    return {
        "average_score": avg,
        "states": dict(states),
        "top_risks": dict(risks.most_common(8)),
    }
