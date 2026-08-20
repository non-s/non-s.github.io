"""Join YouTube observations to creative memory using comparable age windows."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from utils.atomic_state import load_versioned, save_versioned
from utils.research_engine import compute_fitness
from utils.state_lock import state_lock

CATALOG_SCHEMA_VERSION = 1


def age_window(published_at: str, observed_at: str | None = None) -> str:
    """Map cumulative metrics to the closest non-overlapping maturity window."""
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00")) if observed_at else datetime.now(UTC)
        hours = max(0.0, (observed - published).total_seconds() / 3600.0)
    except (AttributeError, TypeError, ValueError):
        return "unknown"
    if hours < 1:
        return "early"
    if hours < 6:
        return "1h"
    if hours < 24:
        return "6h"
    if hours < 72:
        return "24h"
    if hours < 24 * 14:
        return "72h"
    return "mature"


def _duration_seconds(raw: Any) -> float:
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", str(raw or ""))
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours or 0) * 3600 + int(minutes or 0) * 60 + float(seconds or 0)


def normalized_metrics(video: dict[str, Any]) -> dict[str, Any]:
    """Translate actual API fields; absent metrics are intentionally omitted."""
    views = max(0, int(video.get("views") or 0))
    result: dict[str, Any] = {
        "views": views,
        "likes": max(0, int(video.get("likes") or 0)),
        "comments": max(0, int(video.get("comments") or 0)),
        "duration_seconds": _duration_seconds(video.get("duration")),
    }
    aliases = {
        "averageViewPercentage": "average_percentage_viewed",
        "averageViewDuration": "average_view_duration_seconds",
        "ctr": "impressions_ctr",
        "impressionsCtr": "impressions_ctr",
        "subscribersGained": "subscribers_gained",
        "viewedPercentage": "viewed_percentage",
    }
    for source, target in aliases.items():
        if video.get(source) is not None:
            result[target] = float(video[source])
    if views:
        result["engagement_rate"] = (result["likes"] + result["comments"]) / views
        if "subscribers_gained" in result:
            result["subscriber_conversion"] = result["subscribers_gained"] / views
    return result


def sync_catalog_performance(
    data_root: Path,
    videos: list[dict[str, Any]],
    video_tags: dict[str, Any],
    *,
    observed_at: str | None = None,
) -> dict[str, int]:
    """Attach API evidence to existing creations; never create phantom catalog items."""
    path = data_root / "catalog_memory.json"
    summary = {"matched": 0, "unmatched": 0, "updated": 0}
    if not path.exists():
        summary["unmatched"] = len(videos)
        return summary
    observed = observed_at or datetime.now(UTC).isoformat()
    with state_lock(path):
        catalog = load_versioned(path, CATALOG_SCHEMA_VERSION, {}, [])
        if not isinstance(catalog, list):
            raise ValueError("catalog memory data must be a list")
        by_content = {item.get("content_id"): item for item in catalog if isinstance(item, dict)}
        for video in videos:
            video_id = str(video.get("video_id", ""))
            tag = video_tags.get(video_id, {}) if isinstance(video_tags, dict) else {}
            content = tag.get("content_id") if isinstance(tag, dict) else None
            item = by_content.get(content)
            if not content or item is None:
                summary["unmatched"] += 1
                continue
            summary["matched"] += 1
            metrics = normalized_metrics(video)
            window = age_window(str(video.get("published_at", "")), observed)
            snapshot = {"observed_at": observed, "video_id": video_id, "window": window, **metrics}
            windows = item.setdefault("performance_windows", {})
            previous = windows.get(window) if isinstance(windows, dict) else None
            if not isinstance(previous, dict) or previous != snapshot:
                windows[window] = snapshot
                novelty = item.get("visual_dna", {}).get("novelty", {}).get("recent_distance")
                item["fitness"] = compute_fitness(metrics, str(item.get("kind", "long")), novelty=novelty).to_dict()
                item["youtube_video_id"] = video_id
                summary["updated"] += 1
        if summary["updated"]:
            save_versioned(path, catalog, CATALOG_SCHEMA_VERSION)
    return summary
