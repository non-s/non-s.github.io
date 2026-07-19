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
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jamendo_sync")

CLIENT_ID = "04ff30b1"
API_URL = "https://api.jamendo.com/v3.0/tracks/"
BGM_DIR = ROOT / "_assets" / "audio" / "bgm"
MAX_TRACKS = 150
DOWNLOADS_PER_RUN = 20
REQUEST_TIMEOUT_S = 20
FETCH_RETRIES = 3
RETRY_DELAY_S = 2.0
FETCH_LIMIT = 200
OFFSET_POOL_SIZE = 2000  # how deep into the catalog a random offset can land

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

# Among the tracks that clear the license/download checks, prefer these
# genres so the library leans toward an actual lofi/jazz-influenced sound
# rather than generic corporate/ambient background music.
PREFERRED_GENRES = {"lofi", "jazz", "chillhop", "triphop", "downtempo", "jazzhop"}


def _fetch_candidates(limit: int = FETCH_LIMIT, offset: int = 0) -> list[dict]:
    """Search Jamendo, retrying on transient failure.

    Checked live: identical back-to-back requests with the same client id,
    query and limit returned results_count 50, 50, 0, 50, 50, 0 -- Jamendo's
    API itself is intermittently flaky (status "success" but an empty
    results list), independent of query size or caller. A short retry loop
    resolves it in practice; two failures in a row never happened across
    a dozen manual checks.

    No `order` param on purpose: `order=popularity_month` was checked live
    and silently caps the matching pool at ~200 tracks total (offset=200
    consistently returned 0 more, even after retries) -- the default
    ordering paginates through the full tagged catalog instead, confirmed
    live with offset=200/400 both returning full pages.
    """
    query = (
        f"{API_URL}?client_id={CLIENT_ID}&format=json&fuzzytags={MOOD_TAGS}"
        f"&include=licenses+musicinfo&audioformat=mp32&limit={limit}&offset={offset}"
    )
    for attempt in range(1, FETCH_RETRIES + 1):
        try:
            with urllib.request.urlopen(query, timeout=REQUEST_TIMEOUT_S) as response:
                payload = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            log.warning("Jamendo search attempt %d/%d failed: %s", attempt, FETCH_RETRIES, exc)
            time.sleep(RETRY_DELAY_S)
            continue
        if payload.get("headers", {}).get("status") != "success":
            log.warning(
                "Jamendo API attempt %d/%d error: %s",
                attempt,
                FETCH_RETRIES,
                payload.get("headers", {}).get("error_message"),
            )
            time.sleep(RETRY_DELAY_S)
            continue
        results = payload.get("results") or []
        if results:
            return results
        log.warning("Jamendo returned success with 0 results on attempt %d/%d; retrying.", attempt, FETCH_RETRIES)
        time.sleep(RETRY_DELAY_S)
    log.error("Jamendo search returned nothing after %d attempts.", FETCH_RETRIES)
    return []


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


def _genre_score(track: dict) -> int:
    genres = set((track.get("musicinfo") or {}).get("tags", {}).get("genres") or [])
    return 1 if genres & PREFERRED_GENRES else 0


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
    # Jamendo's own tempo classification for the track ("verylow"/"low"/
    # "medium"/"high"), checked live against the API -- lets
    # generate_lofi_short.py pair a track's energy with the b-roll clip's
    # visual mood (utils/lofi_branding.py's mood_energy()) instead of
    # picking bgm fully at random. Missing on ~5% of results in practice;
    # the picker falls back to the full library when nothing matches, so an
    # absent value here just opts that track out of the mood filter, not a
    # broken pipeline.
    speed = str((track.get("musicinfo") or {}).get("speed") or "")
    meta_path.write_text(
        json.dumps(
            {
                "source": "jamendo",
                "track_id": track_id,
                "track_name": track.get("name", ""),
                "artist_name": track.get("artist_name", ""),
                "license_ccurl": track.get("license_ccurl", ""),
                "shareurl": track.get("shareurl", ""),
                "speed": speed,
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
        # Genuinely oldest-first (by download mtime), not a random 2 --
        # picking randomly means a track downloaded on day one could
        # survive indefinitely by luck while a same-age peer gets evicted,
        # which isn't actually "rotating" the library toward fresher music
        # over time the way the log message here always claimed.
        existing_audio.sort(key=lambda p: p.stat().st_mtime)
        for stale in existing_audio[:2]:
            stale.unlink(missing_ok=True)
            stale.with_suffix(".json").unlink(missing_ok=True)
            log.info("Removed old track %s to rotate library.", stale.name)
            existing_ids.discard(stale.stem.removeprefix("jamendo_"))

    # The commercially-safe (plain CC BY) yield is low -- checked live,
    # roughly 2% of raw results -- so one 200-track page rarely has enough
    # new downloadable tracks on its own. Sampling a handful of random
    # offsets into the tagged catalog each run both widens the pool and
    # spreads discovery across the catalog instead of hammering the same
    # top page every time.
    raw: list[dict] = []
    seen_track_ids: set[str] = set()
    offsets = random.sample(range(0, OFFSET_POOL_SIZE, FETCH_LIMIT), k=5)
    for offset in offsets:
        for track in _fetch_candidates(offset=offset):
            track_id = str(track.get("id") or "")
            if track_id and track_id not in seen_track_ids:
                seen_track_ids.add(track_id)
                raw.append(track)

    candidates = [t for t in raw if _downloadable(t, existing_ids)]
    if not candidates:
        commercially_safe = sum(1 for t in raw if _commercially_safe(str(t.get("license_ccurl") or "")))
        log.warning(
            "No new downloadable Jamendo tracks found this run (raw=%d, commercially_safe=%d, already_owned=%d).",
            len(raw),
            commercially_safe,
            len(existing_ids),
        )
        return 0

    random.shuffle(candidates)
    candidates.sort(key=_genre_score, reverse=True)
    downloaded = 0
    for track in candidates:
        if downloaded >= DOWNLOADS_PER_RUN:
            break
        if _download_track(track):
            downloaded += 1
    log.info("Jamendo sync complete: %d new track(s).", downloaded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
