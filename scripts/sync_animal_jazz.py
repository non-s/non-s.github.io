#!/usr/bin/env python3
"""Sync real, commercially-safe jazz tracks from the Jamendo API for the
cute-animal Shorts pillar.

Unlike the (removed) rain-pillar Jamendo experiment -- which tried to use
Jamendo as a source of "rain sound" and found the catalog is music, not
sound effects, so it never delivered real rain -- jazz is an actual music
genre Jamendo has genuine jazz tracks for, so this is a legitimate fit,
not a repeat of that mistake.

Same license-safety check the removed scripts/sync_jamendo_music.py used
(re-derived from git history, `_commercially_safe()` below): only plain
Attribution (CC BY) tracks clear a monetized channel -- NonCommercial (NC)
tracks explicitly forbid the use this channel makes of them, and
NoDerivs/ShareAlike (ND/SA) are excluded for the same reasons that script
documented. Checked live against the Jamendo API, 2026-07-22: a narrow
`fuzzytags=jazz` search returned 0 commercially-safe results out of 200;
a broader OR search (`jazz+lounge+swing+chillout+cafe+relax`) returned a
handful (roughly 1.5-2% of raw results) -- thin, same order of magnitude
as the old lofi pillar's yield, so this library grows slowly and repeats
early on. Only tracks whose own musicinfo.genres actually includes a
jazz-family genre are kept (see PREFERRED_JAZZ_GENRES) -- the broader
fuzzytags net widens the candidate pool searched, it does not relax what
counts as "actually jazz."
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

from utils import jamendo_cache  # noqa: E402
from utils.circuit_breaker import CircuitBreaker  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("animal_jazz_sync")

CLIENT_ID = "04ff30b1"
API_URL = "https://api.jamendo.com/v3.0/tracks/"
JAZZ_DIR = ROOT / "_assets" / "audio" / "animal_jazz"
MAX_TRACKS = 100
DOWNLOADS_PER_RUN = 10
REQUEST_TIMEOUT_S = 20
FETCH_RETRIES = 3
RETRY_DELAY_S = 2.0
FETCH_LIMIT = 200
OFFSET_POOL_SIZE = 2000

# fuzzytags = OR search: widening the net with generic lounge/cafe/relax
# terms (not just "jazz") measurably increases the commercially-safe
# yield, same technique the old lofi sync used -- see module docstring.
MOOD_TAGS = "jazz+swing+bossanova+bigband+bebop+smoothjazz+lounge+chillout+cafe+relax"

# Only tracks actually tagged with one of these genres count as "jazz" for
# this pillar -- the broader MOOD_TAGS search above is just to widen the
# candidate pool, not to relax what counts as on-brand.
PREFERRED_JAZZ_GENRES = {"jazz", "swing", "bigband", "bebop", "smoothjazz", "jazzhop", "freejazz", "fusionjazz"}


def _fetch_candidates_ex(tags: str = MOOD_TAGS, limit: int = FETCH_LIMIT, offset: int = 0) -> tuple[list[dict], bool]:
    """Same shape as the removed sync_jamendo_music.py's identical
    helper -- see its docstring for the retry/circuit-breaker reasoning,
    preserved here since the underlying Jamendo API flakiness is
    unrelated to which tags/pillar is searching."""
    query = (
        f"{API_URL}?client_id={CLIENT_ID}&format=json&fuzzytags={tags}"
        f"&include=licenses+musicinfo&audioformat=mp32&limit={limit}&offset={offset}"
    )
    hard_failure = False
    for attempt in range(1, FETCH_RETRIES + 1):
        try:
            with urllib.request.urlopen(query, timeout=REQUEST_TIMEOUT_S) as response:
                payload = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            log.warning("Jamendo search attempt %d/%d failed: %s", attempt, FETCH_RETRIES, exc)
            hard_failure = True
            time.sleep(RETRY_DELAY_S)
            continue
        if payload.get("headers", {}).get("status") != "success":
            log.warning(
                "Jamendo API attempt %d/%d error: %s",
                attempt,
                FETCH_RETRIES,
                payload.get("headers", {}).get("error_message"),
            )
            hard_failure = True
            time.sleep(RETRY_DELAY_S)
            continue
        results = payload.get("results") or []
        if results:
            return results, False
        log.warning("Jamendo returned success with 0 results on attempt %d/%d; retrying.", attempt, FETCH_RETRIES)
        time.sleep(RETRY_DELAY_S)
    log.error("Jamendo search returned nothing after %d attempts.", FETCH_RETRIES)
    return [], hard_failure


def _commercially_safe(license_ccurl: str) -> bool:
    """Only plain Attribution (CC BY) clears a monetized channel -- see
    module docstring."""
    return bool(re.search(r"creativecommons\.org/licenses/by/", license_ccurl or "", re.IGNORECASE))


def _is_jazz_genre(track: dict) -> bool:
    genres = set((track.get("musicinfo") or {}).get("tags", {}).get("genres") or [])
    return bool(genres & PREFERRED_JAZZ_GENRES)


def _downloadable(track: dict, existing_ids: set[str]) -> bool:
    if not track.get("audiodownload_allowed"):
        return False
    if not track.get("audiodownload"):
        return False
    if not _commercially_safe(str(track.get("license_ccurl") or "")):
        return False
    if not _is_jazz_genre(track):
        return False
    if str(track.get("id")) in existing_ids:
        return False
    return True


def _download_track(track: dict) -> bool:
    track_id = str(track["id"])
    audio_path = JAZZ_DIR / f"jamendo_{track_id}.mp3"
    meta_path = JAZZ_DIR / f"jamendo_{track_id}.json"
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
    JAZZ_DIR.mkdir(parents=True, exist_ok=True)

    existing_audio = list(JAZZ_DIR.glob("jamendo_*.mp3"))
    existing_ids = {p.stem.removeprefix("jamendo_") for p in existing_audio}
    if len(existing_audio) >= MAX_TRACKS:
        existing_audio.sort(key=lambda p: p.stat().st_mtime)
        for stale in existing_audio[:2]:
            stale.unlink(missing_ok=True)
            stale.with_suffix(".json").unlink(missing_ok=True)
            log.info("Removed old jazz track %s to rotate library.", stale.name)
            existing_ids.discard(stale.stem.removeprefix("jamendo_"))

    raw: list[dict] = []
    seen_track_ids: set[str] = set()
    offsets = random.sample(range(0, OFFSET_POOL_SIZE, FETCH_LIMIT), k=5)
    breaker = CircuitBreaker(threshold=3)
    for offset in offsets:
        if breaker.is_open:
            log.warning("Jamendo circuit breaker open after repeated failures; skipping remaining offsets.")
            break
        tracks, hard_failure = jamendo_cache.cached_search(
            MOOD_TAGS, offset, FETCH_LIMIT, _fetch_candidates_ex
        )
        if hard_failure:
            breaker.record_failure()
        else:
            breaker.record_success()
        for track in tracks:
            track_id = str(track.get("id") or "")
            if track_id and track_id not in seen_track_ids:
                seen_track_ids.add(track_id)
                raw.append(track)

    candidates = [t for t in raw if _downloadable(t, existing_ids)]
    if not candidates:
        commercially_safe = sum(1 for t in raw if _commercially_safe(str(t.get("license_ccurl") or "")))
        jazz_genre = sum(1 for t in raw if _is_jazz_genre(t))
        log.warning(
            "No new downloadable jazz tracks found this run (raw=%d, commercially_safe=%d, jazz_genre=%d, "
            "already_owned=%d).",
            len(raw),
            commercially_safe,
            jazz_genre,
            len(existing_ids),
        )
        jamendo_cache.prune()
        return 0

    random.shuffle(candidates)
    downloaded = 0
    for track in candidates:
        if downloaded >= DOWNLOADS_PER_RUN:
            break
        if _download_track(track):
            downloaded += 1
    log.info("Animal jazz sync complete: %d new track(s).", downloaded)
    jamendo_cache.prune()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
