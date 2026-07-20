#!/usr/bin/env python3
"""Detect silent degradation in the lofi publishing pipeline.

youtube-bot.yml and lofi-mix-daily.yml can both "succeed" (green
checkmark, exit 0) on a run that uploaded nothing at all -- an empty or
stale b-roll/bgm library, a sustained Pixabay/Jamendo outage, or an
unnoticed upstream API contract change could all silently zero out
uploads for hours or days while every run keeps reporting success.
ops-alert.yml already catches genuinely *failed* runs; this catches the
quieter case by checking how long it's actually been since a real upload
landed, and failing (non-zero exit) if that's too long while publishing
is supposed to be active. Wired into ops-alert.yml's workflow_run list
like any other monitored workflow, so a degraded run raises the same
GitHub issue alert as a hard failure would -- no separate alerting path
to maintain.

Uses each .done marker's `upload_intent.created_at` -- set once, at the
moment upload_youtube.py actually completed the YouTube API call (see
its _done_marker() call site) -- rather than `publish_ts_utc`, which can
be a *future* scheduled-publish time when YOUTUBE_SCHEDULE_UPLOADS is on
and so would understate how long it's actually been since the pipeline
last did real work.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VIDEOS_DIR = ROOT / "_videos"
DEFAULT_STALE_HOURS = 26.0  # hourly Shorts cadence + safety margin for GitHub cron drift


def _marker_upload_ts(marker: dict) -> datetime | None:
    created_at = str((marker.get("upload_intent") or {}).get("created_at") or "")
    if not created_at:
        return None
    try:
        stamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def most_recent_upload_ts(videos_dir: Path = VIDEOS_DIR) -> datetime | None:
    latest: datetime | None = None
    for path in sorted(videos_dir.glob("*.done")):
        try:
            marker = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        stamp = _marker_upload_ts(marker)
        if stamp and (latest is None or stamp > latest):
            latest = stamp
    return latest


def check(
    *,
    stale_hours: float = DEFAULT_STALE_HOURS,
    now: datetime | None = None,
    videos_dir: Path = VIDEOS_DIR,
) -> dict:
    now = now or datetime.now(timezone.utc)
    latest = most_recent_upload_ts(videos_dir)
    if latest is None:
        return {"degraded": True, "reason": "no_uploads_found", "latest_upload": None, "hours_since": None}
    hours_since = (now - latest).total_seconds() / 3600.0
    degraded = hours_since > stale_hours
    return {
        "degraded": degraded,
        "reason": "stale" if degraded else "healthy",
        "latest_upload": latest.isoformat(),
        "hours_since": round(hours_since, 2),
        "stale_hours_threshold": stale_hours,
    }


def main() -> int:
    if os.environ.get("YOUTUBE_PUBLISHING_ENABLED", "") != "1":
        print(json.dumps({"degraded": False, "reason": "publishing_disabled"}, indent=2))
        return 0
    stale_hours = float(os.environ.get("PUBLISHING_STALE_HOURS", DEFAULT_STALE_HOURS))
    result = check(stale_hours=stale_hours, videos_dir=VIDEOS_DIR)
    print(json.dumps(result, indent=2))
    return 1 if result["degraded"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
