#!/usr/bin/env python3
"""List every video currently on the channel, with id/title/publishedAt.

One-off/manual admin tool: real ground truth for "what's actually live on
the channel right now" is the channel itself, not any locally cached
snapshot or git history of _videos/*.done markers -- both can be stale
relative to videos deleted or added outside this pipeline (e.g. a manual
reset done directly in YouTube Studio).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upload_youtube import _fetch_recent_channel_uploads, get_youtube_service  # noqa: E402


def _attach_statistics(youtube, uploads: list[dict]) -> None:
    """In-place: merge view/like/comment counts onto each upload dict.

    playlistItems (what _fetch_recent_channel_uploads uses) never carries
    statistics -- only videos.list does -- so this is a second pass,
    batched at the API's 50-id-per-call max to keep quota cost trivial
    (~1 unit/call) against the 200-video default limit above.
    """
    ids = [str(u.get("video_id") or "") for u in uploads if u.get("video_id")]
    stats_by_id: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        batch = ids[i : i + 50]
        response = youtube.videos().list(part="statistics", id=",".join(batch)).execute()
        for item in response.get("items", []) or []:
            stats_by_id[item.get("id")] = item.get("statistics") or {}
    for upload in uploads:
        stats = stats_by_id.get(str(upload.get("video_id") or ""), {})
        upload["view_count"] = int(stats.get("viewCount", 0) or 0)
        upload["like_count"] = int(stats.get("likeCount", 0) or 0)
        upload["comment_count"] = int(stats.get("commentCount", 0) or 0)


def main() -> int:
    youtube = get_youtube_service()
    uploads = _fetch_recent_channel_uploads(youtube, limit=200)
    _attach_statistics(youtube, uploads)
    print(json.dumps(uploads, indent=2, ensure_ascii=False))
    print(f"\ntotal: {len(uploads)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
