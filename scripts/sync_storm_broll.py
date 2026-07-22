#!/usr/bin/env python3
"""Sync real Pixabay rain/storm b-roll clips for the storm ambience pillar.

Mirrors scripts/sync_lofi_broll.py's on-disk rotating-library pattern
exactly, just with `video_type="film"` (real-world footage, see
utils.broll.fetch_pixabay's docstring for the "film" vs "animation"
distinction) and storm/rain search queries instead of anime-lofi ones:
downloads real Pixabay video files into a capped pool in
_assets/video/storm_broll, oldest rotated out once the pool is full, so
generate_storm_ambience.py / generate_storm_short.py can pick a random
real clip already on disk instead of hitting the network per render --
falling back to the illustrated pinned_storm_clip.mp4 whenever the pool
is empty (no PIXABAY_API_KEY configured, or this sync hasn't run yet).
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

from scripts.search_storm_broll_candidates import DEFAULT_QUERIES as STORM_QUERIES  # noqa: E402
from utils.broll import BrollClip, download_clip, fetch_pixabay, looks_storm_relevant  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("storm_broll_sync")

BROLL_DIR = ROOT / "_assets" / "video" / "storm_broll"
MAX_CLIPS = 16


def _looks_storm_relevant(clip: BrollClip) -> bool:
    return looks_storm_relevant(str(clip.source_metadata.get("tags") or ""))


def _downloadable(clip: BrollClip, existing_ids: set[str]) -> bool:
    clip_id = str(clip.source_metadata.get("pixabay_video_id") or "")
    if not clip_id:
        return False
    if clip_id in existing_ids:
        return False
    if not _looks_storm_relevant(clip):
        return False
    return True


def _download(clip: BrollClip) -> bool:
    clip_id = str(clip.source_metadata["pixabay_video_id"])
    video_path = BROLL_DIR / f"pixabay_{clip_id}.mp4"
    meta_path = BROLL_DIR / f"pixabay_{clip_id}.json"
    if not download_clip(clip, video_path):
        return False
    meta_path.write_text(
        json.dumps(
            {
                "source": "pixabay",
                "pixabay_video_id": clip_id,
                "title": clip.title,
                "license": clip.license,
                "license_evidence": clip.license_evidence,
                "photographer": clip.source_metadata.get("photographer", ""),
                "photographer_url": clip.source_metadata.get("photographer_url", ""),
                "query": clip.source_metadata.get("pixabay_query", ""),
                "is_ai_generated": clip.source_metadata.get("is_ai_generated", False),
                "tags": clip.source_metadata.get("tags", ""),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    log.info("Downloaded storm clip %s (%s) by %s", clip_id, clip.title, clip.source_metadata.get("photographer", ""))
    return True


def main() -> int:
    BROLL_DIR.mkdir(parents=True, exist_ok=True)

    existing_videos = list(BROLL_DIR.glob("pixabay_*.mp4"))
    existing_ids = {p.stem.removeprefix("pixabay_") for p in existing_videos}
    if len(existing_videos) >= MAX_CLIPS:
        random.shuffle(existing_videos)
        for stale in existing_videos[:2]:
            stale.unlink(missing_ok=True)
            stale.with_suffix(".json").unlink(missing_ok=True)
            log.info("Removed old storm clip %s to rotate library.", stale.name)
            existing_ids.discard(stale.stem.removeprefix("pixabay_"))

    queries = random.sample(STORM_QUERIES, k=min(3, len(STORM_QUERIES)))
    candidates: list[BrollClip] = []
    for query in queries:
        candidates.extend(fetch_pixabay(query, per_page=8, video_type="film"))

    downloadable = [clip for clip in candidates if _downloadable(clip, existing_ids)]
    if not downloadable:
        log.warning("No new downloadable storm b-roll clips found this run.")
        return 0

    random.shuffle(downloadable)
    downloaded = 0
    seen_this_run: set[str] = set()
    for clip in downloadable:
        if downloaded >= 2:
            break
        clip_id = str(clip.source_metadata["pixabay_video_id"])
        if clip_id in seen_this_run:
            continue
        seen_this_run.add(clip_id)
        if _download(clip):
            downloaded += 1
    log.info("Storm b-roll sync complete: %d new clip(s).", downloaded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
