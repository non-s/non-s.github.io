"""Opening-retention heuristics for the first swipe window."""

from __future__ import annotations

import re
from typing import Any

ACTION_WORDS = {
    "aim",
    "aims",
    "bend",
    "bends",
    "build",
    "builds",
    "call",
    "calls",
    "change",
    "changes",
    "cool",
    "cools",
    "copy",
    "copies",
    "dance",
    "dances",
    "escape",
    "escapes",
    "fake",
    "fakes",
    "feel",
    "feels",
    "filter",
    "filters",
    "flow",
    "flows",
    "follow",
    "follows",
    "glow",
    "glows",
    "grow",
    "grows",
    "hide",
    "hides",
    "hunt",
    "hunts",
    "judge",
    "judges",
    "keep",
    "keeps",
    "lock",
    "locks",
    "make",
    "makes",
    "move",
    "moves",
    "protect",
    "protects",
    "read",
    "reads",
    "recognize",
    "recognizes",
    "rely",
    "relies",
    "release",
    "releases",
    "remember",
    "remembers",
    "reveal",
    "reveals",
    "sample",
    "samples",
    "sense",
    "senses",
    "show",
    "shows",
    "slow",
    "slows",
    "smell",
    "smells",
    "sniff",
    "sniffs",
    "sort",
    "sorts",
    "spread",
    "spreads",
    "stabilize",
    "stabilizes",
    "steer",
    "steers",
    "store",
    "stores",
    "taste",
    "tastes",
    "trace",
    "traces",
    "turn",
    "turns",
    "use",
    "uses",
    "warn",
    "warns",
}

CUE_WORDS = {
    "air",
    "angle",
    "beak",
    "boundary",
    "bubbles",
    "canopy",
    "cloud",
    "clouds",
    "color",
    "cue",
    "ear",
    "ears",
    "edge",
    "eye",
    "eyes",
    "face",
    "feather",
    "feathers",
    "field",
    "filings",
    "flash",
    "gill",
    "gills",
    "heat",
    "injured",
    "injury",
    "layers",
    "leaf",
    "leaves",
    "light",
    "map",
    "movement",
    "nose",
    "orbit",
    "paw",
    "paws",
    "pattern",
    "roots",
    "shape",
    "scent",
    "scale",
    "scales",
    "sound",
    "spores",
    "stripe",
    "stripes",
    "surface",
    "tail",
    "taste",
    "thread",
    "threads",
    "tongue",
    "trail",
    "trails",
    "wing",
    "wings",
}

SUBJECT_WORDS = {
    "ant",
    "ants",
    "atmosphere",
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
    "coral",
    "cow",
    "cows",
    "clouds",
    "deer",
    "dog",
    "dogs",
    "dolphin",
    "dolphins",
    "dragonfly",
    "dragonflies",
    "duckling",
    "ducklings",
    "duck",
    "ducks",
    "earth",
    "elephants",
    "fields",
    "forest",
    "forests",
    "fossils",
    "fox",
    "foxes",
    "fungi",
    "glaciers",
    "goat",
    "goats",
    "horse",
    "horses",
    "lightning",
    "lion",
    "lions",
    "macaw",
    "macaws",
    "magnets",
    "mantis",
    "mantises",
    "monkey",
    "monkeys",
    "moon",
    "mountains",
    "mushrooms",
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
    "plants",
    "rivers",
    "rocks",
    "seal",
    "seals",
    "shark",
    "sharks",
    "sheep",
    "snake",
    "snakes",
    "storms",
    "trees",
    "turtles",
    "volcanoes",
    "whales",
    "wolves",
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "amazing",
    "are",
    "as",
    "at",
    "be",
    "because",
    "before",
    "by",
    "can",
    "do",
    "does",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "one",
    "or",
    "payoff",
    "secret",
    "signal",
    "signals",
    "that",
    "the",
    "their",
    "this",
    "today",
    "to",
    "visible",
    "watch",
    "when",
    "where",
    "why",
    "with",
}

GENERIC_OPENING_PATTERNS = (
    r"\bone visible signal\b",
    r"\bbefore the payoff\b",
    r"\bhiding in plain sight\b",
    r"\byou won't believe\b",
    r"\bamazing secret\b",
    r"\bthis animal is amazing\b",
    r"\bshow why the [a-z ]+ matters\b",
    r"\bread the moment from one\b",
    r"\bdetect changes with (?:their|its)\b",
)

REASON_TERMS = {"because", "so", "that", "when", "which", "why"}


def _words(text: object) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", str(text or "").lower())


def _stem(word: str) -> str:
    if len(word) <= 4:
        return word
    if word.endswith("ies"):
        word = f"{word[:-3]}y"
    elif word.endswith("ied"):
        word = f"{word[:-3]}y"
    elif word.endswith("ing") and len(word) > 6:
        word = word[:-3]
    elif word.endswith("ed") and len(word) > 5:
        word = word[:-2]
    elif word.endswith(("ches", "shes")) and len(word) > 6:
        word = word[:-2]
    elif word.endswith("es") and len(word) > 5 and word[-3] in {"s", "x", "z"}:
        word = word[:-2]
    elif word.endswith("s") and len(word) > 4:
        word = word[:-1]
    if word.endswith("y") and len(word) > 4:
        word = word[:-1]
    return word


def _meaningful(text: object) -> set[str]:
    return {_stem(word) for word in _words(text) if len(word) >= 3 and word not in STOPWORDS}


