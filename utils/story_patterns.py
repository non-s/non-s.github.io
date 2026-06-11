"""Editorial story pattern classification for Wild Brief."""

from __future__ import annotations

import re

SERIES_CLUSTERS: dict[str, tuple[str, ...]] = {
    "Animal Minds": ("learn", "memory", "signal", "recognize", "solve", "social", "plan"),
    "Survival Cheats": ("survive", "escape", "hunt", "venom", "camouflage", "defense", "predator"),
    "Baby Nature": ("baby", "calf", "cub", "chick", "kit", "pup", "nest", "born"),
    "Impossible Biology": ("heart", "regrow", "glow", "transparent", "electric", "breathe", "biology"),
    "Hidden Behaviors": ("hidden", "secret", "night", "underground", "silent", "tiny", "rare"),
}


def _text(story: dict) -> str:
    return " ".join(str(story.get(key) or "") for key in ("title", "hook", "script", "description", "category"))


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z][a-z0-9'-]*", text.lower()))


def classify_story_pattern(story: dict | None = None) -> dict:
    """Classify a story into one of the channel's editorial clusters."""
    story = story or {}
    text = _text(story)
    tokens = _tokens(text)
    ranked = []
    for cluster, keywords in SERIES_CLUSTERS.items():
        hits = sorted(set(keywords) & tokens)
        ranked.append((len(hits), cluster, hits))
    ranked.sort(reverse=True)
    hit_count, cluster, matched = ranked[0]
    if hit_count == 0:
        cluster = str(story.get("series") or "Hidden Behaviors")
        matched = []
    payoff = "mechanism_reveal"
    if {"escape", "survive", "predator"} & tokens:
        payoff = "survival_payoff"
    elif {"baby", "born", "nest"} & tokens:
        payoff = "care_payoff"
    sentiment = "wonder"
    if {"venom", "hunt", "kill", "danger"} & tokens:
        sentiment = "tension"
    elif {"baby", "cute", "gentle"} & tokens:
        sentiment = "warmth"
    return {
        "cluster": cluster,
        "matched_terms": matched,
        "payoff": payoff,
        "sentiment": sentiment,
        "confidence": round(min(1.0, 0.32 + hit_count * 0.22), 3),
    }


def apply_story_pattern(story: dict) -> dict:
    out = dict(story or {})
    out["story_pattern"] = classify_story_pattern(out)
    if not out.get("series"):
        out["series"] = out["story_pattern"]["cluster"]
    return out
