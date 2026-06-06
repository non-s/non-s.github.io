"""Local automation health audit for Wild Brief."""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from utils.seo_optimizer import _ANIMAL_WORDS, optimise_title, seo_score


def _safe_json(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _script_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _frontloaded(title: str) -> bool:
    words = re.findall(r"[a-z]+", (title or "").lower())
    return bool(words and words[0] in _ANIMAL_WORDS)


def build_health(root: Path | str = ".") -> dict:
    root = Path(root)
    queue = _safe_json(root / "_data" / "stories_queue.json")
    latest = _safe_json(root / "_data" / "analytics" / "latest.json")
    comments = _safe_json(root / "_data" / "analytics" / "comments.json")
    stories = [
        item for item in (queue.get("stories") or [])
        if isinstance(item, dict) and not item.get("consumed")
    ]
    categories = Counter(str(item.get("category") or "unknown") for item in stories)
    scripts = [_script_key(str(item.get("script") or "")) for item in stories if item.get("script")]
    duplicate_scripts = len(scripts) - len(set(scripts))

    seo_scores: list[int] = []
    frontloaded = 0
    for item in stories:
        title = str(item.get("seo_title") or item.get("title") or "")
        optimised = optimise_title(
            title,
            hook=str(item.get("hook") or ""),
            script=str(item.get("script") or ""),
            tags=[str(t) for t in (item.get("yt_tags") or [])],
            category=str(item.get("category") or ""),
        )
        seo_scores.append(int(seo_score(optimised)["score"]))
        if _frontloaded(optimised):
            frontloaded += 1

    pending = len(stories)
    avg_seo = round(sum(seo_scores) / len(seo_scores), 2) if seo_scores else 0.0
    frontloaded_pct = round(frontloaded * 100 / pending, 2) if pending else 0.0
    issues: list[str] = []
    if pending < 20:
        issues.append("queue_inventory_low")
    if duplicate_scripts:
        issues.append("duplicate_scripts_in_queue")
    if avg_seo < 90:
        issues.append("seo_average_below_target")
    if frontloaded_pct < 95:
        issues.append("animal_frontload_below_target")
    if latest and latest.get("metric_scope") != "youtube_analytics_and_public_statistics":
        issues.append("youtube_analytics_scope_incomplete")
    if latest and float(latest.get("avg_view_pct", 0) or 0) < 55:
        issues.append("average_retention_needs_attention")

    score = 100
    score -= min(20, duplicate_scripts * 4)
    score -= 15 if pending < 20 else 0
    score -= max(0, int(90 - avg_seo))
    score -= max(0, int(95 - frontloaded_pct))
    score -= 10 if "youtube_analytics_scope_incomplete" in issues else 0
    score -= 8 if "average_retention_needs_attention" in issues else 0
    score = max(0, min(100, score))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "score": score,
        "state": "excellent" if score >= 90 else ("watch" if score >= 75 else "needs_work"),
        "issues": issues,
        "queue": {
            "pending": pending,
            "categories": dict(sorted(categories.items())),
            "duplicate_scripts": duplicate_scripts,
            "missing_scripts": sum(1 for item in stories if not item.get("script")),
            "missing_source": sum(1 for item in stories if not (item.get("source_url") or item.get("url"))),
        },
        "seo": {
            "average_score": avg_seo,
            "animal_frontloaded_pct": frontloaded_pct,
        },
        "analytics": {
            "pulled_at": latest.get("pulled_at", ""),
            "metric_scope": latest.get("metric_scope", ""),
            "total_views": latest.get("total_views", 0),
            "avg_view_pct": latest.get("avg_view_pct", latest.get("avg_view_percentage", 0)),
            "shorts_tracked": latest.get("shorts_tracked", 0),
        },
        "comments": {
            "comments_sampled": comments.get("comments_sampled", 0),
            "question_count": comments.get("question_count", 0),
        },
    }