def _first_words(text: object, count: int) -> str:
    return " ".join(_words(text)[:count])


def _as_text(story: dict[str, Any], *keys: str) -> str:
    return " ".join(str(story.get(key) or "") for key in keys).strip()


def _thumbnail_text(story: dict[str, Any]) -> str:
    return str(story.get("thumbnail_text") or story.get("cover_text") or story.get("first_frame_text") or "")


def _first_2s(story: dict[str, Any]) -> str:
    explicit = str(story.get("first_2s_narration") or "").strip()
    if explicit:
        return explicit
    script = str(story.get("script") or "")
    return " ".join(_words(script)[:12])


def _subject(story: dict[str, Any], text: str) -> str:
    explicit = str(story.get("subject") or "").strip().lower()
    if explicit:
        return explicit
    category = str(story.get("category") or "").replace("_", " ").strip().lower()
    for word in _words(text):
        if word in SUBJECT_WORDS:
            return word
    for word in _words(category):
        if word in SUBJECT_WORDS:
            return word
    if category:
        return category.split()[0]
    return ""


def _cue_terms(story: dict[str, Any]) -> set[str]:
    explicit = str(story.get("cue") or "").strip()
    terms = _meaningful(explicit)
    thumb_words = _words(_thumbnail_text(story))
    terms.update(
        _stem(word)
        for word in thumb_words
        if word not in STOPWORDS
        and word not in SUBJECT_WORDS
        and (word in CUE_WORDS or _stem(word) in CUE_WORDS or len(word) >= 5)
    )
    first_text = _first_2s(story)
    terms.update(
        _stem(word)
        for word in _words(first_text)
        if word not in STOPWORDS and word not in SUBJECT_WORDS and (word in CUE_WORDS or _stem(word) in CUE_WORDS)
    )
    return terms


def _generic_hits(text: str) -> list[str]:
    return [pattern for pattern in GENERIC_OPENING_PATTERNS if re.search(pattern, text, re.I)]


def score_retention_opening(story: dict[str, Any] | None = None) -> dict[str, Any]:
    """Score whether the first frame, hook, and first words sell one clear promise."""
    story = story or {}
    title = _as_text(story, "seo_title", "title")
    hook = str(story.get("hook") or title)
    script = str(story.get("script") or hook)
    thumb = _thumbnail_text(story)
    has_frame_text = bool(thumb.strip())
    first_2s = _first_2s(story)
    text = " ".join(part for part in (title, hook, script, thumb, first_2s) if part)
    lower_text = text.lower()
    subject = _subject(story, text)
    cue_terms = _cue_terms(story)
    frame_terms = _meaningful(thumb)
    hook_terms = _meaningful(hook)
    first_terms = _meaningful(first_2s)
    early_terms = _meaningful(_first_words(f"{hook} {script}", 18))
    frame_bridge = sorted(frame_terms & (hook_terms | first_terms))
    cue_bridge = sorted(cue_terms & (hook_terms | first_terms | early_terms))

    score = 38.0
    strengths: list[str] = []
    risks: list[str] = []

    if subject and subject in _first_words(f"{hook} {script}", 12):
        score += 14
        strengths.append("subject_frontloaded")
    else:
        score -= 8
        risks.append("subject_not_frontloaded")

    if has_frame_text:
        if frame_bridge:
            score += 14
            strengths.append("frame_hook_bridge")
        else:
            score -= 10
            risks.append("frame_text_not_echoed_early")

        if cue_bridge:
            score += 12
            strengths.append("visible_cue_repeated_early")
        else:
            score -= 8
            risks.append("visible_cue_not_repeated_early")

    if "watch" in _words(f"{hook} {first_2s}"):
        score += 8
        strengths.append("watch_instruction_early")
    else:
        risks.append("missing_watch_instruction")

    if any(word in ACTION_WORDS for word in _words(f"{title} {hook} {first_2s}")):
        score += 10
        strengths.append("action_promise_early")
    else:
        score -= 8
        risks.append("missing_early_action")

    if any(term in _words(_first_words(script, 28)) for term in REASON_TERMS):
        score += 10
        strengths.append("reason_arrives_early")
    else:
        score -= 8
        risks.append("reason_arrives_late")

    thumb_count = len(_words(thumb))
    if has_frame_text:
        if 2 <= thumb_count <= 4:
            score += 8
            strengths.append("frame_text_scannable")
        else:
            score -= 6
            risks.append("frame_text_not_scannable")

    generic_hits = _generic_hits(lower_text)
    if generic_hits:
        if generic_hits == [r"\bbefore the payoff\b"] and frame_bridge and cue_bridge:
            score -= 6
            risks.append("formulaic_opening_language")
        else:
            score -= 22
            risks.append("generic_opening_language")

    if "?" in title or "why" in _words(hook) or "before" in _words(hook):
        score += 4
        strengths.append("curiosity_shape")

    score = round(max(0.0, min(100.0, score)), 1)
    state = "retention_ready" if score >= 82 else ("needs_tightening" if score >= 70 else "rewrite_opening")
    return {
        "score": score,
        "state": state,
        "approved": score >= 76,
        "subject": subject,
        "cue_terms": sorted(cue_terms),
        "frame_hook_bridge": frame_bridge,
        "cue_bridge": cue_bridge,
        "strengths": list(dict.fromkeys(strengths)),
        "risks": list(dict.fromkeys(risks)),
    }
