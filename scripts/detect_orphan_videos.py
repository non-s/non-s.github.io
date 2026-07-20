#!/usr/bin/env python3
"""Detect .done markers whose video_id no longer exists on YouTube.

Checks every marker's video_id against the real YouTube API (videos.list,
batched up to 50 ids per call to keep this quota-cheap) and logs any that
come back missing to utils.orphan_registry's durable, append-only log --
see that module's docstring for the concurrency-race/manual-deletion
background. scripts/rebrand_video_thumbnails.py (and anything else that
walks _videos/*.done) reads that log to skip ids no longer worth trying
to act on, instead of accumulating a hand-maintained constant every time
one is found.

Read-only against YouTube itself (only ever calls videos.list) -- the
only side effect is the registry file, which the caller (an admin
workflow) commits like any other _data/ state file.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upload_youtube import get_youtube_service  # noqa: E402
from utils import orphan_registry  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("detect_orphan_videos")

VIDEOS_DIR = ROOT / "_videos"
BATCH_SIZE = 50  # videos.list's max ids per request


def _marker_video_ids(videos_dir: Path = VIDEOS_DIR) -> dict[str, Path]:
    """video_id -> its .done marker path, for every marker that has one."""
    ids: dict[str, Path] = {}
    for path in sorted(videos_dir.glob("*.done")):
        try:
            marker = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        video_id = str(marker.get("video_id") or "")
        if video_id:
            ids[video_id] = path
    return ids


def _existing_video_ids(youtube, video_ids: list[str]) -> set[str]:
    """Which of these ids YouTube still reports as existing."""
    existing: set[str] = set()
    for i in range(0, len(video_ids), BATCH_SIZE):
        batch = video_ids[i : i + BATCH_SIZE]
        response = youtube.videos().list(part="status", id=",".join(batch)).execute()
        for item in response.get("items", []):
            existing.add(str(item.get("id") or ""))
    return existing


def find_orphans(youtube, videos_dir: Path = VIDEOS_DIR, already_known: set[str] | None = None) -> list[dict]:
    """Marker video_ids that exist locally but not on YouTube, excluding
    ones already in the registry. Doesn't touch the registry file."""
    already_known = already_known or set()
    marker_ids = _marker_video_ids(videos_dir)
    candidates = [vid for vid in marker_ids if vid not in already_known]
    if not candidates:
        return []
    existing = _existing_video_ids(youtube, candidates)
    now = datetime.now(timezone.utc).isoformat()
    orphans = []
    for video_id in candidates:
        if video_id in existing:
            continue
        marker_path = marker_ids[video_id]
        title = ""
        try:
            title = json.loads(marker_path.read_text(encoding="utf-8")).get("title", "")
        except Exception:
            pass
        orphans.append(
            {
                "video_id": video_id,
                "marker": marker_path.name,
                "title": title,
                "detected_at": now,
            }
        )
    return orphans


def main() -> int:
    youtube = get_youtube_service()
    # Read via the module (not a directly-imported function reference) so
    # a caller that points orphan_registry.ORPHAN_LOG_PATH elsewhere (e.g.
    # a test) is actually honored -- a bound default parameter value is
    # fixed at function-definition time, before any such override happens.
    known = orphan_registry.load_orphan_ids(orphan_registry.ORPHAN_LOG_PATH)
    orphans = find_orphans(youtube, videos_dir=VIDEOS_DIR, already_known=known)

    if not orphans:
        log.info("No new orphaned markers found (%d already known).", len(known))
        return 0

    orphan_registry.append_orphans(orphans, orphan_registry.ORPHAN_LOG_PATH)
    for row in orphans:
        log.warning("Orphaned marker detected: %s (%r) -> %s", row["video_id"], row["title"], row["marker"])
    log.info("Logged %d newly-detected orphaned marker(s).", len(orphans))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
