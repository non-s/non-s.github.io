"""Durable registry of YouTube video ids known to have been deleted.

A `.done` marker records that upload_youtube.py successfully published a
video once, but nothing kept that in sync if the video was later removed
from YouTube -- by a manual deletion, a copyright strike, or (before it
was fixed) the marker-resurrection concurrency race in youtube-bot.yml/
lofi-mix-daily.yml's "Salvar marcadores no git" step, which could bring
back a marker for a video that had already been correctly deleted.
scripts/rebrand_video_thumbnails.py used to hand-maintain a
`_KNOWN_DELETED_VIDEO_IDS` constant for the two ids found this way by
manual investigation; this module is the general version of that --
written by scripts/detect_orphan_videos.py once it confirms (via the
YouTube API) that a marker's video_id no longer exists, and read by any
script that walks `_videos/*.done` markers and needs to skip ones that no
longer point at a real video.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORPHAN_LOG_PATH = ROOT / "_data" / "orphaned_videos.jsonl"


def load_orphan_ids(path: Path = ORPHAN_LOG_PATH) -> set[str]:
    """video_ids logged as confirmed-deleted. Empty set if the log doesn't
    exist yet (nothing has ever been detected) -- never an error."""
    if not path.exists():
        return set()
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        video_id = str(row.get("video_id") or "")
        if video_id:
            ids.add(video_id)
    return ids


def append_orphans(rows: list[dict], path: Path = ORPHAN_LOG_PATH) -> None:
    """Append newly-detected orphan records. Append-only by design: this is
    a historical log, not a mutable table -- a script re-detecting the same
    id should dedupe against load_orphan_ids() before calling this, not
    rely on this function to skip duplicates."""
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
