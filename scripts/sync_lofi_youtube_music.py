#!/usr/bin/env python3
"""Sync real Creative Commons lofi/ambient music from YouTube via yt-dlp.

Searches YouTube's own "Creative Commons" filter (Filters > Features >
Creative Commons in the UI, `sp=EgIwAQ%3D%3D` in the search URL) for lofi/
ambient/chill mood queries, and only keeps videos where yt-dlp's extracted
`license` field is exactly YouTube's Creative Commons Attribution string.

This is a materially different check than matching "creative commons" in a
video's title or description: plenty of uploaders write that in the title
without ever setting YouTube's actual license field, and a plain
`ytsearch:` for those titles turns up almost entirely videos with no real
license metadata at all (checked live: 0/5 had `license` set). The CC
search filter only returns videos the uploader explicitly tagged through
YouTube Studio's license setting, and every result from it in testing had
the license field populated -- this script still checks it per-video
before downloading, since the search filter is YouTube's word for it, not
independently verified, same caveat as any self-declared CC license.

CC BY requires attribution, so every download keeps a sidecar JSON with
the title, channel, video URL and license string.
"""

from __future__ import annotations

import json
import logging
import random
import sys
from pathlib import Path
from urllib.parse import quote

import yt_dlp

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("youtube_cc_music_sync")

BGM_DIR = ROOT / "_assets" / "audio" / "bgm"
MAX_TRACKS = 10
SEARCH_LIMIT = 6
MIN_DURATION_S = 60
MAX_DURATION_S = 1200  # skip multi-hour mixes; this is one rotating track, not the whole loop

REQUIRED_LICENSE = "Creative Commons Attribution license (reuse allowed)"
CC_FILTER_PARAM = "EgIwAQ%3D%3D"

MOOD_QUERIES = [
    "lofi ambient relaxing music",
    "lofi jazz chill beats",
    "lofi rain study music",
    "lofi piano calm ambient",
    "lofi sleep ambient music",
    "chillhop instrumental relax",
    "lofi cafe jazz ambient",
    "lofi nature calm music",
]


def _search_candidates(query: str, limit: int = SEARCH_LIMIT) -> list[dict]:
    search_url = f"https://www.youtube.com/results?search_query={quote(query)}&sp={CC_FILTER_PARAM}"
    opts = {"quiet": True, "no_warnings": True, "playlistend": limit}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
    except Exception as exc:
        log.warning("Search failed for %r: %s", query, exc)
        return []
    entries = (info or {}).get("entries") or []
    return [entry for entry in entries if entry]


def _eligible(entry: dict, existing_ids: set[str]) -> bool:
    video_id = str(entry.get("id") or "")
    if not video_id or video_id in existing_ids:
        return False
    if entry.get("license") != REQUIRED_LICENSE:
        return False
    if entry.get("is_live"):
        return False
    duration = entry.get("duration")
    if not duration or duration < MIN_DURATION_S or duration > MAX_DURATION_S:
        return False
    return True


def _download_track(entry: dict) -> bool:
    video_id = str(entry["id"])
    audio_path = BGM_DIR / f"ytcc_{video_id}.mp3"
    meta_path = BGM_DIR / f"ytcc_{video_id}.json"
    opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "outtmpl": str(BGM_DIR / f"ytcc_{video_id}.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "5"}],
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    except Exception as exc:
        log.warning("Download failed for %s: %s", video_id, exc)
        audio_path.unlink(missing_ok=True)
        return False
    if not audio_path.exists():
        log.warning("Download reported success but %s is missing.", audio_path.name)
        return False
    meta_path.write_text(
        json.dumps(
            {
                "source": "youtube_cc",
                "video_id": video_id,
                "track_name": entry.get("title", ""),
                "artist_name": entry.get("uploader") or entry.get("channel") or "",
                "license_ccurl": REQUIRED_LICENSE,
                "shareurl": f"https://www.youtube.com/watch?v={video_id}",
                "track_id": video_id,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    log.info("Downloaded %s by %s (%s)", entry.get("title"), entry.get("uploader"), video_id)
    return True


def main() -> int:
    BGM_DIR.mkdir(parents=True, exist_ok=True)

    existing_audio = list(BGM_DIR.glob("ytcc_*.mp3"))
    existing_ids = {p.stem.removeprefix("ytcc_") for p in existing_audio}
    if len(existing_audio) >= MAX_TRACKS:
        random.shuffle(existing_audio)
        for stale in existing_audio[:2]:
            stale.unlink(missing_ok=True)
            stale.with_suffix(".json").unlink(missing_ok=True)
            log.info("Removed old track %s to rotate library.", stale.name)
            existing_ids.discard(stale.stem.removeprefix("ytcc_"))

    queries = random.sample(MOOD_QUERIES, k=min(3, len(MOOD_QUERIES)))
    candidates: list[dict] = []
    for query in queries:
        candidates.extend(_search_candidates(query))

    eligible = [entry for entry in candidates if _eligible(entry, existing_ids)]
    if not eligible:
        log.warning("No new eligible Creative Commons tracks found this run.")
        return 0

    random.shuffle(eligible)
    downloaded = 0
    seen_this_run: set[str] = set()
    for entry in eligible:
        if downloaded >= 2:
            break
        video_id = str(entry["id"])
        if video_id in seen_this_run:
            continue
        seen_this_run.add(video_id)
        if _download_track(entry):
            downloaded += 1
    log.info("YouTube CC music sync complete: %d new track(s).", downloaded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
