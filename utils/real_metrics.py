"""Helpers for joining local .done markers with real channel analytics."""
from __future__ import annotations

import json
from pathlib import Path


def safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def latest_video_rows(latest: dict) -> list[dict]:
    rows = []
    for key in ("top_performers", "remake_candidates"):
        values = latest.get(key) or []
        if isinstance(values, list):
            rows.extend(item for item in values if isinstance(item, dict))
    matrix = latest.get("video_rows") or latest.get("observations") or []
    if isinstance(matrix, list):
        rows.extend(item for item in matrix if isinstance(item, dict))
    return rows


def analytics_by_video_id(latest: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in latest_video_rows(latest):
        video_id = str(row.get("video_id") or "").strip()
        if not video_id:
            continue
        current = out.get(video_id, {})
        merged = {**current, **row}
        out[video_id] = merged
    return out


def public_stats_by_video_id(youtube_intelligence: dict) -> dict[str, dict]:
    audit = youtube_intelligence.get("video_audit") if isinstance(youtube_intelligence.get("video_audit"), dict) else {}
    rows = audit.get("top_public_videos") or []
    out: dict[str, dict] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        video_id = str(row.get("video_id") or "").strip()
        if video_id:
            out[video_id] = row
    return out


def enrich_markers_with_latest(markers: list[dict], latest: dict,
                               youtube_intelligence: dict | None = None) -> list[dict]:
    analytics_map = analytics_by_video_id(latest)
    public_map = public_stats_by_video_id(youtube_intelligence or {})
    enriched = []
    for marker in markers:
        out = dict(marker)
        video_id = str(out.get("video_id") or "")
        row = analytics_map.get(video_id)
        public = public_map.get(video_id, {})
        if row or public:
            row = row or {}
            existing = out.get("analytics") if isinstance(out.get("analytics"), dict) else {}
            out["analytics"] = {
                **existing,
                "views": row.get("views", row.get("viewCount", public.get("views", existing.get("views", 0)))),
                "likes": row.get("likes", row.get("likeCount", public.get("likes", existing.get("likes", 0)))),
                "comments": row.get("comments", row.get("commentCount", public.get("comments", existing.get("comments", 0)))),
                "averageViewPercentage": row.get(
                    "average_view_percentage",
                    row.get("view_pct", row.get("avg_view_pct", existing.get("averageViewPercentage", 0))),
                ),
                "averageViewDuration": row.get("average_view_duration", existing.get("averageViewDuration", 0)),
                "subscribersGained": row.get("subscribers_gained", row.get("subscribersGained", existing.get("subscribersGained", 0))),
                "viewsPerHour": row.get("views_per_hour", existing.get("viewsPerHour", 0)),
                "growthScore": row.get("growth_score", existing.get("growthScore", 0)),
            }
            for key in ("category", "story_format", "series"):
                if row.get(key) and not out.get(key):
                    out[key] = row[key]
        enriched.append(out)
    return enriched


def data_coverage(markers: list[dict]) -> dict:
    metrics = {
        "views": 0,
        "retention": 0,
        "watch_time": 0,
        "subscribers": 0,
        "comments": 0,
    }
    for marker in markers:
        stats = marker.get("analytics") if isinstance(marker.get("analytics"), dict) else {}
        if float(stats.get("views") or stats.get("viewCount") or marker.get("views") or 0):
            metrics["views"] += 1
        if float(stats.get("averageViewPercentage") or stats.get("avg_view_pct") or 0):
            metrics["retention"] += 1
        if float(stats.get("averageViewDuration") or 0):
            metrics["watch_time"] += 1
        if float(stats.get("subscribersGained") or marker.get("subscribers_gained") or 0):
            metrics["subscribers"] += 1
        if float(stats.get("comments") or stats.get("commentCount") or marker.get("comments") or 0):
            metrics["comments"] += 1
    total = len(markers)
    return {"total_markers": total, **metrics}
