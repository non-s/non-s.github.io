"""Chief content office scoring for Wild Brief.

This layer is deliberately local and free: it combines signals the
pipeline already owns into a single publishing priority. It is not a
replacement for the editorial, SEO, ops, or pre-publish gates. It is the
agency-level view that decides which approved story deserves the next
slot.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone

from utils.story_intelligence import classify_format


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", (text or "").lower())


def _freshness_score(story: dict) -> float:
    raw = str(story.get("fetched_at") or story.get("date") or "")
    if not raw:
        return 68.0
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hours = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600)
    except Exception:
        return 68.0
    if hours <= 18:
        return 100.0
    if hours <= 72:
        return 88.0
    if hours <= 168:
        return 72.0
    if hours <= 336:
        return 54.0
    return 38.0


def _trend_score(story: dict) -> float:
    ctx = story.get("trend_context") or {}
    raw = _num(ctx.get("trend_score"), 0)
    if raw <= 0:
        return 48.0
    mentions = _num(ctx.get("mentions"), 0)
    return max(0.0, min(100.0, raw + min(10.0, mentions * 1.5)))


def _learning_score(story: dict, strategy: dict | None = None) -> float:
    strategy = strategy or {}
    category = str(story.get("category") or "").lower()
    story_format = str(story.get("story_format") or classify_format(
        f"{story.get('title', '')} {story.get('hook', '')} {story.get('script', '')}"
    ))
    category_weights = strategy.get("category_weights") or {}
    format_weights = strategy.get("format_weights") or {}
    cat_weight = _num(category_weights.get(category), 1.0)
    fmt_weight = _num(format_weights.get(story_format), 1.0)
    exploit_keywords = [
        str(item).lower() for item in (strategy.get("exploit_keywords") or [])
        if str(item).strip()
    ]
    text = (
        f"{story.get('title', '')} {story.get('hook', '')} "
        f"{story.get('script', '')}"
    ).lower()
    keyword_bonus = 8 if exploit_keywords and any(word in text for word in exploit_keywords) else 0
    base = 50 + (cat_weight - 1.0) * 22 + (fmt_weight - 1.0) * 18 + keyword_bonus
    return max(0.0, min(100.0, base))


def _distinctiveness_score(story: dict, cohort: list[dict] | None = None) -> float:
    title_words = set(_words(str(story.get("title") or story.get("seo_title") or "")))
    hook_words = set(_words(str(story.get("hook") or "")))
    subject_words = title_words | hook_words
    if not subject_words:
        return 42.0
    category = str(story.get("category") or "")
    same_category = [
        item for item in (cohort or [])
        if item is not story and str(item.get("category") or "") == category
    ]
    if not same_category:
        return 88.0
    overlaps = []
    for other in same_category[:20]:
        other_words = set(_words(str(other.get("title") or other.get("seo_title") or "")))
        if not other_words:
            continue
        overlaps.append(
            len(subject_words & other_words) / max(1, len(subject_words | other_words))
        )
    if not overlaps:
        return 84.0
    avg_overlap = sum(overlaps) / len(overlaps)
    return max(25.0, min(100.0, 100 - avg_overlap * 120))


def agency_score(story: dict, *,
                 strategy: dict | None = None,
                 cohort: list[dict] | None = None) -> dict:
    editorial = story.get("editorial") or {}
    humanity = editorial.get("humanity") or story.get("humanity") or {}
    hook_audit = story.get("hook_audit") or {}
    title_audit = story.get("title_audit") or {}

    quality = (
        _num(editorial.get("score"), 0) * 0.38
        + _num(humanity.get("score"), 0) * 0.28
        + _num(story.get("score"), 0) * 3.2
        + _num(hook_audit.get("score"), 74) * 0.10
        + _num(title_audit.get("score"), 74) * 0.10
    )
    quality = max(0.0, min(100.0, quality))
    trend = _trend_score(story)
    learning = _learning_score(story, strategy)
    freshness = _freshness_score(story)
    distinctiveness = _distinctiveness_score(story, cohort)

    risk_penalty = 0.0
    reasons = []
    if not editorial.get("approved", False):
        risk_penalty += 34
        reasons.append("editorial_not_approved")
    if _num(humanity.get("score"), 0) < 58:
        risk_penalty += 16
        reasons.append("low_humanity")
    if _num(story.get("safety_penalty"), 0) > 0:
        risk_penalty += min(16, _num(story.get("safety_penalty"), 0))
        reasons.append("safety_penalty")
    if (story.get("studio_state") or "") in {"blocked", "hold"}:
        risk_penalty += 12
        reasons.append("studio_hold")

    score = (
        quality * 0.42
        + learning * 0.22
        + trend * 0.16
        + freshness * 0.10
        + distinctiveness * 0.10
        - risk_penalty
    )
    score = int(max(0, min(100, round(score))))
    if score >= 82:
        decision = "publish_now"
    elif score >= 68:
        decision = "strong_candidate"
    elif score >= 52:
        decision = "needs_polish"
    else:
        decision = "hold"

    strengths = []
    if quality >= 78:
        strengths.append("strong_quality")
    if trend >= 72:
        strengths.append("timely_trend")
    if learning >= 68:
        strengths.append("matches_channel_learning")
    if distinctiveness >= 78:
        strengths.append("fresh_angle")
    if freshness >= 88:
        strengths.append("fresh_inventory")

    return {
        "score": score,
        "decision": decision,
        "quality": round(quality, 1),
        "trend": round(trend, 1),
        "learning": round(learning, 1),
        "freshness": round(freshness, 1),
        "distinctiveness": round(distinctiveness, 1),
        "risk_penalty": round(risk_penalty, 1),
        "strengths": strengths,
        "reasons": reasons,
    }


def rank_for_agency(candidates: list[dict],
                    strategy: dict | None = None) -> list[dict]:
    cohort = list(candidates)
    ranked = []
    for candidate in candidates:
        item = dict(candidate)
        item["agency"] = agency_score(item, strategy=strategy, cohort=cohort)
        ranked.append(item)
    return sorted(
        ranked,
        key=lambda item: (
            item["agency"]["decision"] == "publish_now",
            int(item["agency"]["score"]),
            float(item.get("growth_priority", 0) or 0),
            bool((item.get("editorial") or {}).get("approved")),
        ),
        reverse=True,
    )


def agency_snapshot(candidates: list[dict],
                    strategy: dict | None = None,
                    limit: int = 8) -> dict:
    ranked = rank_for_agency(candidates, strategy)
    decisions = Counter((item.get("agency") or {}).get("decision", "unknown") for item in ranked)
    avg = (
        round(
            sum(int((item.get("agency") or {}).get("score", 0)) for item in ranked)
            / len(ranked),
            1,
        )
        if ranked else 0
    )
    return {
        "average_score": avg,
        "decisions": dict(sorted(decisions.items())),
        "top": [
            {
                "title": item.get("seo_title") or item.get("title") or "",
                "category": item.get("category") or "",
                "score": (item.get("agency") or {}).get("score", 0),
                "decision": (item.get("agency") or {}).get("decision", ""),
                "strengths": list((item.get("agency") or {}).get("strengths") or [])[:4],
            }
            for item in ranked[:limit]
        ],
    }
