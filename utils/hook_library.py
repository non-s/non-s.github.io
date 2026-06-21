"""Learned hook templates and lightweight hook scoring."""

from __future__ import annotations

import json
import re
from pathlib import Path

from utils.story_patterns import classify_story_pattern

HOOK_LIBRARY_FILE = Path("_data/hook_library.json")
BANNED_GENERIC_PHRASES = (
    "you won't believe",
    "what happens next",
    "this animal is amazing",
    "mind blowing",
    "secret hiding in plain sight",
)
DEFAULT_TEMPLATES: dict[str, list[str]] = {
    "Animal Minds": ["This {subject} solves the problem before anyone notices."],
    "Survival Cheats": ["This {subject} cheats death by changing one tiny move."],
    "Baby Nature": ["This baby {subject} survives by doing the quietest thing."],
    "Impossible Biology": ["This {subject} body part does something biology should not allow."],
    "Hidden Behaviors": ["This {subject} move is invisible until the payoff starts."],
    "Earth Engine": ["This {subject} force changes the scene before the payoff lands."],
    "Plant Signals": ["This {subject} signal starts quietly, then changes the whole system."],
    "Planet Systems": ["This {subject} system hides the clue until the pattern appears."],
}


def _words(text: object) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", str(text or ""))


def load_hook_library(path: Path = HOOK_LIBRARY_FILE) -> dict:
    if not path.exists():
        return {"templates": DEFAULT_TEMPLATES, "banned_phrases": list(BANNED_GENERIC_PHRASES)}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    templates = data.get("templates") if isinstance(data, dict) else {}
    banned = data.get("banned_phrases") if isinstance(data, dict) else []
    merged_templates = {**DEFAULT_TEMPLATES, **(templates or {})}
    return {
        "templates": merged_templates,
        "banned_phrases": banned or list(BANNED_GENERIC_PHRASES),
        "clusters": data.get("clusters", {}) if isinstance(data, dict) else {},
    }


def score_hook(hook: str, story: dict | None = None, library: dict | None = None) -> dict:
    library = library or load_hook_library()
    story = story or {}
    lower = str(hook or "").lower()
    words = _words(hook)
    reasons: list[str] = []
    score = 52.0
    if 5 <= len(words) <= 13:
        score += 15
        reasons.append("mobile_length")
    if story.get("category") and str(story.get("category")).lower() in lower:
        score += 8
        reasons.append("category_specific")
    if any(token in lower for token in ("before", "because", "survives", "changes", "why", "seconds")):
        score += 14
        reasons.append("payoff_language")
    banned_hits = [phrase for phrase in library.get("banned_phrases", []) if phrase in lower]
    if banned_hits:
        score -= 32
        reasons.append("banned_generic_hook")
    if len(set(w.lower() for w in words)) <= max(2, len(words) // 2):
        score -= 12
        reasons.append("repetitive_hook")
    return {"score": round(max(0, min(100, score)), 2), "reasons": reasons, "banned_hits": banned_hits}


def choose_hook_template(story: dict, library: dict | None = None) -> dict:
    library = library or load_hook_library()
    pattern = classify_story_pattern(story)
    templates = (library.get("templates") or {}).get(pattern["cluster"]) or DEFAULT_TEMPLATES.get(
        pattern["cluster"], DEFAULT_TEMPLATES["Hidden Behaviors"]
    )
    subject = str(story.get("subject") or story.get("category") or "animal").lower()
    text = str(templates[0]).format(subject=subject)
    return {"cluster": pattern["cluster"], "template": templates[0], "example": text}


def build_hook_library(stories: list[dict] | None = None) -> dict:
    clusters: dict[str, dict] = {}
    for story in stories or []:
        if not isinstance(story, dict):
            continue
        pattern = classify_story_pattern(story)
        cluster = pattern["cluster"]
        hook = str(story.get("hook") or "")
        if not hook:
            continue
        bucket = clusters.setdefault(cluster, {"hooks": [], "count": 0})
        bucket["count"] += 1
        if score_hook(hook, story)["score"] >= 72:
            bucket["hooks"].append(hook[:140])
    return {
        "templates": DEFAULT_TEMPLATES,
        "banned_phrases": list(BANNED_GENERIC_PHRASES),
        "clusters": clusters,
    }
