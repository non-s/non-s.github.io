#!/usr/bin/env python3
"""Sync Pexels b-roll clips for the lofi Shorts/live pipeline.

Downloads real Pexels video files (utils/broll.py -- same free,
no-attribution-required commercial license Wild Brief already relies on for
nature b-roll) matching a rotating set of lofi-aesthetic queries: rain
windows, cozy rooms, fireplaces, night cities, study desks. Every clip keeps
a sidecar JSON with the Pexels photographer name and clip URL, so a video
description can credit the source if we ever want to.

Mirrors scripts/sync_lofi_youtube_music.py's on-disk library pattern: a capped
pool of files in _assets/video/lofi_broll, oldest rotated out once the pool
is full, so the Shorts generator can just pick a random clip already on
disk instead of hitting the network per render.
"""

from __future__ import annotations

import json
import logging
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.broll import BrollClip, download_clip, fetch_broll_clips  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("lofi_broll_sync")

BROLL_DIR = ROOT / "_assets" / "video" / "lofi_broll"
MAX_CLIPS = 12

LOFI_QUERIES = [
    "rain window cozy",
    "fireplace night cozy room",
    "coffee cup steam desk",
    "night city lights window",
    "study desk lamp night",
    "snow falling window cozy",
    "candle warm room night",
    "ocean waves night calm",
    "bedroom plants sunlight morning",
    "cat sleeping cozy blanket",
]


def _downloadable(clip: BrollClip, existing_ids: set[str]) -> bool:
    clip_id = str(clip.source_metadata.get("pexels_video_id") or "")
    if not clip_id:
        return False
    if clip_id in existing_ids:
        return False
    return True


def _download(clip: BrollClip) -> bool:
    clip_id = str(clip.source_metadata["pexels_video_id"])
    video_path = BROLL_DIR / f"pexels_{clip_id}.mp4"
    meta_path = BROLL_DIR / f"pexels_{clip_id}.json"
    if not download_clip(clip, video_path):
        return False
    meta_path.write_text(
        json.dumps(
            {
                "source": "pexels",
                "pexels_video_id": clip_id,
                "title": clip.title,
                "license": clip.license,
                "license_evidence": clip.license_evidence,
                "photographer": clip.source_metadata.get("photographer", ""),
                "photographer_url": clip.source_metadata.get("photographer_url", ""),
                "query": clip.source_metadata.get("pexels_query", ""),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    log.info("Downloaded clip %s (%s) by %s", clip_id, clip.title, clip.source_metadata.get("photographer", ""))
    return True


def main() -> int:
    BROLL_DIR.mkdir(parents=True, exist_ok=True)

    existing_videos = list(BROLL_DIR.glob("pexels_*.mp4"))
    existing_ids = {p.stem.removeprefix("pexels_") for p in existing_videos}
    if len(existing_videos) >= MAX_CLIPS:
        random.shuffle(existing_videos)
        for stale in existing_videos[:2]:
            stale.unlink(missing_ok=True)
            stale.with_suffix(".json").unlink(missing_ok=True)
            log.info("Removed old clip %s to rotate library.", stale.name)
            existing_ids.discard(stale.stem.removeprefix("pexels_"))

    queries = random.sample(LOFI_QUERIES, k=min(4, len(LOFI_QUERIES)))
    candidates: list[BrollClip] = []
    for query in queries:
        candidates.extend(fetch_broll_clips(query, want_n=4, orientation="portrait"))

    downloadable = [clip for clip in candidates if _downloadable(clip, existing_ids)]
    if not downloadable:
        log.warning("No new downloadable lofi b-roll clips found this run.")
        return 0

    random.shuffle(downloadable)
    downloaded = 0
    seen_this_run: set[str] = set()
    for clip in downloadable:
        if downloaded >= 2:
            break
        clip_id = str(clip.source_metadata["pexels_video_id"])
        if clip_id in seen_this_run:
            continue
        seen_this_run.add(clip_id)
        if _download(clip):
            downloaded += 1
    log.info("Lofi b-roll sync complete: %d new clip(s).", downloaded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
