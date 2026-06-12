"""Free growth strategy helpers for Wild Brief production ranking.

The module only reads local analytics snapshots written by
scripts/analyze_channel.py. No new service, key, or paid dependency is
required: production simply leans toward categories and story shapes that
already proved they can earn views, retention, or subscribers.
"""

from __future__ import annotations

import json
from pathlib import Path

from utils.story_intelligence import classify_format

ANALYTICS_FILE = Path("_data/analytics/latest.json")
OPS_FILE = Path("_data/ops_guardian.json")


def load_strategy(path: Path | None = None) -> dict:
    """Return the latest growth strategy payload, or an empty strategy."""
    p = path or ANALYTICS_FILE
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    strategy = data.get("production_recommendations") or {}
    if not isinstance(strategy, dict):
        return {}
    return strategy


def category_weights(strategy: dict | None = None) -> dict[str, float]:
    """Map category -> production weight from the latest analytics."""
    strategy = strategy or load_strategy()
    raw = strategy.get("category_weights") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for key, value in raw.items():
        try:
            out[str(key)] = max(0.5, min(2.5, float(value)))
        except Exception:
            continue
    return out


def paused_categories(path: Path | None = None) -> dict[str, dict]:
    p = path or OPS_FILE
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, dict] = {}
    for item in data.get("paused_topics") or []:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "").strip().lower()
        if category:
            out[category] = item
    return out


def score_story(story: dict, strategy: dict | None = None) -> float:
    """Score one candidate for production priority.

    Editorial approval still dominates. The growth layer is a multiplier,
    not a license to publish weak stories.
    """
    strategy = strategy or load_strategy()
    weights = category_weights(strategy)
    category = str(story.get("category") or "wildlife")
    editorial = story.get("editorial") or {}
    editorial_score = float(editorial.get("score", 0) or 0)
    humanity = editorial.get("humanity") or story.get("humanity") or {}
    try:
        humanity_score = float(humanity.get("score", 0) or 0)
    except Exception:
        humanity_score = 0.0
    ai_score = float(story.get("score", 0) or 0)
    base = editorial_score + humanity_score * 0.55 + ai_score * 3
    story_format = str(
        story.get("story_format")
        or classify_format(f"{story.get('title', '')} {story.get('hook', '')} {story.get('script', '')}")
    )
    format_weights = strategy.get("format_weights") or {}
    try:
        format_weight = float(format_weights.get(story_format, 1.0))
    except Exception:
        format_weight = 1.0
    exploit_keywords = [str(item).lower() for item in (strategy.get("exploit_keywords") or []) if str(item).strip()]
    title_hook = f"{story.get('title', '')} {story.get('hook', '')}".lower()
    if exploit_keywords and any(word in title_hook for word in exploit_keywords):
        base *= 1.18
    if humanity_score >= 86:
        base *= 1.16
    elif humanity_score >= 72:
        base *= 1.08
    elif humanity_score < 58:
        base *= 0.62
    if editorial and not editorial.get("approved", False):
        base *= 0.35
    paused = paused_categories()
    if category.lower() in paused:
        base *= 0.42
    return round(base * weights.get(category, 1.0) * max(0.7, min(1.8, format_weight)), 3)


def rank_for_growth(candidates: list[dict], strategy: dict | None = None) -> list[dict]:
    """Attach growth metadata and sort strongest candidates first."""
    strategy = strategy or load_strategy()
    ranked: list[dict] = []
    for candidate in candidates:
        item = dict(candidate)
        item["growth_priority"] = score_story(item, strategy)
        ranked.append(item)
    return sorted(
        ranked,
        key=lambda item: (
            bool((item.get("editorial") or {}).get("approved")),
            float(item.get("growth_priority", 0) or 0),
            int(((item.get("editorial") or {}).get("humanity") or {}).get("score", 0) or 0),
            int((item.get("editorial") or {}).get("score", 0) or 0),
            int(item.get("score", 0) or 0),
        ),
        reverse=True,
    )
