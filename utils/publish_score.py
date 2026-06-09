"""Unified publish scoring for Wild Brief Shorts."""
from __future__ import annotations

import re

from utils.story_intelligence import audit_hook, audit_title, classify_format


WINNING_CATEGORIES = {"farm", "birds", "wildlife"}
RECOVERY_CATEGORIES = {"cats", "dogs", "ocean"}
WINNING_FORMATS = {"animal_memory", "body_superpower", "animal_intelligence"}
ACTION_WORDS = {
    "fake", "remember", "recognize", "plan", "escape", "slide", "call",
    "hear", "hold", "roar", "use", "hide", "protect", "trick",
}


def _as_score(value, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def _score_dict(payload: dict, *path: str) -> dict:
    cur = payload
    for key in path:
        cur = cur.get(key) if isinstance(cur, dict) else {}
    return cur if isinstance(cur, dict) else {}


def phrase_risk(text: str) -> dict:
    lower = (text or "").lower()
    hits = []
    for phrase in (
        "another signal hiding in plain sight",
        "another secret hiding in plain sight",
        "one tiny movement",
        "hidden reason",
        "secret",
    ):
        count = len(re.findall(r"\b" + re.escape(phrase) + r"\b", lower))
        if count:
            hits.append({"phrase": phrase, "count": count})
    penalty = min(24, sum(item["count"] * (8 if item["phrase"] != "secret" else 3) for item in hits))
    return {"penalty": penalty, "hits": hits}


def score_story(story: dict, *, analytics_strategy: dict | None = None) -> dict:
    """Score an unrendered queue/story candidate from 0-100."""
    analytics_strategy = analytics_strategy or {}
    title = str(story.get("seo_title") or story.get("title") or "")
    hook = str(story.get("hook") or "")
    script = str(story.get("script") or "")
    category = str(story.get("category") or "").lower()
    text = f"{title} {hook} {script}"
    story_format = str(story.get("story_format") or classify_format(text))
    hook_audit = audit_hook(hook)
    title_audit = audit_title(title)
    risk = phrase_risk(text)

    score = 38
    score += hook_audit.score * 0.16
    score += title_audit.score * 0.14
    score += min(12, _as_score(story.get("score")) * 1.2)
    if category in WINNING_CATEGORIES:
        score += 9
    elif category in RECOVERY_CATEGORIES:
        score -= 7
    if story_format in WINNING_FORMATS:
        score += 10
    if any(word in text.lower() for word in ACTION_WORDS):
        score += 8
    words = script.split()
    if 42 <= len(words) <= 95:
        score += 8
    elif len(words) > 115:
        score -= 12
    score -= risk["penalty"]

    category_weights = analytics_strategy.get("category_weights") or {}
    format_weights = analytics_strategy.get("format_weights") or {}
    score *= max(0.75, min(1.25, _as_score(category_weights.get(category), 1.0)))
    score *= max(0.75, min(1.2, _as_score(format_weights.get(story_format), 1.0)))
    score = round(max(0, min(100, score)), 1)
    approved = score >= 72 and not risk["hits"][:1]
    return {
        "score": score,
        "approved": approved,
        "state": "publish_ready" if approved else ("rewrite" if score >= 55 else "reject"),
        "category": category,
        "story_format": story_format,
        "hook_score": hook_audit.score,
        "title_score": title_audit.score,
        "phrase_risk": risk,
    }


def score_metadata(meta: dict) -> dict:
    """Score a rendered Short package using metadata gathered after render."""
    base = score_story(meta)
    audit = _score_dict(meta, "pre_publish_audit")
    visual = _score_dict(meta, "visual_qa")
    visual_ctr = _score_dict(meta, "visual_ctr")
    monetization = _score_dict(meta, "monetization_audit")
    score = base["score"]
    score += _as_score(audit.get("score"), 70) * 0.12 - 8
    if meta.get("has_captions"):
        score += 4
    if meta.get("has_broll"):
        score += 5
    if visual.get("checked") and not visual.get("approved"):
        score -= 35
    if visual_ctr.get("checked"):
        ctr_score = _as_score(visual_ctr.get("score"), 50)
        if ctr_score >= 72:
            score += 4
        elif ctr_score < 52:
            score -= 8
    if monetization.get("approved") is False:
        score -= 20
    score = round(max(0, min(100, score)), 1)
    approved = score >= 65 and base.get("state") != "reject" and audit.get("approved", True)
    return {**base, "score": score, "approved": approved}
