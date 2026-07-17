#!/usr/bin/env python3
"""End (transition to complete) any currently active/upcoming live broadcast.

One-off/manual admin tool. Used to cleanly take the 24/7 relay's YouTube
broadcast off the air on purpose -- e.g. right before a re-launch after an
update -- rather than just letting the GitHub Actions job stop and waiting
for YouTube to eventually notice the RTMP feed went quiet and end it on
its own.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upload_youtube import get_youtube_service  # noqa: E402

ACTIVE_STATUSES = {"live", "ready", "testing"}


def find_active_broadcast_ids(youtube) -> list[str]:
    response = (
        youtube.liveBroadcasts()
        .list(part="id,status", broadcastStatus="all", broadcastType="all", maxResults=50)
        .execute()
    )
    return [
        item["id"]
        for item in response.get("items", [])
        if (item.get("status") or {}).get("lifeCycleStatus") in ACTIVE_STATUSES
    ]


def end_broadcasts(youtube, broadcast_ids: list[str]) -> dict[str, bool]:
    results: dict[str, bool] = {}
    for broadcast_id in broadcast_ids:
        try:
            youtube.liveBroadcasts().transition(broadcastStatus="complete", id=broadcast_id, part="id,status").execute()
            results[broadcast_id] = True
        except Exception as exc:
            print(f"Failed to end {broadcast_id}: {exc}", file=sys.stderr)
            results[broadcast_id] = False
    return results


def main() -> int:
    youtube = get_youtube_service()
    broadcast_ids = find_active_broadcast_ids(youtube)
    if not broadcast_ids:
        print("No active/ready/testing broadcast found; nothing to end.")
        return 0
    results = end_broadcasts(youtube, broadcast_ids)
    for broadcast_id, ok in results.items():
        print(f"{broadcast_id}: {'ended' if ok else 'FAILED'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
