#!/usr/bin/env python3
"""Delete a single video from the channel by ID. Manual operator tool.

Usage: python scripts/delete_video.py VIDEO_ID [VIDEO_ID ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upload_youtube import get_youtube_service


def main() -> int:
    video_ids = [v.strip() for v in sys.argv[1:] if v.strip()]
    if not video_ids:
        print("Usage: python scripts/delete_video.py VIDEO_ID [VIDEO_ID ...]")
        return 1

    youtube = get_youtube_service()
    exit_code = 0
    for video_id in video_ids:
        try:
            youtube.videos().delete(id=video_id).execute()
            print(f"Deleted video {video_id}")
        except Exception as exc:
            print(f"Failed to delete video {video_id}: {exc}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
