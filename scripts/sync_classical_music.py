#!/usr/bin/env python3
"""Sync real, commercially-safe classical/orchestral/piano tracks from the
Jamendo API for the "Amber Hours Classical" pillar.

Classical is, by a wide margin, the best-yielding genre the channel owner
found when checking Jamendo's catalog live across many genres tonight:
`fuzzytags=classical+orchestral+piano` returned ~18.5-19% commercially-safe
(CC BY) results out of 200 raw, versus 1.5-9% for every other genre tried
(jazz, folk, electronic, pop, rock, ...). Verified the matches are
genuinely on-genre, not mistagged filler -- e.g. Kimiko Ishizaka's Open
Goldberg Variations (a well-known real open-licensed classical pianist)
came up repeatedly. `musicinfo.tags.genres` (not `musicinfo.genres` --
checked live, that's the correct nested path) reports "classical" on
~99.5% of raw results for this query, so the genre-gate below rarely
rejects a real match; it exists to catch the rare mistagged crossover
track, not to fight the search.

Same license-safety check every other Jamendo sync in this repo's history
uses (re-derived from git history, `_commercially_safe()` below): only
plain Attribution (CC BY) clears a monetized channel. Unlike every other
pillar's optional/bonus music layer, this pillar's whole audio identity
IS the licensed track -- see generate_classical_ambience.py's mandatory,
non-skippable attribution block for why that matters legally, not just
stylistically.

MAX_TRACKS/DOWNLOADS_PER_RUN sized toward the owner's explicit ~150-track
target for the live relay's rotation -- see this script's own module
docstring math in the final build report for the realistic ramp-up
curve, given the measured ~19% yield (much faster than the old lofi
pillar's 150-track ramp at ~2% yield, which is the historical precedent
this script's shape is copied from -- see `git show 3b9d5b79a --
scripts/sync_jamendo_music.py`).
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
log = logging.getLogger("classical_music_sync")

CLIENT_ID = "04ff30b1"
API_URL = "https://api.jamendo.com/v3.0/tracks/"
CLASSICAL_DIR = ROOT / "_assets" / "audio" / "classical"
MAX_TRACKS = 150
DOWNLOADS_PER_RUN = 30  # higher than the jazz/lofi syncs' 10-20 -- yield here is ~9x jazz's, can afford more per run
REQUEST_TIMEOUT_S = 20
FETCH_RETRIES = 3
RETRY_DELAY_S = 2.0
FETCH_LIMIT = 200
OFFSET_POOL_SIZE = 2000

# fuzzytags = OR search. classical+orchestral+piano is the exact query the
# channel owner checked live (~18.5-19% yield); instrumental/chamber/
# symphonic widen the candidate pool further using the same "widen the
# net, filter by genre" technique the jazz/lofi syncs use, without
# relaxing what counts as on-brand below.
MOOD_TAGS = "classical+orchestral+piano+instrumental+chamber+symphonic"

# Only tracks actually tagged with one of these genres count as "classical"
# for this pillar. Checked live: "classical" itself covers ~99.5% of raw
# matches for the core query; the others are real co-tags seen on the same
# result set (filmscore, symphonic, chamber) or defensive extras (piano,
# orchestral) in case a future/different query surfaces them under a
# slightly different tag.
PREFERRED_CLASSICAL_GENRES = {"classical", "orchestral", "symphonic", "chamber", "filmscore", "piano"}


def _fetch_candidates_ex(tags: str = MOOD_TAGS, limit: int = FETCH_LIMIT, offset: int = 0) -> tuple[list[dict], bool]:
    """Same shape as every other Jamendo sync in this repo (re-derived
    from the removed scripts/sync_jamendo_music.py's identical helper via
    git history) -- see its docstring for the retry/circuit-breaker
    reasoning; Jamendo's API flakiness (identical requests occasionally
    returning an empty result set even on "success" status) is unrelated
    to which tags/pillar is searching."""
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


def _is_classical_genre(track: dict) -> bool:
    genres = set(((track.get("musicinfo") or {}).get("tags") or {}).get("genres") or [])
    return bool(genres & PREFERRED_CLASSICAL_GENRES)


def _is_instrumental(track: dict) -> bool:
    """Soft quality gate: exclude a track explicitly tagged as having
    vocals (a sung crossover track slipping through the classical tag),
    but don't require the field be set -- checked live, Jamendo leaves
    this blank on some genuine classical tracks rather than omitting it
    outright, so "blank" must mean "allow", not "reject"."""
    value = str((track.get("musicinfo") or {}).get("vocalinstrumental") or "").strip().lower()
    return value != "vocal"


def _downloadable(track: dict, existing_ids: set[str]) -> bool:
    if not track.get("audiodownload_allowed"):
        return False
    if not track.get("audiodownload"):
        return False
    if not _commercially_safe(str(track.get("license_ccurl") or "")):
        return False
    if not _is_classical_genre(track):
        return False
    if not _is_instrumental(track):
        return False
    if str(track.get("id")) in existing_ids:
        return False
    return True


def _download_track(track: dict) -> bool:
    track_id = str(track["id"])
    audio_path = CLASSICAL_DIR / f"jamendo_{track_id}.mp3"
    meta_path = CLASSICAL_DIR / f"jamendo_{track_id}.json"
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
    CLASSICAL_DIR.mkdir(parents=True, exist_ok=True)

    existing_audio = list(CLASSICAL_DIR.glob("jamendo_*.mp3"))
    existing_ids = {p.stem.removeprefix("jamendo_") for p in existing_audio}
    if len(existing_audio) >= MAX_TRACKS:
        existing_audio.sort(key=lambda p: p.stat().st_mtime)
        for stale in existing_audio[:3]:
            stale.unlink(missing_ok=True)
            stale.with_suffix(".json").unlink(missing_ok=True)
            log.info("Removed old classical track %s to rotate library.", stale.name)
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
        classical_genre = sum(1 for t in raw if _is_classical_genre(t))
        log.warning(
            "No new downloadable classical tracks found this run (raw=%d, commercially_safe=%d, "
            "classical_genre=%d, already_owned=%d).",
            len(raw),
            commercially_safe,
            classical_genre,
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
    log.info(
        "Classical music sync complete: %d new track(s) (library now ~%d).", downloaded, len(existing_ids) + downloaded
    )
    jamendo_cache.prune()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
