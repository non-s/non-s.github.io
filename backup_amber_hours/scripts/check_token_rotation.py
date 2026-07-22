#!/usr/bin/env python3
"""Remind the operator to periodically rotate the YOUTUBE_TOKEN secret.

Long-lived OAuth refresh tokens don't expire on their own, which is
exactly why they should still be rotated periodically -- nothing else in
this repo ever prompts for it. _data/security/token_rotation.json tracks
the last known rotation date; this script fails (non-zero exit) when
that date is missing or older than `rotate_after_days`, so it can be
wired into ops-alert.yml like any other monitored workflow.

`last_rotated` starts as null (never fabricate a real-looking date this
tool has no way to actually know) -- that's treated as overdue from day
one, same as an actually-stale rotation, so the first real run is
expected to fail until an operator runs this with --mark-rotated after
actually rotating the token in Google/GitHub.
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

STATE_PATH = ROOT / "_data" / "security" / "token_rotation.json"
DEFAULT_ROTATE_AFTER_DAYS = 180


def _load_state(path: Path = STATE_PATH) -> dict:
    if not path.exists():
        return {"last_rotated": None, "rotate_after_days": DEFAULT_ROTATE_AFTER_DAYS}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"last_rotated": None, "rotate_after_days": DEFAULT_ROTATE_AFTER_DAYS}
    if not isinstance(data, dict):
        return {"last_rotated": None, "rotate_after_days": DEFAULT_ROTATE_AFTER_DAYS}
    data.setdefault("last_rotated", None)
    data.setdefault("rotate_after_days", DEFAULT_ROTATE_AFTER_DAYS)
    return data


def check(*, now: datetime | None = None, path: Path = STATE_PATH) -> dict:
    now = now or datetime.now(timezone.utc)
    state = _load_state(path)
    last_rotated = state.get("last_rotated")
    rotate_after_days = int(state.get("rotate_after_days") or DEFAULT_ROTATE_AFTER_DAYS)

    if not last_rotated:
        return {"overdue": True, "reason": "never_recorded", "last_rotated": None, "days_since": None}

    try:
        stamp = datetime.fromisoformat(str(last_rotated).replace("Z", "+00:00"))
    except ValueError:
        return {"overdue": True, "reason": "unparseable_date", "last_rotated": last_rotated, "days_since": None}
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)

    days_since = (now - stamp).days
    overdue = days_since > rotate_after_days
    return {
        "overdue": overdue,
        "reason": "overdue" if overdue else "current",
        "last_rotated": last_rotated,
        "days_since": days_since,
        "rotate_after_days": rotate_after_days,
    }


def mark_rotated(*, now: datetime | None = None, path: Path = STATE_PATH) -> dict:
    """Record today as the last rotation date. Call this after actually
    rotating the token in Google/GitHub, not before."""
    now = now or datetime.now(timezone.utc)
    state = _load_state(path)
    state["last_rotated"] = now.isoformat()
    state.setdefault("rotate_after_days", DEFAULT_ROTATE_AFTER_DAYS)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mark-rotated", action="store_true", help="Record today as the last rotation date.")
    args = parser.parse_args()

    if args.mark_rotated:
        state = mark_rotated(path=STATE_PATH)
        print(json.dumps(state, indent=2))
        return 0

    result = check(path=STATE_PATH)
    print(json.dumps(result, indent=2))
    return 1 if result["overdue"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
