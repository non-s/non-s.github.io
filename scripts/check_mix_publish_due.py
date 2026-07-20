#!/usr/bin/env python3
"""Gate for lofi-mix-daily.yml: due only once >= MIN_HOURS have passed since
the last successfully published horizontal mix.

Exists because relying on a single daily `schedule:` cron firing is fragile
-- checked live (chat, 2026-07-20): GitHub Actions silently dropped an
entire day's trigger for this exact workflow, with zero run record, no
error, nothing to retry. lofi-mix-daily.yml now polls every 15 minutes
instead, and this script is the guard that keeps that from publishing one
mix every 15 minutes: a run only does the real work when the elapsed time
since the last published mix's `_videos/mix-*.done` marker has crossed the
threshold, so a single missed poll costs at most ~15 minutes of drift
instead of losing the rest of the day.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VIDEOS_DIR = ROOT / "_videos"
MIN_HOURS_BETWEEN_PUBLISHES = 24.0


def _parse_ts(value: str) -> datetime | None:
    value = str(value or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _load_marker(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def last_mix_publish(videos_dir: Path = VIDEOS_DIR) -> tuple[datetime | None, str]:
    """Latest publish_ts_utc across every committed mix `.done` marker, and
    that marker's video_id. (None, "") when no mix has ever published --
    a first run must never be blocked waiting on a marker that can't
    exist yet."""
    best_ts: datetime | None = None
    best_id = ""
    for marker_path in sorted(videos_dir.glob("mix-*.done")):
        marker = _load_marker(marker_path)
        # Prefer the real upload completion time over publish_ts_utc, same
        # reasoning as scripts/check_publishing_health.py's identical
        # choice: publish_ts_utc can be a *future* scheduled-publish time
        # when YOUTUBE_SCHEDULE_UPLOADS is on, which would understate how
        # long it's actually been since a mix last really published.
        upload_intent = marker.get("upload_intent") or {}
        ts = (
            _parse_ts(upload_intent.get("created_at") if isinstance(upload_intent, dict) else "")
            or _parse_ts(marker.get("publish_ts_utc"))
            or _parse_ts(marker.get("scheduled_publish_at"))
        )
        if ts is None:
            continue
        if best_ts is None or ts > best_ts:
            best_ts = ts
            best_id = str(marker.get("video_id") or "")
    return best_ts, best_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--min-hours", type=float, default=MIN_HOURS_BETWEEN_PUBLISHES)
    args = parser.parse_args()

    last_ts, last_id = last_mix_publish(VIDEOS_DIR)
    now = datetime.now(timezone.utc)
    hours_since = (now - last_ts).total_seconds() / 3600.0 if last_ts else None
    due = last_ts is None or hours_since >= args.min_hours

    result = {
        "due": due,
        "hours_since_last_publish": round(hours_since, 2) if hours_since is not None else None,
        "last_publish_ts_utc": last_ts.isoformat() if last_ts else None,
        "last_video_id": last_id,
    }
    if args.json:
        print(json.dumps(result))
    else:
        print(
            f"due={str(due).lower()} hours_since_last_publish={result['hours_since_last_publish']} "
            f"last_video_id={last_id or '(none)'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
