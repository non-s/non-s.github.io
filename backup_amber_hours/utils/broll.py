"""Pixabay b-roll discovery, shared across content pillars.

The storm pillar needs real-world rain/storm footage -- see
fetch_pixabay()'s docstring for why Pixabay (checked live) is the source
used; Pexels was tried first and removed once that became clear. The
cute-animal Shorts pillar and the baby white/brown-noise pillar (both
chat, 2026-07-22) reuse the same fetch_pixabay()/download_clip() plumbing
with their own relevance signals below -- one HTTP/cache layer, one
per-pillar topical filter each.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
import random
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

_USER_AGENT = "WildBrief-Bot/4.0 (+https://non-s.github.io)"
_TIMEOUT = 20
_CACHE_DIR = Path(os.environ.get("BROLL_CACHE_DIR", "_data/broll_cache"))
_CACHE_TTL_S = 86400 * 7
_PIXABAY_API = "https://pixabay.com/api/videos/"

# The storm workflows can call fetch_pixabay() many times within one
# process run; this throttle keeps real (non-cached) calls from bursting.
_MIN_REQUEST_INTERVAL_S = float(os.environ.get("BROLL_MIN_INTERVAL_S", "0"))
_last_request_ts = 0.0


def _throttle() -> None:
    global _last_request_ts
    wait = _MIN_REQUEST_INTERVAL_S - (time.time() - _last_request_ts)
    if wait > 0:
        time.sleep(wait)
    _last_request_ts = time.time()


# Real-world rain/storm footage (video_type=
# "film", not "animation") instead of an illustrated look, so the check
# is topical relevance instead of art style -- same double-gate shape as
# ANIME_STYLE_SIGNALS/looks_anime_styled/is_on_brand_broll_clip above:
# checked once at download time (scripts/sync_storm_broll.py) and again
# at selection time (generate_storm_ambience.py, generate_storm_short.py)
# so a clip that reaches the shared pool some other way still can't be
# picked for a published video.
STORM_RELEVANCE_SIGNALS = {
    "rain",
    "storm",
    "thunder",
    "lightning",
    "cloud",
    "night",
    "window",
    "downpour",
    "monsoon",
}


def looks_storm_relevant(tags: str) -> bool:
    tags = (tags or "").lower()
    return any(signal in tags for signal in STORM_RELEVANCE_SIGNALS)


def is_on_brand_storm_clip(video_path: Path) -> bool:
    meta_path = video_path.with_suffix(".json")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(meta, dict):
        return False
    return looks_storm_relevant(str(meta.get("tags") or ""))


def pick_storm_broll_file(directory: Path, pattern: str = "pixabay_*.mp4") -> Path | None:
    """Random pick among real, on-topic storm/rain clips in `directory`.

    Plain uniform choice (unlike pick_weighted_broll_file's mood/
    performance weighting) -- the storm pillar doesn't have per-scene
    b-roll moods or performance data to weight by yet.
    """
    candidates = [p for p in sorted(directory.glob(pattern)) if is_on_brand_storm_clip(p)]
    if not candidates:
        return None
    return random.choice(candidates)


# Cute-animal Shorts pillar (chat, 2026-07-22): same double-gate shape as
# STORM_RELEVANCE_SIGNALS above (checked once at download time in
# scripts/sync_animal_broll.py, again at selection time in
# generate_cute_animal_short.py), just a different topic. Deliberately
# broad across several animals rather than one species -- variety across
# uploads is this pillar's whole appeal (see generate_cute_animal_short.py's
# module docstring), unlike the storm pillar's single fixed scene.
ANIMAL_RELEVANCE_SIGNALS = {
    "cat",
    "kitten",
    "puppy",
    "dog",
    "bunny",
    "rabbit",
    "hamster",
    "pet",
    "animal",
    "paw",
    "fur",
}


def looks_animal_relevant(tags: str) -> bool:
    tags = (tags or "").lower()
    return any(signal in tags for signal in ANIMAL_RELEVANCE_SIGNALS)


def is_on_brand_animal_clip(video_path: Path) -> bool:
    meta_path = video_path.with_suffix(".json")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(meta, dict):
        return False
    return looks_animal_relevant(str(meta.get("tags") or ""))


def pick_animal_broll_file(directory: Path, pattern: str = "pixabay_*.mp4") -> Path | None:
    """Random pick among real, on-topic cute-animal clips in `directory`."""
    candidates = [p for p in sorted(directory.glob(pattern)) if is_on_brand_animal_clip(p)]
    if not candidates:
        return None
    return random.choice(candidates)


# Baby white/brown-noise ambience pillar (acting-founder growth pass,
# 2026-07-22): same double-gate shape as STORM_RELEVANCE_SIGNALS/
# ANIMAL_RELEVANCE_SIGNALS above -- calm, dim, non-distracting nursery/
# night visuals, not the rain/storm scene (this pillar's audio is plain
# noise-color, not rain texture) and not the playful animal-content tags.
NOISE_RELEVANCE_SIGNALS = {
    "night",
    "star",
    "stars",
    "sky",
    "candle",
    "blanket",
    "cozy",
    "soft",
    "light",
    "room",
    "nursery",
    "moon",
    "glow",
    "lamp",
    "baby",
    "sleep",
    "crib",
    "calm",
}


def looks_noise_relevant(tags: str) -> bool:
    tags = (tags or "").lower()
    return any(signal in tags for signal in NOISE_RELEVANCE_SIGNALS)


def is_on_brand_noise_clip(video_path: Path) -> bool:
    meta_path = video_path.with_suffix(".json")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(meta, dict):
        return False
    return looks_noise_relevant(str(meta.get("tags") or ""))


def pick_noise_broll_file(directory: Path, pattern: str = "pixabay_*.mp4") -> Path | None:
    """Random pick among real, on-topic calm nursery/night clips in `directory`."""
    candidates = [p for p in sorted(directory.glob(pattern)) if is_on_brand_noise_clip(p)]
    if not candidates:
        return None
    return random.choice(candidates)


@dataclasses.dataclass
class BrollClip:
    """One b-roll candidate returned by Pexels."""

    source: str
    url: str
    download_url: str
    width: int
    height: int
    duration_s: float
    title: str = ""
    license: str = ""
    license_evidence: str = ""
    source_metadata: dict = dataclasses.field(default_factory=dict)


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT})
    return session


def _cache_key(source: str, query: str) -> Path:
    h = hashlib.sha256(f"{source}\x00{query}".lower().encode()).hexdigest()[:16]
    return _CACHE_DIR / f"{source}-{h}.json"


def _cache_get(path: Path) -> list[dict] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ts = data.get("ts", 0)
        if time.time() - ts > _CACHE_TTL_S:
            return None
        return data.get("clips") or []
    except Exception:
        return None


def _cache_put(path: Path, clips: list[dict]) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"ts": time.time(), "clips": clips}, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        log.debug("broll cache write failed: %s", exc)


def fetch_pixabay(query: str, per_page: int = 8, page: int = 1, video_type: str = "animation") -> list[BrollClip]:
    """Search Pixabay Videos for `query`. Empty list on any failure.

    `video_type="animation"` is Pixabay's own category for illustrated/
    motion-graphics content (as opposed to `"film"`, real-world footage) --
    this is what makes it a usable source for an anime/cartoon-style loop
    aesthetic, which Pexels does not have (checked live: Pexels "anime"
    searches return cosplay footage and mistagged live-action, not actual
    illustrated content).
    """
    key = os.environ.get("PIXABAY_API_KEY", "")
    if not key:
        log.warning("Pixabay API key (PIXABAY_API_KEY) is missing — cannot fetch B-roll")
        return []
    if not query:
        return []

    per_page = max(3, min(200, int(per_page or 8)))
    page = max(1, int(page or 1))
    cache_path = _cache_key("pixabay", f"{query}|{per_page}|{page}|{video_type}|v1")
    cached = _cache_get(cache_path)
    if cached is not None:
        return [BrollClip(**c) for c in cached]

    try:
        _throttle()
        response = _session().get(
            _PIXABAY_API,
            params={
                "key": key,
                "q": query[:100],
                "video_type": video_type,
                "per_page": per_page,
                "page": page,
                "safesearch": "true",
            },
            timeout=_TIMEOUT,
        )
        if response.status_code != 200:
            log.warning("Pixabay API request failed with status code %d for query %r", response.status_code, query[:40])
            return []
        videos = response.json().get("hits", []) or []
    except Exception as exc:
        log.debug("pixabay error %s: %s", query[:40], exc)
        return []

    out: list[BrollClip] = []
    for video in videos:
        files = video.get("videos") or {}
        # "large" (Pixabay's ~4K tier) is preferred over "medium" (chat,
        # 2026-07-21: the channel owner explicitly asked for real 4K across
        # every format -- long-form, Shorts, and the live relay -- and
        # accepted the reliability tradeoff this reverses. Re-encoding a
        # "large" clip through the loop-crossfade filter graph
        # (utils/broll.py -> scripts/live_stream_dynamic.py
        # _prepare_seamless_loop_clip) previously used enough memory on a
        # standard GitHub Actions runner to get the whole job SIGTERM'd
        # (exit 143) partway through, twice in a row, with no application-
        # level error at all -- only visible by comparing timing against
        # actual OOM behavior, since the process left no traceback. That
        # incident is why "medium" was preferred before; every consumer
        # now renders at 3840x2160 (TARGET_W/TARGET_H in
        # generate_storm_ambience.py/generate_storm_short.py/
        # live_stream_dynamic.py) so the 4K source is no longer discarded
        # at re-encode time, at the cost of reintroducing that OOM risk --
        # the live relay's existing self-heal loop (ffmpeg crash -> 5s
        # cooldown -> restart, plus live-stream-watchdog.yml) is the
        # accepted mitigation, not a new one.
        item = files.get("large") or files.get("medium") or files.get("small") or files.get("tiny")
        if not item or not item.get("url"):
            continue
        tags = str(video.get("tags") or "")
        out.append(
            BrollClip(
                source="pixabay",
                url=video.get("pageURL", ""),
                download_url=item["url"],
                width=int(item.get("width") or 0),
                height=int(item.get("height") or 0),
                duration_s=float(video.get("duration") or 0),
                title=tags.split(",")[0].strip() if tags else "",
                license="Pixabay Content License (free for commercial use, no attribution required)",
                license_evidence=video.get("pageURL", ""),
                source_metadata={
                    "pixabay_video_id": str(video.get("id") or ""),
                    "pixabay_page": page,
                    "pixabay_query": query[:100],
                    "photographer": video.get("user", ""),
                    "photographer_url": video.get("userURL", ""),
                    "is_ai_generated": bool(video.get("isAiGenerated")),
                    "tags": tags,
                },
            )
        )
    _cache_put(cache_path, [dataclasses.asdict(clip) for clip in out])
    return out


def download_clip(clip: BrollClip, dest: Path, max_bytes: int | None = None) -> bool:
    """Download `clip.download_url` to `dest`, capped by `max_bytes`."""
    if max_bytes is None:
        max_bytes = int(os.environ.get("BROLL_DOWNLOAD_MAX_BYTES", str(90 * 1024 * 1024)))
    try:
        response = _session().get(clip.download_url, stream=True, timeout=_TIMEOUT * 2)
        if response.status_code != 200:
            return False
        total = 0
        chunks = []
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                log.debug("broll clip exceeded max_bytes; aborting download")
                return False
            chunks.append(chunk)
        body = b"".join(chunks)
        if len(body) < 50 * 1024:
            return False
        if b"ftyp" not in body[:32]:
            return False
        dest.write_bytes(body)
        return True
    except Exception as exc:
        log.debug("broll download failed: %s", exc)
        return False
