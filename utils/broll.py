"""
utils/broll.py — Free-tier b-roll discovery for YouTube Shorts.

Why this exists
---------------
YouTube's "Inauthentic Content" policy (July 2025) flags pure
narration-over-static-image Shorts as low-effort AI content. Channels
have been demonetised / terminated for it. To stay on the right side
of the bar we have to put MOTION on screen, ideally varied every 2-3s.

This module keeps animal footage discovery small and reusable.
Wild Brief intentionally uses vetted free sources:

  1. Internet Archive public-domain/CC0 video — default, no API key

Each source returns a list of `BrollClip` objects sorted by relevance.
`fetch_broll_clips(query, want_n)` is the unified entry point.

Pexels/Pixabay remain as opt-in legacy providers through
`BROLL_SOURCE_MODE=archive,pexels,pixabay`, but they are no longer used by
default.

Caching
-------
Archive.org asks automated tools to use descriptive User-Agent headers,
cache responses, and respect rate limits. We cache discovery on disk
under `_data/broll_cache/` so a re-run of the same story avoids repeated
metadata calls.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path

import requests

from utils.internet_archive import archive_video_relevance_score, discover_public_domain_videos

log = logging.getLogger(__name__)

_USER_AGENT = "WildBrief-Bot/4.0 (+https://non-s.github.io)"
_TIMEOUT = 20
_CACHE_DIR = Path(os.environ.get("BROLL_CACHE_DIR", "_data/broll_cache"))
_CACHE_TTL_S = 86400 * 7  # 7 days


@dataclasses.dataclass
class BrollClip:
    """One b-roll candidate.

    `download_url` points to an MP4. `width`/`height` describe the
    source resolution — we prefer >= 1080 vertical so the post-crop
    to 1080x1920 doesn't upscale.
    """

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


# ── HTTP session ─────────────────────────────────────────────────


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": _USER_AGENT})
    return s


# ── On-disk cache for discovery results ──────────────────────────


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


# ── 1. Pexels Videos API ─────────────────────────────────────────
#
# Endpoint: GET https://api.pexels.com/videos/search
# Header:   Authorization: <PEXELS_API_KEY>
# Limits:   200 req/h, 20k/mo. Free key, no card.
# Docs:     https://www.pexels.com/api/documentation/#videos

_PEXELS_API = "https://api.pexels.com/videos/search"
_PIXABAY_API = "https://pixabay.com/api/videos/"


def _pexels_clip_title(url: str, uploader: str = "") -> str:
    """Extract the descriptive clip slug; uploader names are not subjects."""
    parts = (url or "").rstrip("/").split("/")
    tail = parts[-1] if parts else ""
    slug = parts[-2] if tail.isdigit() and len(parts) >= 2 else re.sub(r"-\d+$", "", tail)
    return re.sub(r"[-_]+", " ", slug).strip() or uploader.strip()


def fetch_pexels(query: str, per_page: int = 8) -> list[BrollClip]:
    """Search Pexels Videos for `query`. Empty list on any failure."""
    key = os.environ.get("PEXELS_API_KEY", "")
    if not key or not query:
        return []

    cache_path = _cache_key("pexels", f"{query}|{per_page}")
    cached = _cache_get(cache_path)
    if cached is not None:
        return [BrollClip(**c) for c in cached]

    try:
        r = _session().get(
            _PEXELS_API,
            params={
                "query": query[:120],
                "per_page": per_page,
                "orientation": "portrait",  # 9:16 Shorts-native
                "size": "medium",
            },
            headers={"Authorization": key},
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            log.debug("pexels %d for %r", r.status_code, query[:40])
            return []
        videos = r.json().get("videos", []) or []
    except Exception as exc:
        log.debug("pexels error %s: %s", query[:40], exc)
        return []

    out: list[BrollClip] = []
    for v in videos:
        # Pick the highest-quality vertical-orientation file under 5 MB.
        files = v.get("video_files", []) or []
        files = [f for f in files if f.get("link") and f.get("width") and f.get("height")]
        # Prefer portrait/vertical; fall back to landscape we'll crop.
        files.sort(
            key=lambda f: (
                0 if (f.get("height") or 0) >= (f.get("width") or 0) else 1,
                abs((f.get("height") or 0) - 1920),
            )
        )
        if not files:
            continue
        f = files[0]
        out.append(
            BrollClip(
                source="pexels",
                url=v.get("url", ""),
                download_url=f["link"],
                width=int(f.get("width") or 0),
                height=int(f.get("height") or 0),
                duration_s=float(v.get("duration") or 0),
                title=_pexels_clip_title(
                    v.get("url", ""),
                    (v.get("user", {}) or {}).get("name", ""),
                ),
                license="Pexels License (free for commercial use)",
            )
        )
    _cache_put(cache_path, [dataclasses.asdict(c) for c in out])
    return out


def fetch_pixabay(query: str, per_page: int = 8) -> list[BrollClip]:
    """Search Pixabay Videos for `query`. Empty list on any failure."""
    key = os.environ.get("PIXABAY_API_KEY", "")
    if not key or not query:
        return []
    cache_path = _cache_key("pixabay", f"{query}|{per_page}")
    cached = _cache_get(cache_path)
    if cached is not None:
        return [BrollClip(**c) for c in cached]
    try:
        r = _session().get(
            _PIXABAY_API,
            params={
                "key": key,
                "q": query[:100],
                "per_page": max(3, min(int(per_page), 200)),
                "safesearch": "true",
                "video_type": "all",
            },
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            log.debug("pixabay %d for %r", r.status_code, query[:40])
            return []
        videos = r.json().get("hits", []) or []
    except Exception as exc:
        log.debug("pixabay error %s: %s", query[:40], exc)
        return []
    out: list[BrollClip] = []
    for video in videos:
        variants = [
            item
            for item in (video.get("videos") or {}).values()
            if item.get("url") and item.get("width") and item.get("height")
        ]
        variants.sort(
            key=lambda item: (
                0 if int(item.get("height") or 0) >= int(item.get("width") or 0) else 1,
                abs(int(item.get("height") or 0) - 1920),
            )
        )
        if not variants:
            continue
        item = variants[0]
        out.append(
            BrollClip(
                source="pixabay",
                url=video.get("pageURL", ""),
                download_url=item["url"],
                width=int(item.get("width") or 0),
                height=int(item.get("height") or 0),
                duration_s=float(video.get("duration") or 0),
                title=str(video.get("tags") or "").strip(),
                license="Pixabay Content License (free for commercial use)",
            )
        )
    _cache_put(cache_path, [dataclasses.asdict(c) for c in out])
    return out


def fetch_archive(query: str, per_page: int = 8) -> list[BrollClip]:
    """Search Internet Archive for explicit public-domain/CC0 video clips."""
    if not query:
        return []
    rows = max(12, min(int(per_page or 8) * 5, 50))
    cache_path = _cache_key("archive", f"{query}|{rows}|pd-video-v5")
    cached = _cache_get(cache_path)
    if cached is not None:
        return [BrollClip(**c) for c in cached]
    assets = discover_public_domain_videos(query, rows=rows)
    out: list[BrollClip] = []
    for asset in assets:
        out.append(
            BrollClip(
                source="internet_archive",
                url=asset.source_url,
                download_url=asset.url,
                width=asset.width or 1280,
                height=asset.height or 720,
                duration_s=asset.duration_s or 10.0,
                title=asset.title,
                license=asset.license,
                license_evidence=asset.license_evidence,
                source_metadata={
                    "identifier": asset.identifier,
                    "file_name": asset.file_name,
                    "creator": asset.creator,
                    "collection": asset.collection,
                    "description": asset.description,
                    "downloads": asset.downloads,
                    "relevance_score": archive_video_relevance_score(asset, query),
                    "rights_policy": "explicit_public_domain_cc0_or_usgov_only",
                },
            )
        )
    out = out[: max(1, int(per_page or 8))]
    _cache_put(cache_path, [dataclasses.asdict(c) for c in out])
    return out


# ── 2. Discovery ─────────────────────────────────────────────────

# Strip filler words so "The octopus changes colour today" becomes
# a more targeted "octopus changes colour" — better b-roll matches.
_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "as",
    "that",
    "this",
    "these",
    "those",
    "it",
    "its",
    "after",
    "before",
    "during",
    "into",
    "over",
    "under",
    "between",
    "again",
    "than",
    "today",
    "yesterday",
    "tomorrow",
    "new",
    "latest",
    "update",
    "report",
    "says",
    "said",
    "now",
    "just",
    "really",
}


def _build_query(text: str) -> str:
    """Reduce a title to b-roll-friendly keywords."""
    if not text:
        return ""
    toks = re.findall(r"[A-Za-z][A-Za-z\-']{2,}", text)
    kept = [t for t in toks if t.lower() not in _STOPWORDS][:6]
    return " ".join(kept)


def _enabled_sources() -> list[str]:
    raw = os.environ.get("BROLL_SOURCE_MODE", "archive").strip().lower()
    if raw in {"legacy", "pexels"}:
        return ["pexels", "pixabay"]
    if raw in {"all", "archive+legacy"}:
        return ["archive", "pexels", "pixabay"]
    sources = [part.strip() for part in re.split(r"[,;+ ]+", raw) if part.strip()]
    allowed = {"archive", "internet_archive", "pexels", "pixabay"}
    normalised = ["archive" if source == "internet_archive" else source for source in sources if source in allowed]
    return normalised or ["archive"]


def fetch_broll_clips(query: str, want_n: int = 4, category: str = "", animal_only: bool = False) -> list[BrollClip]:
    """Collect up to `want_n` vetted animal clips."""
    seen_urls: set[str] = set()
    collected: list[BrollClip] = []
    refined = _build_query(query)
    cat_query = (category or "").strip().lower()
    queries = [q for q in (refined, query, cat_query) if q]

    # Track per-source contribution so b-roll failures are visible at INFO.
    fetcher_map = {
        "archive": fetch_archive,
        "pexels": fetch_pexels,
        "pixabay": fetch_pixabay,
    }
    source_order = _enabled_sources()
    per_source: dict[str, int] = {source: 0 for source in source_order}

    for source in source_order:
        fetcher = fetcher_map[source]
        if len(collected) >= want_n:
            break
        for q in queries:
            if len(collected) >= want_n:
                break
            try:
                clips = fetcher(q)
            except Exception as exc:
                log.warning("broll fetcher %s crashed: %s", fetcher.__name__, exc)
                clips = []
            for c in clips:
                if c.download_url in seen_urls:
                    continue
                seen_urls.add(c.download_url)
                collected.append(c)
                per_source[c.source] = per_source.get(c.source, 0) + 1
                if len(collected) >= want_n:
                    break

    source_counts = ", ".join(f"{source}={per_source.get(source, 0)}" for source in source_order)
    log.info("  B-roll source mode: %s · total=%d/%d", source_counts, len(collected), want_n)
    return collected


# ── Download helper ──────────────────────────────────────────────


def download_clip(clip: BrollClip, dest: Path, max_bytes: int | None = None) -> bool:
    """Download `clip.download_url` to `dest`. Caps body at `max_bytes`.

    Returns True on success. Uses streaming so a 30 MB clip doesn't
    blow up memory. Validates the MP4 magic bytes.
    """
    if max_bytes is None:
        max_bytes = int(os.environ.get("BROLL_DOWNLOAD_MAX_BYTES", str(90 * 1024 * 1024)))
    try:
        r = _session().get(clip.download_url, stream=True, timeout=_TIMEOUT * 2)
        if r.status_code != 200:
            return False
        total = 0
        chunks = []
        for chunk in r.iter_content(chunk_size=64 * 1024):
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
        # MP4 magic: "ftyp" at byte 4-8 of an ISO base media file.
        if b"ftyp" not in body[:32]:
            return False
        dest.write_bytes(body)
        return True
    except Exception as exc:
        log.debug("broll download failed: %s", exc)
        return False
