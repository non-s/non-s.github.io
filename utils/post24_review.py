"""Classify Shorts after the first 24 hours."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from utils.editorial_guard import editorial_issues
from utils.local_rewriter import rescue_story

ANALYTICS_FILE = Path("_data/analytics/latest.json")
POST24_FILE = Path("_data/post24_review.json")
RETENTION_SCALE_FLOOR = 62.0
RETENTION_REWRITE_FLOOR = 62.0


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _title_issues(title: str) -> list[str]:
    title = str(title or "").strip()
    if not title:
        return []
    return editorial_issues({"title": title, "seo_title": title}, include_script=False)


def _specific_title_repairs(title: str) -> list[str]:
    lower = str(title or "").lower()
    if "another signal hiding in plain sight" in lower and "chicken" in lower:
        return ["Chickens react differently when their heads move"]
    if "use their body to follow" in lower and "snake" in lower:
        return ["Snakes follow the trail through body movement"]
    if "never roar" in lower and "prey" in lower:
        return ["Tigers stay silent before they strike"]
    if "ear tufts" in lower and "aren't ears" in lower:
        return ["Black birds show ear tufts that are not ears"]
    return []


def _repair_suggestions(item: dict, title_issues: list[str]) -> list[str]:
    if not title_issues:
        return []
    title = str(item.get("title") or "")
    specific = [
        candidate
        for candidate in _specific_title_repairs(title)
        if not editorial_issues({"title": candidate, "seo_title": candidate}, include_script=False)
    ]
    if specific:
        return specific[:3]
    story = {
        "title": title,
        "seo_title": title,
        "hook": title,
        "script": title,
        "thumbnail_text": str(item.get("thumbnail_text") or ""),
        "category": str(item.get("category") or ""),
        "source_url": str(item.get("url") or item.get("source_url") or ""),
    }
    rescued, applied = rescue_story(story, title_issues)
    if not applied:
        return []
    candidate = str(rescued.get("seo_title") or rescued.get("title") or "").strip()
    if not candidate or candidate.lower() == title.strip().lower():
        return []
    if editorial_issues({"title": candidate, "seo_title": candidate}, include_script=False):
        return []
    return [candidate[:82]]


def classify_video(item: dict) -> str:
    if _title_issues(str(item.get("title") or "")):
        return "repair_package"
    views = int(item.get("views") or 0)
    retention = float(item.get("view_pct") or item.get("average_view_percentage") or 0)
    growth = float(item.get("growth_score") or 0)
    if retention >= RETENTION_SCALE_FLOOR and growth >= 180:
        return "scale"
    if views >= 900 and retention < RETENTION_REWRITE_FLOOR:
        return "rewrite_hook"
    if views < 500 and retention < 50:
        return "pause_topic"
    return "watch"


def build_review(analytics: dict | None = None) -> dict:
    analytics = analytics or _safe_json(ANALYTICS_FILE)
    rows = []
    for item in analytics.get("top_performers") or []:
        title = item.get("title", "")
        title_issues = _title_issues(str(title or ""))
        row = {
            "video_id": item.get("video_id", ""),
            "title": title,
            "category": item.get("category", ""),
            "views": item.get("views", 0),
            "retention": item.get("view_pct") or item.get("average_view_percentage") or 0,
            "growth_score": item.get("growth_score", 0),
            "decision": classify_video(item),
        }
        if title_issues:
            row["title_issues"] = title_issues
            suggestions = _repair_suggestions(item, title_issues)
            if suggestions:
                row["suggested_titles"] = suggestions
        rows.append(row)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": rows,
        "counts": {
            state: sum(1 for row in rows if row["decision"] == state)
            for state in ("repair_package", "scale", "rewrite_hook", "pause_topic", "watch")
        },
        "rules": {
            "repair_package": "title or packaging fails editorial guard",
            "scale": f"retention >= {RETENTION_SCALE_FLOOR:g} and growth_score >= 180",
            "rewrite_hook": f"views >= 900 and retention < {RETENTION_REWRITE_FLOOR:g}",
            "pause_topic": "views < 500 and retention < 50",
        },
    }


def write_review(path: Path = POST24_FILE) -> dict:
    review = build_review()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")
    return review
