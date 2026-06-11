"""JSONL schemas for Wild Brief growth analytics.

The builders here normalize partial YouTube/API/sidecar data into stable rows.
They are intentionally tolerant of missing fields so scheduled jobs can keep
publishing even when analytics are delayed or unavailable.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "wild-brief-growth-v1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _metric(metrics: dict, *names: str, default: Any = 0) -> Any:
    for name in names:
        if name in metrics and metrics.get(name) is not None:
            return metrics.get(name)
    return default


def _safe_rate(numerator: float, denominator: float) -> float:
    return float(numerator) / max(float(denominator), 1.0)


def _source_diversity(distribution: dict[str, int | float] | None) -> float:
    if not distribution:
        return 0.0
    values = [max(0.0, _float(value)) for value in distribution.values()]
    total = sum(values)
    if total <= 0:
        return 0.0
    entropy = 0.0
    for value in values:
        if value <= 0:
            continue
        share = value / total
        entropy -= share * math.log2(share)
    max_entropy = math.log2(len(values)) if len(values) > 1 else 1.0
    return round(entropy / max_entropy, 6)


def build_video_metric_row(
    video_id: str,
    title: str = "",
    metrics: dict | None = None,
    context: dict | None = None,
    variants: dict | None = None,
    traffic_sources: dict | None = None,
    pulled_at: str | None = None,
) -> dict:
    """Build a normalized per-video analytics row."""
    metrics = metrics or {}
    context = context or {}
    variants = variants or context.get("variants") or context.get("experiments") or {}
    traffic_sources = traffic_sources or context.get("traffic_sources") or {}

    views = _int(_metric(metrics, "views", "viewCount"))
    engaged_views = _int(_metric(metrics, "engaged_views", "engagedViews"))
    estimated_minutes = _float(_metric(metrics, "estimated_minutes_watched", "estimatedMinutesWatched"))
    average_view_duration = _float(_metric(metrics, "average_view_duration", "averageViewDuration"))
    average_view_percentage = _float(_metric(metrics, "average_view_percentage", "averageViewPercentage", "view_pct"))
    likes = _int(_metric(metrics, "likes", "likeCount"))
    comments = _int(_metric(metrics, "comments", "commentCount"))
    shares = _int(_metric(metrics, "shares"))
    subscribers_gained = _int(_metric(metrics, "subscribers_gained", "subscribersGained"))

    derived = {
        "engaged_view_rate": round(_safe_rate(engaged_views, views), 6),
        "replay_rate_proxy": round(_safe_rate(max(views - engaged_views, 0), engaged_views), 6),
        "sub_per_1k_engaged": round(1000 * _safe_rate(subscribers_gained, engaged_views), 6),
        "comment_rate_per_1k_engaged": round(1000 * _safe_rate(comments, engaged_views), 6),
        "minutes_per_engaged_view": round(_safe_rate(estimated_minutes * 60, engaged_views), 6),
        "source_diversity": _source_diversity(traffic_sources),
    }
    row = {
        "schema_version": SCHEMA_VERSION,
        "row_type": "video_metric",
        "pulled_at": pulled_at or _text(context.get("pulled_at")) or _now_iso(),
        "video_id": _text(video_id),
        "title": _text(title or context.get("title")),
        "category": _text(context.get("category")),
        "series": _text(context.get("series")),
        "format": _text(context.get("format") or context.get("story_format")),
        "publish_slot": _text(context.get("publish_slot")),
        "variants": {str(k): str(v) for k, v in dict(variants).items()},
        "metrics": {
            "views": views,
            "engaged_views": engaged_views,
            "estimated_minutes_watched": estimated_minutes,
            "average_view_duration": average_view_duration,
            "average_view_percentage": average_view_percentage,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "subscribers_gained": subscribers_gained,
        },
        "traffic_sources": {str(k): _float(v) for k, v in dict(traffic_sources).items()},
        "derived": derived,
    }
    validate_row(row, "video_metric")
    return row


def build_variant_row(
    axis: str,
    variant: str,
    story_id: str,
    video_id: str = "",
    assigned_at: str | None = None,
    context: dict | None = None,
) -> dict:
    """Build a row recording one deterministic experiment assignment."""
    context = context or {}
    row = {
        "schema_version": SCHEMA_VERSION,
        "row_type": "variant_assignment",
        "assigned_at": assigned_at or _text(context.get("assigned_at")) or _now_iso(),
        "axis": _text(axis),
        "variant": _text(variant),
        "story_id": _text(story_id),
        "video_id": _text(video_id or context.get("video_id")),
        "category": _text(context.get("category")),
        "series": _text(context.get("series")),
        "format": _text(context.get("format") or context.get("story_format")),
    }
    validate_row(row, "variant_assignment")
    return row


def build_retention_row(
    video_id: str,
    elapsed_video_time_ratio: float,
    audience_watch_ratio: float,
    pulled_at: str | None = None,
    context: dict | None = None,
) -> dict:
    """Build one retention-curve bucket row."""
    context = context or {}
    row = {
        "schema_version": SCHEMA_VERSION,
        "row_type": "retention_bucket",
        "pulled_at": pulled_at or _text(context.get("pulled_at")) or _now_iso(),
        "video_id": _text(video_id),
        "elapsed_video_time_ratio": round(_float(elapsed_video_time_ratio), 6),
        "audience_watch_ratio": round(_float(audience_watch_ratio), 6),
        "source": _text(context.get("source") or "youtube_analytics"),
    }
    validate_row(row, "retention_bucket")
    return row


def build_trend_signal_row(
    source: str,
    topic: str,
    score: float,
    observed_at: str | None = None,
    context: dict | None = None,
) -> dict:
    """Build a normalized free-signal topic row."""
    context = context or {}
    row = {
        "schema_version": SCHEMA_VERSION,
        "row_type": "trend_signal",
        "observed_at": observed_at or _text(context.get("observed_at")) or _now_iso(),
        "source": _text(source),
        "topic": _text(topic),
        "score": round(_float(score), 6),
        "url": _text(context.get("url")),
        "category": _text(context.get("category")),
        "notes": list(context.get("notes") or []),
    }
    validate_row(row, "trend_signal")
    return row


def validate_row(row: dict, row_type: str | None = None) -> bool:
    """Raise ValueError when a row misses its core schema contract."""
    expected = row_type or row.get("row_type")
    if row.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("missing or invalid schema_version")
    if expected and row.get("row_type") != expected:
        raise ValueError(f"expected row_type {expected!r}")
    required = {
        "video_metric": ("pulled_at", "video_id", "metrics", "derived"),
        "variant_assignment": ("assigned_at", "axis", "variant", "story_id"),
        "retention_bucket": ("pulled_at", "video_id", "elapsed_video_time_ratio", "audience_watch_ratio"),
        "trend_signal": ("observed_at", "source", "topic", "score"),
    }.get(str(row.get("row_type")), ())
    for key in required:
        if key not in row:
            raise ValueError(f"missing required field: {key}")
    json.dumps(row, ensure_ascii=False)
    return True


def write_jsonl_row(path: Path, row: dict) -> None:
    """Append one validated JSONL row, creating parent directories."""
    validate_row(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    """Read JSONL rows. Missing files return an empty list."""
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows
