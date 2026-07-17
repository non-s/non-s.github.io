#!/usr/bin/env python3
"""Print the current active/upcoming live broadcast's real title/description.

One-off/manual, read-only admin tool. live_stream_dynamic.py's
_rebrand_if_stale() overwrites the broadcast's title/description back to
the hardcoded BROADCAST_TITLE/BROADCAST_DESCRIPTION constants whenever
they drift -- so after a manual edit in YouTube Studio, this is how to
see the real live value before deciding whether the code constants need
updating to match (otherwise the next monitor cycle reverts the edit).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upload_youtube import get_youtube_service  # noqa: E402

ACTIVE_STATUSES = {"live", "ready", "testing"}


def find_active_broadcasts(youtube) -> list[dict]:
    response = (
        youtube.liveBroadcasts()
        .list(part="id,snippet,status", broadcastStatus="all", broadcastType="all", maxResults=50)
        .execute()
    )
    return [
        item
        for item in response.get("items", [])
        if (item.get("status") or {}).get("lifeCycleStatus") in ACTIVE_STATUSES
    ]


def main() -> int:
    youtube = get_youtube_service()
    broadcasts = find_active_broadcasts(youtube)
    if not broadcasts:
        print("No active/ready/testing broadcast found.")
        return 0
    for item in broadcasts:
        snippet = item.get("snippet") or {}
        status = item.get("status") or {}
        print(
            json.dumps(
                {
                    "id": item.get("id"),
                    "lifeCycleStatus": status.get("lifeCycleStatus"),
                    "title": snippet.get("title"),
                    "description": snippet.get("description"),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
