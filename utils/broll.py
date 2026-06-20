"""Free-tier Pexels b-roll discovery for YouTube Shorts.

The Shorts pipeline needs real motion on screen, ideally with varied clips
every few seconds. Wild Brief now uses Pexels as the only production visual
source so the rights, cache, quota and QA behavior stay predictable.
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

log = logging.getLogger(__name__)

_USER_AGENT = "WildBrief-Bot/4.0 (+https://non-s.github.io)"
_TIMEOUT = 20
_CACHE_DIR = Path(os.environ.get("BROLL_CACHE_DIR", "_data/broll_cache"))
_CACHE_TTL_S = 86400 * 7
_PEXELS_API = "https://api.pexels.com/v1/videos/search"


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


def _pexels_clip_title(url: str, uploader: str = "") -> str:
    """Extract the descriptive clip slug; uploader names are not subjects."""
    parts = (url or "").rstrip("/").split("/")
    tail = parts[-1] if parts else ""
    slug = parts[-2] if tail.isdigit() and len(parts) >= 2 else re.sub(r"-\d+$", "", tail)
    return re.sub(r"[-_]+", " ", slug).strip() or uploader.strip()


def fetch_pexels(query: str, per_page: int = 8, page: int = 1) -> list[BrollClip]:
    """Search Pexels Videos for `query`. Empty list on any failure."""
    key = os.environ.get("PEXELS_API_KEY", "")
    if not key or not query:
        return []

    per_page = max(1, min(80, int(per_page or 8)))
    page = max(1, int(page or 1))
    cache_path = _cache_key("pexels", f"{query}|{per_page}|{page}|v1")
    cached = _cache_get(cache_path)
    if cached is not None:
        return [BrollClip(**c) for c in cached]

    try:
        response = _session().get(
            _PEXELS_API,
            params={
                "query": query[:120],
                "per_page": per_page,
                "page": page,
                "orientation": "portrait",
                "size": "medium",
            },
            headers={"Authorization": key},
            timeout=_TIMEOUT,
        )
        if response.status_code != 200:
            log.debug("pexels %d for %r", response.status_code, query[:40])
            return []
        videos = response.json().get("videos", []) or []
    except Exception as exc:
        log.debug("pexels error %s: %s", query[:40], exc)
        return []

    out: list[BrollClip] = []
    for video in videos:
        files = video.get("video_files", []) or []
        files = [item for item in files if item.get("link") and item.get("width") and item.get("height")]
        files.sort(
            key=lambda item: (
                0 if (item.get("height") or 0) >= (item.get("width") or 0) else 1,
                abs((item.get("height") or 0) - 1920),
            )
        )
        if not files:
            continue
        item = files[0]
        out.append(
            BrollClip(
                source="pexels",
                url=video.get("url", ""),
                download_url=item["link"],
                width=int(item.get("width") or 0),
                height=int(item.get("height") or 0),
                duration_s=float(video.get("duration") or 0),
                title=_pexels_clip_title(
                    video.get("url", ""),
                    (video.get("user", {}) or {}).get("name", ""),
                ),
                license="Pexels License (free for commercial use)",
                license_evidence=video.get("url", ""),
                source_metadata={
                    "pexels_video_id": str(video.get("id") or ""),
                    "pexels_page": page,
                    "pexels_query": query[:120],
                    "photographer": (video.get("user", {}) or {}).get("name", ""),
                    "photographer_url": (video.get("user", {}) or {}).get("url", ""),
                },
            )
        )
    _cache_put(cache_path, [dataclasses.asdict(clip) for clip in out])
    return out


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
    tokens = re.findall(r"[A-Za-z][A-Za-z\-']{2,}", text)
    kept = [token for token in tokens if token.lower() not in _STOPWORDS][:6]
    return " ".join(kept)


def _enabled_sources() -> list[str]:
    """Return active visual sources. Production is intentionally Pexels-only."""
    return ["pexels"]


def fetch_broll_clips(query: str, want_n: int = 4, category: str = "", animal_only: bool = False) -> list[BrollClip]:
    """Collect up to `want_n` vetted Pexels clips."""
    seen_urls: set[str] = set()
    collected: list[BrollClip] = []
    refined = _build_query(query)
    cat_query = (category or "").strip().lower()
    queries = [q for q in (refined, query, cat_query) if q]
    source_order = _enabled_sources()
    per_source: dict[str, int] = {source: 0 for source in source_order}

    for q in queries:
        if len(collected) >= want_n:
            break
        try:
            clips = fetch_pexels(q)
        except Exception as exc:
            log.warning("broll fetcher fetch_pexels crashed: %s", exc)
            clips = []
        for clip in clips:
            if clip.download_url in seen_urls:
                continue
            seen_urls.add(clip.download_url)
            collected.append(clip)
            per_source[clip.source] = per_source.get(clip.source, 0) + 1
            if len(collected) >= want_n:
                break

    source_counts = ", ".join(f"{source}={per_source.get(source, 0)}" for source in source_order)
    log.info("  B-roll source mode: %s · total=%d/%d", source_counts, len(collected), want_n)
    return collected


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
