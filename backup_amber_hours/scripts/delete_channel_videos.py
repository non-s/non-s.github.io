#!/usr/bin/env python3
"""Permanently delete specific videos from the channel by id.

One-off/manual admin tool. Deliberately requires explicit video ids as
CLI arguments -- no query, no "delete everything matching X" -- so this
can never run as an unattended pipeline step and accidentally delete the
wrong thing.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upload_youtube import get_youtube_service  # noqa: E402


def delete_videos(youtube, video_ids: list[str]) -> dict[str, bool]:
    results: dict[str, bool] = {}
    for video_id in video_ids:
        try:
            youtube.videos().delete(id=video_id).execute()
            results[video_id] = True
        except Exception as exc:
            print(f"Failed to delete {video_id}: {exc}", file=sys.stderr)
            results[video_id] = False
    return results


def main() -> int:
    video_ids = sys.argv[1:]
    if not video_ids:
        print("Usage: delete_channel_videos.py VIDEO_ID [VIDEO_ID ...]", file=sys.stderr)
        return 2

    youtube = get_youtube_service()
    results = delete_videos(youtube, video_ids)
    for video_id, ok in results.items():
        print(f"{video_id}: {'deleted' if ok else 'FAILED'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
