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
    """Transition each broadcast to complete, falling back to an outright
    delete when YouTube rejects the transition.

    Checked live: a broadcast stuck in "ready" (bound to a stream key but
    that never actually received valid data, e.g. after an ffmpeg
    misconfiguration) has no "live" state to complete from -- the
    transition API call fails with reason "invalidTransition". Deleting
    it outright is the only way to clear that broadcast so a fresh one
    can take its place.
    """
    results: dict[str, bool] = {}
    for broadcast_id in broadcast_ids:
        try:
            youtube.liveBroadcasts().transition(broadcastStatus="complete", id=broadcast_id, part="id,status").execute()
            results[broadcast_id] = True
            continue
        except Exception as exc:
            transition_error = exc
        try:
            youtube.liveBroadcasts().delete(id=broadcast_id).execute()
            results[broadcast_id] = True
        except Exception as delete_exc:
            print(f"Failed to end {broadcast_id}: {transition_error}", file=sys.stderr)
            print(f"Failed to delete {broadcast_id} as fallback: {delete_exc}", file=sys.stderr)
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
