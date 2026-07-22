#!/usr/bin/env python3
"""Sync real Pixabay cute-animal b-roll clips for the cute-animal Shorts
pillar.

Mirrors the (now-removed) storm pillar's original sync_storm_broll.py
rotating-library pattern: downloads real Pixabay video files into a
capped pool in _assets/video/animal_broll, oldest rotated out once the
pool is full, so generate_cute_animal_short.py can pick a random real
clip already on disk instead of hitting the network per render. Unlike
the storm/rain pillar (which settled on 3 fixed pinned clips for a calm,
always-the-same-scene vibe), this pillar deliberately keeps the rotating
pool: variety across different animals is the whole appeal of
cute-animal content, not a consistent single scene.
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
    ANIMAL_RELEVANCE_SIGNALS,
    BrollClip,
    download_clip,
    score_relevance,
    search_pixabay,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("animal_broll_sync")

BROLL_DIR = ROOT / "_assets" / "video" / "animal_broll"
MAX_CLIPS = 24  # bigger than the storm pillar's 16: variety across many
# different animals is the point here, not one consistent scene.

# Real search queries a Pixabay "film" (not "animation") search actually
# returns cute-animal footage for -- deliberately spread across several
# animals so the pool doesn't lean entirely cat or entirely dog.
ANIMAL_QUERIES = (
    "cute cat",
    "kitten playing",
    "cute puppy",
    "dog playing",
    "cute bunny",
    "cute hamster",
    "adorable animal",
    "funny cat",
    "playful kitten",
    "sleeping puppy",
    "cute rabbit",
    "baby animals",
    "fluffy cat",
    "dog and cat friends",
    "tiny hamster",
)


def _looks_animal_relevant(clip: BrollClip) -> bool:
    return score_relevance(str(clip.source_metadata.get("tags") or ""), ANIMAL_RELEVANCE_SIGNALS) >= 1


def _downloadable(clip: BrollClip, existing_ids: set[str]) -> bool:
    clip_id = str(clip.source_metadata.get("pixabay_video_id") or "")
    if not clip_id:
        return False
    if clip_id in existing_ids:
        return False
    if not _looks_animal_relevant(clip):
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
    log.info("Downloaded animal clip %s (%s) by %s", clip_id, clip.title, clip.source_metadata.get("photographer", ""))
    return True


def main() -> int:
    BROLL_DIR.mkdir(parents=True, exist_ok=True)

    existing_videos = list(BROLL_DIR.glob("pixabay_*.mp4"))
    existing_ids = {p.stem.removeprefix("pixabay_") for p in existing_videos}
    if len(existing_videos) >= MAX_CLIPS:
        existing_videos.sort(key=lambda p: p.stat().st_mtime)
        for stale in existing_videos[:3]:
            stale.unlink(missing_ok=True)
            stale.with_suffix(".json").unlink(missing_ok=True)
            log.info("Removed old animal clip %s to rotate library.", stale.name)
            existing_ids.discard(stale.stem.removeprefix("pixabay_"))

    queries = random.sample(ANIMAL_QUERIES, k=min(4, len(ANIMAL_QUERIES)))
    candidates = search_pixabay(
        queries,
        per_page=8,
        pages=2,
        video_type="film",
        signals=ANIMAL_RELEVANCE_SIGNALS,
        min_score=1,
    )

    downloadable = [clip for clip in candidates if _downloadable(clip, existing_ids)]
    if not downloadable:
        log.warning("No new downloadable animal b-roll clips found this run.")
        return 0

    downloaded = 0
    seen_this_run: set[str] = set()
    for clip in downloadable:
        if downloaded >= 3:
            break
        clip_id = str(clip.source_metadata["pixabay_video_id"])
        if clip_id in seen_this_run:
            continue
        seen_this_run.add(clip_id)
        if _download(clip):
            downloaded += 1
    log.info("Animal b-roll sync complete: %d new clip(s).", downloaded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
