"""Data-quality reporting for local Wild Brief learning files."""
from __future__ import annotations

from datetime import datetime, timezone

from utils.confidence_engine import assess_confidence, data_quality_from_counts


METRICS = {
    "views": ("views", "viewCount"),
    "likes": ("likes", "likeCount"),
    "comments": ("comments", "commentCount"),
    "retention": ("averageViewPercentage", "avg_view_pct", "avg_view_percentage"),
    "watch_time": ("averageViewDuration",),
    "subscribers": ("subscribersGained", "subscribers_gained"),
}


def _has_value(source: dict, names: tuple[str, ...]) -> bool:
    for name in names:
        try:
            if float(source.get(name) or 0) > 0:
                return True
        except Exception:
            continue
    return False


def build_data_quality_report(markers: list[dict], *,
                              audience_memory: dict | None = None,
                              format_memory: dict | None = None,
                              early_performance: dict | None = None) -> dict:
    markers = markers or []
    metric_rows = {}
    for metric, names in METRICS.items():
        observed = 0
        missing = 0
        for marker in markers:
            stats = marker.get("analytics") if isinstance(marker.get("analytics"), dict) else {}
            if _has_value(stats, names) or _has_value(marker, names):
                observed += 1
            else:
                missing += 1
        quality = data_quality_from_counts(observed=observed, missing=missing)
        metric_rows[metric] = {
            "observed": observed,
            "estimated": 0,
            "inferred": 0,
            "missing": missing,
            "data_quality": quality["data_quality"],
            "data_quality_score": quality["data_quality_score"],
            "origin": "YouTube Analytics/Public API joined to .done markers" if observed else "missing",
        }

    early = early_performance or {}
    checkpoint_counts = {"observed": 0, "estimated": 0, "missing": 0}
    for video in (early.get("videos") or {}).values():
        for checkpoint in (video.get("checkpoints") or {}).values():
            for metric in checkpoint.values():
                source = str(metric.get("source") or "missing")
                checkpoint_counts[source if source in checkpoint_counts else "missing"] += 1
    checkpoint_quality = data_quality_from_counts(**checkpoint_counts)
    metric_rows["early_checkpoints"] = {
        **checkpoint_counts,
        "inferred": 0,
        "data_quality": checkpoint_quality["data_quality"],
        "data_quality_score": checkpoint_quality["data_quality_score"],
        "origin": "local repeated snapshots; estimated until a near-checkpoint snapshot exists",
    }

    audience = audience_memory or {}
    fmt = format_memory or {}
    confidence_sources = [
        assess_confidence(
            "distribution",
            int(early.get("sample_count") or 0),
            observed=checkpoint_counts["observed"],
            estimated=checkpoint_counts["estimated"],
            missing=checkpoint_counts["missing"],
        ),
        assess_confidence(
            "category",
            int(audience.get("sample_count") or 0),
            observed=int((audience.get("coverage") or {}).get("with_retention") or 0)
            + int((audience.get("coverage") or {}).get("with_subscribers") or 0),
            missing=max(0, int(audience.get("sample_count") or 0) * 2),
        ),
        assess_confidence(
            "format",
            int(fmt.get("sample_count") or 0),
            observed=int((fmt.get("data_coverage") or {}).get("views") or 0),
            missing=max(0, int(fmt.get("sample_count") or 0) - int((fmt.get("data_coverage") or {}).get("views") or 0)),
        ),
    ]
    overall_confidence = round(sum(item["confidence_score"] for item in confidence_sources) / len(confidence_sources), 3)
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sample_count": len(markers),
        "bootstrap_mode": overall_confidence < 0.55,
        "overall_confidence_score": overall_confidence,
        "minimum_sample_rules": {
            "category": 5,
            "format": 5,
            "series": 3,
            "distribution": 8,
        },
        "metrics": metric_rows,
        "systems": {
            "audience_memory": {
                "sample_count": audience.get("sample_count", 0),
                "bootstrap_mode": audience.get("bootstrap_mode", True),
                "coverage": audience.get("coverage", {}),
            },
            "format_memory": {
                "sample_count": fmt.get("sample_count", 0),
                "coverage": fmt.get("data_coverage", {}),
            },
            "early_performance": {
                "sample_count": early.get("sample_count", 0),
                "checkpoint_quality": checkpoint_quality,
            },
        },
        "recommendations": [
            "Treat estimated early checkpoints as watchlist signals until repeated snapshots exist.",
            "Do not promote or penalize category/format/series below minimum sample rules.",
            "Prefer observed retention and subscriber metrics over view-only signals.",
        ],
    }
