#!/usr/bin/env python3
"""Sync Pixabay anime/illustrated b-roll clips for the lofi Shorts/live pipeline.

Downloads real Pixabay video files (utils/broll.py, `video_type="animation"`)
matching a rotating set of anime-lofi-aesthetic queries -- the "Lofi Girl"
studying-loop look, not realistic photography. Pexels was the first source
tried here, but checked live it has no genuine illustrated/anime content:
"anime" searches there return cosplay footage and mistagged live-action, not
actual cartoon-style clips. Every clip keeps a sidecar JSON with the Pixabay
uploader name and clip URL, so a video description can credit the source if
we ever want to.

Mirrors scripts/sync_jamendo_music.py's on-disk library pattern: a capped
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

from utils.broll import BrollClip, download_clip, fetch_pixabay, looks_anime_styled  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("lofi_broll_sync")

BROLL_DIR = ROOT / "_assets" / "video" / "lofi_broll"
MAX_CLIPS = 12

LOFI_QUERIES = [
    "anime lofi girl study",
    "anime rain window cozy",
    "anime night city window",
    "anime study desk lamp",
    "anime cozy room fireplace",
    "anime cafe jazz",
    "anime bedroom plants morning",
    "anime cat sleeping cozy",
    "anime library reading",
    "anime snow window night",
    # Weighted toward the rainy-night/cozy sub-niche identity picked in
    # chat on 2026-07-19 (small channel, so competing on a broad "lofi"
    # search is unwinnable -- see rainy-night videos already using this
    # identity). Each variant's first two non-"anime" words match an
    # existing utils/lofi_branding.py mood key ("rain window"/"night
    # city"/"snow window") on purpose, so this only makes those moods get
    # picked more often -- it doesn't invent new untitled moods.
    "anime rain window thunderstorm",
    "anime night city rain",
    "anime snow window cozy",
    "anime rain window sleepy",
    # New visual settings (not weight-duplicates of an existing mood key)
    # added 2026-07-19 so the identity doesn't get visually repetitive as
    # the b-roll library turns over -- still on-theme (rain/night/cozy),
    # just a different scene. Fall back to a generated title/hook via
    # utils/lofi_branding.py's branded_title() default branch rather than
    # needing a new HOOK_BY_MOOD entry each time.
    "anime autumn rain window",
    "anime foggy morning window",
    "anime rooftop night rain",
    "anime train window rain",
]


# ANIME_STYLE_SIGNALS/looks_anime_styled now live in utils/broll.py so
# generate_lofi_short.py, generate_lofi_mix.py, and
# scripts/live_stream_dynamic.py can apply the same check again at
# selection time, not just here at download time (see utils/broll.py's
# is_on_brand_broll_clip docstring for why that second gate matters).
def _looks_anime_styled(clip: BrollClip) -> bool:
    return looks_anime_styled(str(clip.source_metadata.get("tags") or ""))


def _downloadable(clip: BrollClip, existing_ids: set[str]) -> bool:
    clip_id = str(clip.source_metadata.get("pixabay_video_id") or "")
    if not clip_id:
        return False
    if clip_id in existing_ids:
        return False
    if not _looks_anime_styled(clip):
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
    log.info("Downloaded clip %s (%s) by %s", clip_id, clip.title, clip.source_metadata.get("photographer", ""))
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
            log.info("Removed old clip %s to rotate library.", stale.name)
            existing_ids.discard(stale.stem.removeprefix("pixabay_"))

    queries = random.sample(LOFI_QUERIES, k=min(4, len(LOFI_QUERIES)))
    candidates: list[BrollClip] = []
    for query in queries:
        candidates.extend(fetch_pixabay(query, per_page=8))

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
        clip_id = str(clip.source_metadata["pixabay_video_id"])
        if clip_id in seen_this_run:
            continue
        seen_this_run.add(clip_id)
        if _download(clip):
            downloaded += 1
    log.info("Lofi b-roll sync complete: %d new clip(s).", downloaded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
