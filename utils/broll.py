"""Pixabay b-roll discovery for the lofi Shorts/mix/live pipeline.

The lofi pipeline needs an anime/illustrated-style loop, not real-world
footage -- see fetch_pixabay()'s docstring for why Pixabay (checked live)
is the only source that actually has that content; Pexels was tried first
and removed once that became clear.
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

from utils.broll_performance import mood_performance_weights
from utils.lofi_branding import playlist_bucket_for_title

log = logging.getLogger(__name__)

_USER_AGENT = "WildBrief-Bot/4.0 (+https://non-s.github.io)"
_TIMEOUT = 20
_CACHE_DIR = Path(os.environ.get("BROLL_CACHE_DIR", "_data/broll_cache"))
_CACHE_TTL_S = 86400 * 7
_PIXABAY_API = "https://pixabay.com/api/videos/"

# youtube-bot.yml can call fetch_pixabay() many times within one process
# run; this throttle keeps real (non-cached) calls from bursting.
_MIN_REQUEST_INTERVAL_S = float(os.environ.get("BROLL_MIN_INTERVAL_S", "0"))
_last_request_ts = 0.0


def _throttle() -> None:
    global _last_request_ts
    wait = _MIN_REQUEST_INTERVAL_S - (time.time() - _last_request_ts)
    if wait > 0:
        time.sleep(wait)
    _last_request_ts = time.time()


# Pixabay's video_type=animation category also contains generic 3D
# corporate/motion-graphics stock clips -- checked live: a sync run for
# the query "anime library reading" downloaded a plain 3D "man with a
# stack of books" explainer-video clip (Pixabay id 115021, tagged just
# "man" as its first/title tag), which then played on the live relay
# looking nothing like the intended Lofi-Girl-style loop, and was later
# also picked up as a Short's b-roll since nothing checked style at
# selection time either. video_type alone doesn't guarantee the actual
# illustrated look, so require at least one of Pixabay's own tags to
# name an anime/cartoon style -- both when a clip is downloaded
# (scripts/sync_lofi_broll.py) and again whenever one is picked off disk
# for output (generate_lofi_short.py, generate_lofi_mix.py,
# scripts/live_stream_dynamic.py), so a clip that reaches the shared
# library some other way (stale cache, manual copy, a sync run on older
# code) still can't end up in a published video.
ANIME_STYLE_SIGNALS = {
    "anime",
    "cartoon",
    "manga",
    "chibi",
    "kawaii",
    "toon",
    "illustration",
    "illustrated",
    "drawn",
    "hand-drawn",
    "handdrawn",
    "comic",
}


def looks_anime_styled(tags: str) -> bool:
    tags = (tags or "").lower()
    return any(signal in tags for signal in ANIME_STYLE_SIGNALS)


def is_on_brand_broll_clip(video_path: Path) -> bool:
    """True if `video_path`'s sidecar JSON has anime-style tag evidence.

    Selection-time counterpart to scripts/sync_lofi_broll.py's
    download-time gate: a clip already sitting in the shared media-library
    cache (pre-dating that filter, restored from a stale cache, or copied
    in by hand) must not be picked for a Short/mix/live loop just because
    it's on disk.
    """
    meta_path = video_path.with_suffix(".json")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(meta, dict):
        return False
    return looks_anime_styled(str(meta.get("tags") or ""))


_PREFERRED_MOOD_SIGNALS = ("rain", "night", "snow")
_PREFERRED_WEIGHT = 3


def _clip_query(video_path: Path) -> str:
    meta_path = video_path.with_suffix(".json")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(meta.get("query") or "") if isinstance(meta, dict) else ""


def is_preferred_mood_clip(video_path: Path) -> bool:
    """True if this clip's source query names the rainy-night/cozy-anime
    sub-niche picked in chat on 2026-07-19. Used to weight random b-roll
    selection toward it so new Shorts/mixes actually reflect the channel's
    chosen identity instead of diluting it evenly across all ten b-roll
    moods (the same problem that started that conversation).
    """
    query = _clip_query(video_path).lower()
    return any(signal in query for signal in _PREFERRED_MOOD_SIGNALS)


def pick_weighted_broll_file(
    directory: Path, pattern: str, performance_weights: dict[str, float] | None = None
) -> Path | None:
    """Random pick among on-brand clips in `directory`, but a rainy-night/
    night-city/snow clip is _PREFERRED_WEIGHT times as likely to be chosen
    as any other single clip -- further scaled by `performance_weights`
    (playlist bucket -> multiplier), defaulting to
    utils.broll_performance.mood_performance_weights() when not given, so
    a bucket that's actually performed better/worse on this channel skews
    selection odds further, on top of that fixed editorial bias. That
    default is a no-op ({} -> every multiplier falls back to 1.0) until
    there's enough real per-video view data to compute it from -- see
    utils/broll_performance.py's docstring.
    """
    candidates = [p for p in sorted(directory.glob(pattern)) if is_on_brand_broll_clip(p)]
    if not candidates:
        return None
    if performance_weights is None:
        performance_weights = mood_performance_weights()
    weights = []
    for p in candidates:
        weight = float(_PREFERRED_WEIGHT if is_preferred_mood_clip(p) else 1)
        if performance_weights:
            bucket = playlist_bucket_for_title(_clip_query(p))
            weight *= performance_weights.get(bucket, 1.0)
        weights.append(weight)
    return random.choices(candidates, weights=weights, k=1)[0]


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
        # "medium" (Pixabay's ~1280x720 tier) is preferred over "large"
        # (often 4K) on purpose: both consumers of this clip re-encode it
        # at most to 1920x1080 (TARGET_W/TARGET_H in live_stream_dynamic.py),
        # so a 4K source buys nothing visually but is far more expensive to
        # decode/re-encode. Checked live: re-encoding a "large" clip
        # through the live relay's loop-crossfade filter graph
        # (utils/broll.py -> scripts/live_stream_dynamic.py
        # _prepare_seamless_loop_clip) used enough memory on a standard
        # GitHub Actions runner to get the whole job SIGTERM'd (exit 143)
        # partway through, twice in a row, with no application-level error
        # at all -- only visible by comparing timing against actual OOM
        # behavior, since the process left no traceback.
        item = files.get("medium") or files.get("large") or files.get("small") or files.get("tiny")
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
