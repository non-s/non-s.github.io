"""Seven-day content agency plan from local signals."""
from __future__ import annotations


def build_plan(*, latest: dict, health: dict, ops: dict, trend: dict) -> dict:
    recs = latest.get("production_recommendations") or {}
    paused = [item.get("category") for item in (ops.get("paused_topics") or []) if item.get("category")]
    paused_set = {str(item).lower() for item in paused}
    hot_categories = [
        item for item in list(recs.get("hot_categories") or [])
        if str(item).lower() not in paused_set
    ]
    if not hot_categories:
        hot_categories = [
            item for item in ("farm", "wildlife", "birds", "ocean", "dogs")
            if item not in paused_set
        ]
    trend_topics = trend.get("topics") or []
    green_trends = [
        item for item in trend_topics
        if (item.get("trend_safety") or {}).get("posture") in {"greenlight", "watch"}
    ]
    publish_now = int(((health.get("agency") or {}).get("decisions") or {}).get("publish_now", 0) or 0)
    days = []
    for i in range(7):
        focus = hot_categories[i % len(hot_categories)] if hot_categories else "wildlife"
        trend_item = green_trends[i % len(green_trends)] if green_trends else {}
        days.append({
            "day": i + 1,
            "focus": focus,
            "trend_animal": trend_item.get("animal", ""),
            "mix": "2 exploit + 1 explore" if publish_now >= 21 else "1 exploit + 2 explore",
            "avoid": paused[:3],
            "goal": "raise retention above 60%" if float(latest.get("avg_view_pct", 0) or 0) < 60 else "scale strongest series",
        })
    return {
        "status": "aggressive_growth" if publish_now >= 21 else "build_inventory_quality",
        "publish_now_inventory": publish_now,
        "weekly_goal": "Push average retention toward 70% while scaling winning formats.",
        "days": days,
    }
