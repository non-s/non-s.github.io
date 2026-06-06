"""Safety and opportunity scoring for public animal trends."""
from __future__ import annotations

import re


HIGH_RISK = {
    "attack", "attacks", "death", "dead", "killed", "mauling", "rabies",
    "disease", "virus", "abuse", "cruelty", "tragedy", "injured",
}
OPPORTUNITY = {
    "rescue", "rare", "sighting", "study", "behavior", "viral", "migration",
    "baby", "learn", "memory", "intelligence", "conservation",
}


def _tokens(*values: str) -> set[str]:
    text = " ".join(values).lower()
    return set(re.findall(r"[a-z][a-z'-]+", text))


def score_topic(topic: dict) -> dict:
    titles = " ".join(str(t) for t in (topic.get("top_titles") or [])[:5])
    terms = " ".join(str(t) for t in (topic.get("terms") or []))
    tokens = _tokens(titles, terms, str(topic.get("query") or ""))
    risk_hits = sorted(tokens & HIGH_RISK)
    opportunity_hits = sorted(tokens & OPPORTUNITY)
    trend_score = float(topic.get("trend_score", 0) or 0)
    risk = min(100, len(risk_hits) * 22)
    opportunity = max(0, min(100, trend_score * 0.62 + len(opportunity_hits) * 8 - risk * 0.35))
    if risk >= 22:
        posture = "handle_with_care"
    elif opportunity >= 70:
        posture = "greenlight"
    elif opportunity >= 45:
        posture = "watch"
    else:
        posture = "low_signal"
    return {
        "risk_score": round(risk, 1),
        "opportunity_score": round(opportunity, 1),
        "posture": posture,
        "risk_terms": risk_hits,
        "opportunity_terms": opportunity_hits,
    }


def enrich_topics(topics: list[dict]) -> list[dict]:
    out = []
    for topic in topics:
        item = dict(topic)
        item["trend_safety"] = score_topic(item)
        out.append(item)
    return sorted(
        out,
        key=lambda item: (
            float((item.get("trend_safety") or {}).get("opportunity_score", 0) or 0),
            -float((item.get("trend_safety") or {}).get("risk_score", 0) or 0),
        ),
        reverse=True,
    )
