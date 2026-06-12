"""Operational guardrails for the Wild Brief automation.

The guardian turns local analytics, queue health and published markers
into decisions the bot can act on without paid services: risk level,
paused topics, publish windows, visual-quality warnings and an executive
report for the dashboard.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from utils.audience_expansion import GLOBAL_PUBLISH_WINDOWS
from utils.editorial_guard import editorial_issues


def _safe_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_markers(root: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted((root / "_videos").glob("*.done")):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _recommendable_title(title: str) -> bool:
    title = str(title or "").strip()
    if not title:
        return False
    return not editorial_issues({"title": title, "seo_title": title}, include_script=False)


def _recommended_hours(root: Path, latest: dict) -> list[dict]:
    cohort = _safe_json(root / "_data" / "analytics" / "cohort_timing.json")
    hours = cohort.get("recommended_utc_hours") or []
    out: list[dict] = []
    for item in hours:
        if not isinstance(item, dict):
            continue
        try:
            out.append(
                {
                    "utc_hour": int(item.get("utc_hour")),
                    "country": str(item.get("country") or "global"),
                    "views": int(item.get("views", 0) or 0),
                    "reason": "audience_cohort",
                }
            )
        except Exception:
            continue
    if out:
        return out[:5]
    # Conservative global Shorts windows when country-level cohorts are not
    # available yet. These spread discovery across Asia/Oceania,
    # Europe/Africa and the Americas instead of overfitting one country.
    return [
        {
            "utc_hour": int(item["utc_hour"]),
            "country": "global",
            "views": int(latest.get("total_views", 0) or 0),
            "reason": "default_global_daypart",
            "label": str(item["label"]),
            "regions": list(item["regions"]),
        }
        for item in GLOBAL_PUBLISH_WINDOWS
    ]


def _paused_topics(latest: dict) -> list[dict]:
    category_retention = latest.get("category_avg_view_pct") or {}
    category_growth = latest.get("category_avg_growth_score") or {}
    avg_retention = float(latest.get("avg_view_pct", latest.get("avg_view_percentage", 0)) or 0)
    paused: list[dict] = []
    for category, value in category_retention.items():
        try:
            retention = float(value or 0)
        except Exception:
            continue
        growth = float((category_growth or {}).get(category, 0) or 0)
        if retention and retention < 45 and growth < 150:
            paused.append(
                {
                    "category": str(category),
                    "reason": "retention_below_45",
                    "retention": round(retention, 3),
                    "growth_score": round(growth, 3),
                }
            )
        elif avg_retention and retention < max(40, avg_retention - 15) and growth < 100:
            paused.append(
                {
                    "category": str(category),
                    "reason": "under_channel_average",
                    "retention": round(retention, 3),
                    "growth_score": round(growth, 3),
                }
            )
    return sorted(paused, key=lambda item: (item["retention"], item["growth_score"]))[:8]


def _visual_quality(markers: list[dict]) -> dict:
    checked = rejected = low_quality = 0
    local_checked = local_low_quality = 0
    reasons: Counter[str] = Counter()
    for marker in markers:
        qa = marker.get("visual_qa") or {}
        if isinstance(qa, dict) and qa.get("checked"):
            checked += 1
            if not qa.get("approved", True):
                rejected += 1
                reasons[str(qa.get("reason") or "rejected")] += 1
            try:
                score = int(qa.get("thumbnail_quality", 0) or 0)
            except Exception:
                score = 0
            if score and score < 6:
                low_quality += 1
        local = marker.get("local_visual_qa") or {}
        if isinstance(local, dict) and local.get("checked"):
            local_checked += 1
            try:
                local_score = int(local.get("score", 0) or 0)
            except Exception:
                local_score = 0
            if local_score and local_score < 6:
                local_low_quality += 1
                reasons[str(local.get("reason") or "local_low_quality")] += 1
    return {
        "checked": checked,
        "rejected": rejected,
        "low_quality": low_quality,
        "local_checked": local_checked,
        "local_low_quality": local_low_quality,
        "top_reasons": dict(reasons.most_common(5)),
    }


def _series_plan(latest: dict, queue: dict) -> dict:
    series_perf = latest.get("series_avg_engagement") or {}
    top_series = [
        str(key)
        for key, _ in sorted(
            series_perf.items(),
            key=lambda kv: float(kv[1] or 0),
            reverse=True,
        )[:5]
    ]
    stories = [item for item in (queue.get("stories") or []) if isinstance(item, dict) and not item.get("consumed")]
    queue_categories = Counter(str(item.get("category") or "unknown") for item in stories)
    return {
        "top_series": top_series,
        "queue_categories": dict(sorted(queue_categories.items())),
        "series_to_scale": top_series[:3],
        "identity_rule": "Keep series labels stable so viewers feel a programmed channel, not random uploads.",
    }


def _inventory_forecast(queue: dict, scheduler: dict) -> dict:
    stories = [item for item in (queue.get("stories") or []) if isinstance(item, dict) and not item.get("consumed")]
    pending = len(stories)
    windows = scheduler.get("recommended_utc_hours") or []
    daily_posts = max(1, min(24, len(windows) or 3))
    days_remaining = round(pending / daily_posts, 1) if daily_posts else 0.0
    if days_remaining >= 30:
        state = "excellent"
    elif days_remaining >= 14:
        state = "healthy"
    elif days_remaining >= 7:
        state = "watch"
    else:
        state = "thin"
    return {
        "pending": pending,
        "daily_posts": daily_posts,
        "days_remaining": days_remaining,
        "state": state,
    }


def build_ops_report(root: Path | str = ".") -> dict:
    root = Path(root)
    latest = _safe_json(root / "_data" / "analytics" / "latest.json")
    queue = _safe_json(root / "_data" / "stories_queue.json")
    health = _safe_json(root / "_data" / "automation_health.json")
    markers = _load_markers(root)

    avg_retention = float(latest.get("avg_view_pct", latest.get("avg_view_percentage", 0)) or 0)
    below_floor = latest.get("below_62_pct") or latest.get("below_60_pct") or []
    shorts_tracked = int(latest.get("shorts_tracked", 0) or 0)
    weak_ratio = (len(below_floor) / shorts_tracked) if shorts_tracked else 0.0
    paused = _paused_topics(latest)
    visual = _visual_quality(markers)

    risk_points = 0
    reasons: list[str] = []
    if health and health.get("state") != "excellent":
        risk_points += 25
        reasons.append("automation_health_not_excellent")
    if avg_retention and avg_retention < 52:
        risk_points += 25
        reasons.append("average_retention_below_52")
    elif avg_retention and avg_retention < 58:
        risk_points += 12
        reasons.append("average_retention_watch")
    if weak_ratio >= 0.5:
        risk_points += 20
        reasons.append("many_shorts_below_target_retention")
    if len(paused) >= 3:
        risk_points += 15
        reasons.append("multiple_topics_paused")
    if visual.get("rejected", 0):
        risk_points += 10
        reasons.append("visual_rejections_seen")
    risk_points = min(100, risk_points)
    risk_level = "critical" if risk_points >= 60 else ("watch" if risk_points >= 25 else "normal")

    scheduler = {
        "recommended_utc_hours": _recommended_hours(root, latest),
        "spacing_hours": 4 if risk_level == "normal" else 6,
        "policy": "Publish in recommended windows; widen spacing while risk is watch/critical.",
    }
    inventory = _inventory_forecast(queue, scheduler)
    paused_names = {item["category"] for item in paused}
    scale_categories = [
        item
        for item in (latest.get("production_recommendations") or {}).get("hot_categories", [])[:5]
        if str(item) not in paused_names
    ]
    remake_candidates = [
        item
        for item in (latest.get("remake_candidates") or [])
        if isinstance(item, dict) and _recommendable_title(str(item.get("title") or ""))
    ][:8]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "risk": {
            "level": risk_level,
            "score": risk_points,
            "reasons": reasons,
            "weak_retention_ratio": round(weak_ratio, 3),
            "avg_retention": round(avg_retention, 3),
        },
        "paused_topics": paused,
        "scheduler": scheduler,
        "inventory_forecast": inventory,
        "visual_quality": visual,
        "series_plan": _series_plan(latest, queue),
        "executive_report": {
            "summary": (
                "Automation is healthy; scale winners carefully."
                if risk_level == "normal"
                else "Automation is running, but editorial risk needs attention."
            ),
            "what_to_scale": scale_categories,
            "what_to_pause": [item["category"] for item in paused],
            "what_to_remake": remake_candidates,
            "inventory_state": inventory.get("state"),
            "next_actions": [
                "Favor high-retention categories and formats in the next queue refresh.",
                "Avoid paused topics until the hook or visual angle changes.",
                "Use recommended publish windows unless a manual campaign overrides them.",
                "Review visual QA failures before repeating that source style.",
            ],
        },
    }
    return report


def should_enforce_pause(report: dict) -> bool:
    return (report.get("risk") or {}).get("level") == "critical"
