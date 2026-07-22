#!/usr/bin/env python3
"""Sync real Pixabay calm-nursery/night b-roll clips for the baby
white/brown-noise ambience pillar.

Rotating-pool pattern (same shape as scripts/sync_animal_broll.py, the
freshest sibling example): downloads real Pixabay video files into a
capped pool in _assets/video/noise_broll, oldest rotated out once the
pool is full. Unlike the rain pillar's 3 fixed hand-picked clips, no one
was available to manually review and pin specific clips for this pillar
tonight -- rotation is a stand-in for that, not a deliberate design
choice the way it is for scripts/sync_animal_broll.py (where variety is
the actual appeal). The channel owner can convert this pillar to fixed
pinned clips later the same way they did for the rain pillar, if they
prefer a single consistent scene once they've reviewed real candidates
by hand.
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

from utils.broll import (  # noqa: E402
    NOISE_RELEVANCE_SIGNALS,
    BrollClip,
    download_clip,
    score_relevance,
    search_pixabay,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("noise_broll_sync")

BROLL_DIR = ROOT / "_assets" / "video" / "noise_broll"
MAX_CLIPS = 16  # same size as the storm pillar's original rotating pool

# Real search queries a Pixabay "film" search actually returns calm,
# non-distracting nursery/night footage for -- nothing bright or busy, a
# 2am dimmed-phone-screen-in-a-baby's-room viewing context.
NOISE_QUERIES = (
    "baby sleeping",
    "nursery night",
    "night sky stars",
    "soft candle light",
    "cozy blanket",
    "night light room",
    "baby crib",
    "starry sky slow motion",
    "moonlight room",
    "calm night lamp",
    "sleeping baby close up",
    "dim light nursery",
    "gentle night sky",
    "warm blanket bed",
    "peaceful bedroom night",
)


def _looks_noise_relevant(clip: BrollClip) -> bool:
    return score_relevance(str(clip.source_metadata.get("tags") or ""), NOISE_RELEVANCE_SIGNALS) >= 1


def _downloadable(clip: BrollClip, existing_ids: set[str]) -> bool:
    clip_id = str(clip.source_metadata.get("pixabay_video_id") or "")
    if not clip_id:
        return False
    if clip_id in existing_ids:
        return False
    if not _looks_noise_relevant(clip):
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
    log.info(
        "Downloaded noise-pillar clip %s (%s) by %s", clip_id, clip.title, clip.source_metadata.get("photographer", "")
    )
    return True


def main() -> int:
    BROLL_DIR.mkdir(parents=True, exist_ok=True)

    existing_videos = list(BROLL_DIR.glob("pixabay_*.mp4"))
    existing_ids = {p.stem.removeprefix("pixabay_") for p in existing_videos}
    if len(existing_videos) >= MAX_CLIPS:
        existing_videos.sort(key=lambda p: p.stat().st_mtime)
        for stale in existing_videos[:2]:
            stale.unlink(missing_ok=True)
            stale.with_suffix(".json").unlink(missing_ok=True)
            log.info("Removed old noise-pillar clip %s to rotate library.", stale.name)
            existing_ids.discard(stale.stem.removeprefix("pixabay_"))

    queries = random.sample(NOISE_QUERIES, k=min(4, len(NOISE_QUERIES)))
    candidates = search_pixabay(
        queries,
        per_page=8,
        pages=2,
        video_type="film",
        signals=NOISE_RELEVANCE_SIGNALS,
        min_score=1,
    )

    downloadable = [clip for clip in candidates if _downloadable(clip, existing_ids)]
    if not downloadable:
        log.warning("No new downloadable noise-pillar b-roll clips found this run.")
        return 0

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
    log.info("Noise-pillar b-roll sync complete: %d new clip(s).", downloaded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
