"""Real audience memory for retention, subscribers, comments and return proxy."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from utils.confidence_engine import assess_confidence, blend_weight

AUDIENCE_MEMORY_PATH = Path("_data/audience_memory.json")


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def _stats(marker: dict) -> dict:
    return marker.get("analytics") if isinstance(marker.get("analytics"), dict) else {}


def _series_base(series: str) -> str:
    return re.sub(r"\s+#\d+$", "", str(series or "").strip()) or "Unassigned"


def _row_metrics(marker: dict) -> dict:
    stats = _stats(marker)
    views = _num(stats.get("views") or stats.get("viewCount") or marker.get("views"))
    comments = _num(stats.get("comments") or stats.get("commentCount") or marker.get("comments"))
    subs = _num(stats.get("subscribersGained") or marker.get("subscribers_gained"))
    retention = _num(
        stats.get("averageViewPercentage") or stats.get("avg_view_pct") or stats.get("avg_view_percentage")
    )
    watch_time = _num(stats.get("averageViewDuration"))
    return {
        "views": views,
        "comments": comments,
        "subscribers": subs,
        "retention": retention,
        "watch_time": watch_time,
        "subs_per_1k": subs * 1000 / max(views, 1),
        "comments_per_1k": comments * 1000 / max(views, 1),
    }


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def build_audience_memory(markers: list[dict]) -> dict:
    buckets: dict[str, dict[str, list[dict]]] = {
        "category": defaultdict(list),
        "format": defaultdict(list),
        "series": defaultdict(list),
    }
    videos = []
    for marker in markers:
        metrics = _row_metrics(marker)
        if metrics["views"] <= 0:
            continue
        category = str(marker.get("category") or "unknown").lower()
        fmt = str(marker.get("story_format") or "unknown").lower()
        series = _series_base(str(marker.get("series") or "Unassigned"))
        row = {
            "video_id": marker.get("video_id", ""),
            "title": marker.get("title", ""),
            "category": category,
            "story_format": fmt,
            "series": series,
            **metrics,
        }
        videos.append(row)
        buckets["category"][category].append(metrics)
        buckets["format"][fmt].append(metrics)
        buckets["series"][series].append(metrics)

    def summarize(rows: list[dict]) -> dict:
        retention_values = [r["retention"] for r in rows if r["retention"]]
        watch_values = [r["watch_time"] for r in rows if r["watch_time"]]
        retention = _avg(retention_values)
        subs = _avg([r["subs_per_1k"] for r in rows])
        comments = _avg([r["comments_per_1k"] for r in rows])
        watch = _avg(watch_values)
        return_proxy = round(retention * 0.45 + subs * 8 + comments * 2 + min(20, len(rows) * 1.5), 3)
        return {
            "n": len(rows),
            "views": int(sum(r["views"] for r in rows)),
            "retention_samples": len(retention_values),
            "watch_time_samples": len(watch_values),
            "avg_retention": retention,
            "avg_watch_time": watch,
            "subs_per_1k": subs,
            "comments_per_1k": comments,
            "return_proxy": return_proxy,
        }

    summaries = {axis: {key: summarize(rows) for key, rows in values.items()} for axis, values in buckets.items()}
    for axis, values in summaries.items():
        confidence_axis = "series" if axis == "series" else axis
        for item in values.values():
            observed = item.get("retention_samples", 0) + item.get("watch_time_samples", 0) + item["n"]
            item["confidence"] = assess_confidence(
                confidence_axis,
                item["n"],
                observed=observed,
                estimated=max(0, item["n"] * 3 - observed),
            )

    def weights(axis: str, metric: str, baseline: float, scale: float) -> dict[str, float]:
        out = {}
        for key, item in summaries[axis].items():
            confidence_axis = "series" if axis == "series" else axis
            observed = item.get("retention_samples", 0) + item.get("watch_time_samples", 0)
            if metric in {"subs_per_1k", "comments_per_1k", "return_proxy"}:
                observed += item["n"]
            confidence = assess_confidence(
                confidence_axis,
                item["n"],
                observed=observed,
                estimated=max(0, item["n"] * 3 - observed),
            )
            item["confidence"] = confidence
            if not confidence["can_adjust_strategy"]:
                continue
            if metric == "avg_retention" and not item.get("retention_samples"):
                continue
            if metric == "return_proxy" and not (
                item.get("retention_samples") or item.get("subs_per_1k") or item.get("comments_per_1k")
            ):
                continue
            raw = max(0.78, min(1.28, 1 + ((item[metric] - baseline) / scale)))
            out[key] = blend_weight(raw, confidence)
        return out

    def ranked(axis: str, reverse: bool = True) -> list[dict]:
        return [
            {"value": key, **item}
            for key, item in sorted(
                summaries[axis].items(),
                key=lambda kv: (kv[1]["return_proxy"], kv[1]["subs_per_1k"], kv[1]["avg_retention"]),
                reverse=reverse,
            )
        ]

    return {
        "sample_count": len(videos),
        "bootstrap_mode": len(videos) < 30 or sum(1 for v in videos if v["retention"]) < 15,
        "minimum_sample_rules": {
            "category": 5,
            "format": 5,
            "series": 3,
        },
        "coverage": {
            "with_retention": sum(1 for v in videos if v["retention"]),
            "with_subscribers": sum(1 for v in videos if v["subscribers"]),
            "with_comments": sum(1 for v in videos if v["comments"]),
            "with_watch_time": sum(1 for v in videos if v["watch_time"]),
        },
        "category": summaries["category"],
        "format": summaries["format"],
        "series": summaries["series"],
        "weights": {
            "category_retention": weights("category", "avg_retention", 60, 80),
            "category_subscribers": weights("category", "subs_per_1k", 1.5, 10),
            "category_comments": weights("category", "comments_per_1k", 0.4, 8),
            "format_retention": weights("format", "avg_retention", 60, 80),
            "format_subscribers": weights("format", "subs_per_1k", 1.5, 10),
            "series_return": weights("series", "return_proxy", 40, 90),
        },
        "winners": {
            "category": ranked("category")[:6],
            "format": ranked("format")[:6],
            "series": ranked("series")[:6],
        },
        "losers": {
            "category": ranked("category", reverse=False)[:6],
            "format": ranked("format", reverse=False)[:6],
            "series": ranked("series", reverse=False)[:6],
        },
    }


@lru_cache(maxsize=4)
def load_audience_memory(path: Path = AUDIENCE_MEMORY_PATH) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_audience_memory(markers: list[dict], path: Path = AUDIENCE_MEMORY_PATH) -> dict:
    payload = build_audience_memory(markers)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    load_audience_memory.cache_clear()
    return payload
