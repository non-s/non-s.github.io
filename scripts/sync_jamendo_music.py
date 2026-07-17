#!/usr/bin/env python3
"""Sync real Creative Commons ambient/lofi music from the Jamendo API.

Every downloaded track keeps a sidecar JSON with artist name, track name and
the exact Creative Commons license URL Jamendo reports for it, so a video
description can carry real, verifiable attribution -- CC-BY and CC-BY-SA
require it, and there is no way to know who to credit after the fact if we
only keep the MP3.

This used to shell out to yt-dlp and download the #1 hit for a generic
"No Copyright Music" YouTube search. That is not the same thing as a
verified Creative Commons track: YouTube does not check that an uploader
actually owns the rights to what they tagged, so a top search result can
carry someone else's unlicensed music. Calling Jamendo's API directly and
only keeping tracks it reports as ``audiodownload_allowed`` removes that
guesswork.
"""

from __future__ import annotations

import json
import logging
import random
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jamendo_sync")

# Jamendo's own publicly documented demo client id (developer.jamendo.com).
# Free tier, read-only track search -- no cost, no account needed to use it.
CLIENT_ID = "04ff30b1"
API_URL = "https://api.jamendo.com/v3.0/tracks/"
BGM_DIR = ROOT / "_assets" / "audio" / "bgm"
MAX_TRACKS = 10
REQUEST_TIMEOUT_S = 20

# fuzzytags = OR search: any of these ambient/chill/study moods qualify.
# jazz/lofi/chillhop/piano nudge results toward the jazz-influenced sound
# "lofi" usually means -- checked live against the Jamendo API: querying
# "lofi" or "chillhop" alone returns almost exclusively NC/ND-licensed
# tracks (not usable on a monetized channel), but folding those terms into
# this broader OR search as extra candidates -- rather than replacing the
# generic chillout/ambient terms with them -- measurably increased how many
# results came back plain CC-BY licensed (2/50 -> 6/50 in that check),
# since fuzzytags only ever widens the candidate pool.
MOOD_TAGS = "chillout+lounge+ambient+downtempo+instrumental+relax+meditation+jazz+lofi+chillhop+piano"


def _fetch_candidates(limit: int = 20) -> list[dict]:
    query = (
        f"{API_URL}?client_id={CLIENT_ID}&format=json&fuzzytags={MOOD_TAGS}"
        f"&include=licenses&audioformat=mp32&limit={limit}&order=popularity_month"
    )
    try:
        with urllib.request.urlopen(query, timeout=REQUEST_TIMEOUT_S) as response:
            payload = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        log.error("Jamendo search failed: %s", exc)
        return []
    if payload.get("headers", {}).get("status") != "success":
        log.error("Jamendo API error: %s", payload.get("headers", {}).get("error_message"))
        return []
    return payload.get("results") or []


def _commercially_safe(license_ccurl: str) -> bool:
    """Only plain Attribution (CC BY) clears a monetized channel.

    NonCommercial (NC) tracks explicitly forbid the use this channel makes
    of them -- monetized YouTube is commercial use by definition. NoDerivs
    (ND) and ShareAlike (SA) are excluded too: syncing a track to video is
    arguably a derivative under a strict reading, and SA would require the
    finished video itself to carry a matching CC license, which conflicts
    with normal YouTube distribution. CC BY has neither restriction.
    """
    return bool(re.search(r"creativecommons\.org/licenses/by/", license_ccurl or "", re.IGNORECASE))


def _downloadable(track: dict, existing_ids: set[str]) -> bool:
    if not track.get("audiodownload_allowed"):
        return False
    if not track.get("audiodownload"):
        return False
    if not _commercially_safe(str(track.get("license_ccurl") or "")):
        return False
    if str(track.get("id")) in existing_ids:
        return False
    return True


def _download_track(track: dict) -> bool:
    track_id = str(track["id"])
    audio_path = BGM_DIR / f"jamendo_{track_id}.mp3"
    meta_path = BGM_DIR / f"jamendo_{track_id}.json"
    try:
        urllib.request.urlretrieve(track["audiodownload"], audio_path)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        log.warning("Download failed for track %s: %s", track_id, exc)
        audio_path.unlink(missing_ok=True)
        return False
    meta_path.write_text(
        json.dumps(
            {
                "source": "jamendo",
                "track_id": track_id,
                "track_name": track.get("name", ""),
                "artist_name": track.get("artist_name", ""),
                "license_ccurl": track.get("license_ccurl", ""),
                "shareurl": track.get("shareurl", ""),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    log.info("Downloaded %s by %s (%s)", track.get("name"), track.get("artist_name"), track.get("license_ccurl"))
    return True


def main() -> int:
    BGM_DIR.mkdir(parents=True, exist_ok=True)

    existing_audio = list(BGM_DIR.glob("jamendo_*.mp3"))
    existing_ids = {p.stem.removeprefix("jamendo_") for p in existing_audio}
    if len(existing_audio) >= MAX_TRACKS:
        random.shuffle(existing_audio)
        for stale in existing_audio[:2]:
            stale.unlink(missing_ok=True)
            stale.with_suffix(".json").unlink(missing_ok=True)
            log.info("Removed old track %s to rotate library.", stale.name)
            existing_ids.discard(stale.stem.removeprefix("jamendo_"))

    candidates = [t for t in _fetch_candidates() if _downloadable(t, existing_ids)]
    if not candidates:
        log.warning("No new downloadable Jamendo tracks found this run.")
        return 0

    random.shuffle(candidates)
    downloaded = 0
    for track in candidates:
        if downloaded >= 2:
            break
        if _download_track(track):
            downloaded += 1
    log.info("Jamendo sync complete: %d new track(s).", downloaded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
