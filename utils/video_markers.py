"""Helpers for reading uploaded video marker files."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def read_marker(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def marker_timestamp(marker: dict) -> float:
    for field in ("uploaded_at", "published_at", "publish_ts_utc", "generated_at", "fetched_at"):
        raw = str(marker.get(field) or "").strip()
        if not raw:
            continue
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    return 0.0


def sorted_done_markers(
    root: Path,
    directories: Iterable[str] = ("_videos",),
    *,
    newest_first: bool = False,
) -> list[tuple[Path, dict]]:
    rows: list[tuple[Path, dict]] = []
    for directory_name in directories:
        directory = root / directory_name
        if not directory.exists():
            continue
        for path in directory.glob("*.done"):
            marker = read_marker(path)
            if marker:
                rows.append((path, marker))
    rows.sort(
        key=lambda row: (marker_timestamp(row[1]) or row[0].stat().st_mtime, row[0].name),
        reverse=newest_first,
    )
    return rows
