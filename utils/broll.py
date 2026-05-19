"""
utils/broll.py — Free-tier b-roll discovery for YouTube Shorts.

Why this exists
---------------
YouTube's "Inauthentic Content" policy (July 2025) flags pure
narration-over-static-image Shorts as low-effort AI content. Channels
have been demonetised / terminated for it. To stay on the right side
of the bar we have to put MOTION on screen, ideally varied every 2-3s.

This module gives us free, keyless or low-key motion footage:

  1. Pexels Videos API   — best signal, requires a free key (no card)
  2. NASA Image+Video    — public domain, no key, big visuals
  3. Internet Archive    — public domain, no key, niche
  4. Pollinations gen    — last-resort AI-generated b-roll, no key

Each source returns a list of `BrollClip` objects sorted by relevance.
`fetch_broll_clips(query, want_n)` is the unified entry point — it
walks the sources in priority order until it has `want_n` clips.

Caching
-------
Pexels rate-limits at 200/h, NASA generously. We cache discovery
results in-memory per process and on disk under `_data/broll_cache/`
so a re-run of the same story doesn't burn quota.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
import random
import re
import time
import urllib.parse
from pathlib import Path
from typing import Iterable

import requests

log = logging.getLogger(__name__)

_USER_AGENT = "GlobalBR-News-Bot/4.0 (+https://non-s.github.io)"
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


# ── HTTP session ─────────────────────────────────────────────────

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": _USER_AGENT})
    return s


# ── On-disk cache for discovery results ──────────────────────────

def _cache_key(source: str, query: str) -> Path:
    h = hashlib.sha1(f"{source}\x00{query}".lower().encode()).hexdigest()[:16]
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
        path.write_text(json.dumps({"ts": time.time(), "clips": clips},
                                   ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        log.debug("broll cache write failed: %s", exc)


# ── 1. Pexels Videos API ─────────────────────────────────────────
#
# Endpoint: GET https://api.pexels.com/videos/search
# Header:   Authorization: <PEXELS_API_KEY>
# Limits:   200 req/h, 20k/mo. Free key, no card.
# Docs:     https://www.pexels.com/api/documentation/#videos

_PEXELS_API = "https://api.pexels.com/videos/search"


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
        files.sort(key=lambda f: (
            0 if (f.get("height") or 0) >= (f.get("width") or 0) else 1,
            abs((f.get("height") or 0) - 1920),
        ))
        if not files:
            continue
        f = files[0]
        out.append(BrollClip(
            source="pexels",
            url=v.get("url", ""),
            download_url=f["link"],
            width=int(f.get("width") or 0),
            height=int(f.get("height") or 0),
            duration_s=float(v.get("duration") or 0),
            title=(v.get("user", {}) or {}).get("name", "") + " — pexels",
            license="Pexels License (free for commercial use)",
        ))
    _cache_put(cache_path, [dataclasses.asdict(c) for c in out])
    return out


# ── 2. NASA Image & Video Library ────────────────────────────────
#
# Endpoint: GET https://images-api.nasa.gov/search?media_type=video
# Auth:     none required
# Docs:     https://api.nasa.gov/

_NASA_API = "https://images-api.nasa.gov/search"


def fetch_nasa(query: str, per_page: int = 4) -> list[BrollClip]:
    """Public-domain space / Earth imagery + video. No key."""
    if not query:
        return []

    cache_path = _cache_key("nasa", query)
    cached = _cache_get(cache_path)
    if cached is not None:
        return [BrollClip(**c) for c in cached]

    try:
        r = _session().get(
            _NASA_API,
            params={"q": query[:120], "media_type": "video", "page_size": per_page},
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        items = (r.json().get("collection", {}) or {}).get("items", []) or []
    except Exception as exc:
        log.debug("nasa error: %s", exc)
        return []

    out: list[BrollClip] = []
    for item in items[:per_page]:
        href = item.get("href", "")  # JSON manifest URL
        if not href:
            continue
        # Resolve the manifest to pick the largest MP4.
        try:
            m = _session().get(href, timeout=_TIMEOUT)
            if m.status_code != 200:
                continue
            urls = m.json() or []
        except Exception:
            continue
        urls = [u for u in urls if isinstance(u, str) and u.endswith(".mp4")]
        if not urls:
            continue
        # NASA orders by size descending — prefer the smaller one for bandwidth.
        download_url = urls[-1] if len(urls) > 1 else urls[0]
        # NASA metadata.
        data = (item.get("data") or [{}])[0]
        out.append(BrollClip(
            source="nasa",
            url=item.get("href", ""),
            download_url=download_url,
            width=1920, height=1080,  # NASA's typical encode; cropped at compose time
            duration_s=10.0,  # unknown; treat as plenty
            title=data.get("title", ""),
            license="NASA public domain",
        ))
    _cache_put(cache_path, [dataclasses.asdict(c) for c in out])
    return out


# ── 3. Internet Archive video search ─────────────────────────────
#
# Endpoint: GET https://archive.org/advancedsearch.php
# Auth:     none
# Docs:     https://archive.org/developers/api.html

_IA_API = "https://archive.org/advancedsearch.php"
_IA_DOWNLOAD = "https://archive.org/download"


def fetch_internet_archive(query: str, per_page: int = 3) -> list[BrollClip]:
    """Free, public-domain video search. Best for older / niche subjects."""
    if not query:
        return []

    cache_path = _cache_key("ia", query)
    cached = _cache_get(cache_path)
    if cached is not None:
        return [BrollClip(**c) for c in cached]

    q = f"({query}) AND mediatype:movies AND format:mp4"
    try:
        r = _session().get(
            _IA_API,
            params={
                "q": q,
                "fl[]": "identifier,title",
                "rows": per_page * 2,
                "output": "json",
            },
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        docs = (r.json().get("response", {}) or {}).get("docs", []) or []
    except Exception as exc:
        log.debug("ia error: %s", exc)
        return []

    out: list[BrollClip] = []
    for doc in docs[:per_page]:
        ident = doc.get("identifier", "")
        if not ident:
            continue
        # IA serves at predictable paths; we discover the actual MP4 via the
        # metadata endpoint.
        try:
            meta = _session().get(f"https://archive.org/metadata/{ident}",
                                   timeout=_TIMEOUT).json()
            files = meta.get("files", []) or []
            mp4 = next((f for f in files if (f.get("name") or "").endswith(".mp4")), None)
            if not mp4:
                continue
            url = f"{_IA_DOWNLOAD}/{ident}/{urllib.parse.quote(mp4['name'])}"
        except Exception:
            continue
        out.append(BrollClip(
            source="internet-archive",
            url=f"https://archive.org/details/{ident}",
            download_url=url,
            width=1280, height=720,
            duration_s=15.0,
            title=doc.get("title", ""),
            license="Internet Archive (varies, often PD or CC)",
        ))
    _cache_put(cache_path, [dataclasses.asdict(c) for c in out])
    return out


# ── 4. Unified discovery ─────────────────────────────────────────

# Strip filler words so "Apple announces new iPhone in California" becomes
# a more targeted "Apple iPhone California" — better b-roll matches.
_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "as", "that", "this", "these", "those", "it", "its", "after", "before",
    "during", "into", "over", "under", "between", "again", "than",
    "today", "yesterday", "tomorrow", "new", "latest", "update", "report",
    "says", "said", "now", "just", "really",
}


def _build_query(text: str) -> str:
    """Reduce a headline to b-roll-friendly keywords."""
    if not text:
        return ""
    toks = re.findall(r"[A-Za-z][A-Za-z\-']{2,}", text)
    kept = [t for t in toks if t.lower() not in _STOPWORDS][:6]
    return " ".join(kept)


def fetch_broll_clips(query: str, want_n: int = 4, category: str = "") -> list[BrollClip]:
    """Walk sources until we have `want_n` clips.

    Order: Pexels → NASA → Internet Archive. We always try Pexels first
    because it has portrait-orientation footage tuned for vertical use.
    Returns whatever we managed to collect (empty list possible).
    """
    seen_urls: set[str] = set()
    collected: list[BrollClip] = []
    refined = _build_query(query)
    cat_query = (category or "").strip().lower()
    queries = [q for q in (refined, query, cat_query) if q]

    # Track per-source contribution so b-roll failures are visible at
    # INFO. Without this the workflow log only shows the final count
    # and operators can't tell whether a missing Pexels key, a quota
    # wall, or an unlucky query phrase pushed the run into the static
    # fallback.
    per_source: dict[str, int] = {"pexels": 0, "nasa": 0, "internet_archive": 0}

    for fetcher in (fetch_pexels, fetch_nasa, fetch_internet_archive):
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

    pexels_key_present = bool(os.environ.get("PEXELS_API_KEY", "").strip())
    log.info(
        "  🔎 B-roll sources: pexels=%d (key %s) · nasa=%d · archive=%d · total=%d/%d",
        per_source["pexels"],
        "present" if pexels_key_present else "MISSING",
        per_source["nasa"],
        per_source["internet_archive"],
        len(collected),
        want_n,
    )
    return collected


# ── Download helper ──────────────────────────────────────────────

def download_clip(clip: BrollClip, dest: Path, max_bytes: int = 30 * 1024 * 1024) -> bool:
    """Download `clip.download_url` to `dest`. Caps body at `max_bytes`.

    Returns True on success. Uses streaming so a 30 MB clip doesn't
    blow up memory. Validates the MP4 magic bytes.
    """
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
