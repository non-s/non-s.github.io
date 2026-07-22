"""Normalize YouTube Studio Shorts Reach exports.

The Studio UI can export "viewed vs swiped away" data, but column names vary
by locale/export surface. This module accepts several common spellings and
returns one stable row shape for the local analytics warehouse.
"""

from __future__ import annotations

import csv
import re
from datetime import datetime, timezone
from pathlib import Path


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _num(value, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip().replace("%", "").replace(",", "")
    if not text:
        return default
    try:
        return float(text)
    except Exception:
        return default


def _first(row: dict, *names: str, default=""):
    normalised = {_key(k): v for k, v in row.items()}
    for name in names:
        key = _key(name)
        if key in normalised and normalised[key] not in (None, ""):
            return normalised[key]
    return default


def build_reach_row(row: dict, *, imported_at: str | None = None, source_file: str = "") -> dict:
    """Build a normalized Studio Reach row from one CSV row."""
    imported_at = imported_at or datetime.now(timezone.utc).isoformat()
    video_id = str(
        _first(
            row,
            "video_id",
            "Video ID",
            "Content",
            "Content ID",
            "External video ID",
        )
    ).strip()
    title = str(_first(row, "title", "Video title", "Content title", "Video", default="")).strip()
    views = _num(_first(row, "views", "Shorts views", "Shown in feed", "Impressions", default=0))
    stayed = _num(
        _first(
            row,
            "stayed_to_watch",
            "Stayed to watch",
            "Viewed",
            "Viewed vs swiped away viewed",
            "Shorts feed viewed",
            default=0,
        )
    )
    swiped = _num(
        _first(
            row,
            "swiped_away",
            "Swiped away",
            "Swipe away",
            "Viewed vs swiped away swiped away",
            "Shorts feed swiped away",
            default=0,
        )
    )
    stayed_rate = _num(_first(row, "stayed_to_watch_rate", "Stayed to watch %", "Viewed %", default=0))
    swipe_rate = _num(_first(row, "swipe_away_rate", "Swiped away %", "Swipe away %", default=0))
    if not stayed_rate and stayed and swiped:
        stayed_rate = 100 * stayed / max(stayed + swiped, 1)
    if not swipe_rate and stayed and swiped:
        swipe_rate = 100 * swiped / max(stayed + swiped, 1)
    if stayed_rate > 1:
        stayed_rate /= 100
    if swipe_rate > 1:
        swipe_rate /= 100
    return {
        "row_type": "studio_reach_daily",
        "imported_at": imported_at,
        "date": str(_first(row, "date", "Day", "Date", default=""))[:10],
        "video_id": video_id,
        "title": title,
        "metrics": {
            "views": int(views),
            "stayed_to_watch": int(stayed),
            "swiped_away": int(swiped),
            "stayed_to_watch_rate": round(float(stayed_rate), 4),
            "swipe_away_rate": round(float(swipe_rate), 4),
        },
        "source_file": source_file,
    }


def read_reach_csv(path: Path, *, imported_at: str | None = None) -> list[dict]:
    """Read a Studio Reach CSV into normalized rows."""
    rows: list[dict] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            built = build_reach_row(row, imported_at=imported_at, source_file=str(path))
            if built["video_id"] or built["title"]:
                rows.append(built)
    return rows


def summarize_reach(rows: list[dict]) -> dict:
    """Return dashboard-friendly aggregate reach metrics."""
    total_views = sum(int((row.get("metrics") or {}).get("views") or 0) for row in rows)
    stayed = sum(int((row.get("metrics") or {}).get("stayed_to_watch") or 0) for row in rows)
    swiped = sum(int((row.get("metrics") or {}).get("swiped_away") or 0) for row in rows)
    denom = max(stayed + swiped, 1)
    worst = sorted(
        rows,
        key=lambda row: float((row.get("metrics") or {}).get("swipe_away_rate") or 0),
        reverse=True,
    )[:10]
    return {
        "rows": len(rows),
        "videos": len({row.get("video_id") or row.get("title") for row in rows}),
        "views": total_views,
        "stayed_to_watch": stayed,
        "swiped_away": swiped,
        "stayed_to_watch_rate": round(stayed / denom, 4),
        "swipe_away_rate": round(swiped / denom, 4),
        "worst_swipe_videos": worst,
    }
