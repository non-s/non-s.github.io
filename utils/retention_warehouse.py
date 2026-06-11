"""Retention warehouse normalization and Studio/API reconciliation."""

from __future__ import annotations

from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def normalize_retention_metrics(metrics: dict | None = None) -> dict:
    metrics = metrics or {}
    plays = _num(metrics.get("plays", metrics.get("views", 0)))
    engaged_views = _num(metrics.get("engaged_views", metrics.get("engagedViews", 0)))
    continued = metrics.get("continued_watch_rate", metrics.get("stayed_to_watch_rate"))
    continued_watch_rate = _num(continued, engaged_views / plays if plays else 0)
    swipe_rate = _num(metrics.get("swipe_rate", metrics.get("swipe_away_rate")), max(0.0, 1.0 - continued_watch_rate))
    retention_50_raw = _num(metrics.get("retention_50", metrics.get("average_view_percentage", 0)))
    return {
        "plays": int(plays),
        "engaged_views": int(engaged_views),
        "continued_watch_rate": round(continued_watch_rate, 6),
        "swipe_rate": round(swipe_rate, 6),
        "retention_1s": round(_num(metrics.get("retention_1s", metrics.get("retention_0_1", continued_watch_rate))), 6),
        "retention_3s": round(_num(metrics.get("retention_3s", metrics.get("retention_0_3", continued_watch_rate))), 6),
        "retention_50": round(
            retention_50_raw / (100 if retention_50_raw > 1 else 1),
            6,
        ),
        "retention_95": round(_num(metrics.get("retention_95", 0)), 6),
    }


def reconcile_studio_api(studio: dict | None = None, api: dict | None = None) -> dict:
    studio_norm = normalize_retention_metrics(studio)
    api_norm = normalize_retention_metrics(api)
    fields = ("plays", "engaged_views", "continued_watch_rate", "swipe_rate")
    deltas = {}
    for field in fields:
        base = max(abs(float(studio_norm.get(field, 0))), 1.0)
        deltas[field] = round(abs(float(studio_norm.get(field, 0)) - float(api_norm.get(field, 0))) / base, 6)
    max_delta = max(deltas.values()) if deltas else 0
    return {
        "studio": studio_norm,
        "api": api_norm,
        "deltas": deltas,
        "max_delta": max_delta,
        "within_2pct": max_delta <= 0.02,
    }
