"""
utils/free_images.py — Free image-source fallback chain for Shorts backgrounds.

The Shorts pipeline already tries (1) the story's own image_url and (2) a
Pollinations.ai generation. Both can fail at the same time — RSS feeds
sometimes omit images, and Pollinations rate-limits / 502s in bursts.
This module adds three more keyless sources to try BEFORE giving up:

  - Open Graph image extracted from the source article URL
  - Wikipedia REST API summary thumbnail (when the title mentions a named entity)
  - Openverse Creative-Commons image search (no auth, no key)

Every function returns a bool (True if it wrote a usable image to dest)
so callers can chain them with `or`.
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from pathlib import Path

import requests

log = logging.getLogger(__name__)

_USER_AGENT = "GlobalBR-News-Bot/4.0 (+https://non-s.github.io)"
_TIMEOUT = 12
_MIN_BYTES = 5 * 1024  # below this size, the file is too small to be a useful background


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": _USER_AGENT})
    return s


def _looks_like_image(body: bytes) -> bool:
    """Magic-byte sniff — JPEG / PNG / GIF / WEBP."""
    if len(body) < _MIN_BYTES:
        return False
    head = body[:12]
    return (
        head.startswith(b"\xff\xd8\xff")            # JPEG
        or head.startswith(b"\x89PNG\r\n\x1a\n")    # PNG
        or head.startswith(b"GIF8")                 # GIF
        or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
    )


def _download(url: str, dest: Path, timeout: int = _TIMEOUT) -> bool:
    """GET an image URL into `dest`. Validates content-type + magic bytes."""
    if not url or not url.startswith(("http://", "https://")):
        return False
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": _USER_AGENT}, stream=False)
        if r.status_code != 200:
            return False
        ctype = (r.headers.get("Content-Type") or "").lower()
        # Some CDNs send octet-stream on cache miss; rely on the magic
        # sniff in that case.
        if not (ctype.startswith("image/") or ctype.startswith("application/octet")):
            return False
        if not _looks_like_image(r.content):
            return False
        dest.write_bytes(r.content)
        return True
    except Exception as e:
        log.debug("free_images _download(%s): %s", url[:60], e)
        return False


# ── Open Graph image extractor ────────────────────────────────────
#
# Most news sites publish og:image / twitter:image meta tags. Pulling
# that gives us the publisher's own hero image — usually much more
# relevant than a generic Pollinations background. Free, no auth.

_OG_IMAGE_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image(?::src)?)["\'][^>]*content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_OG_IMAGE_REVERSED = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\'](?:og:image|twitter:image(?::src)?)["\']',
    re.IGNORECASE,
)


def fetch_og_image(article_url: str, dest: Path) -> bool:
    """Scrape `<meta property=og:image>` from the article URL and download it.

    Defensive: any non-200 / parse failure / SSRF-shaped URL returns False.
    """
    if not article_url or not article_url.startswith(("http://", "https://")):
        return False
    try:
        r = requests.get(
            article_url,
            timeout=_TIMEOUT,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
            },
            allow_redirects=True,
        )
        if r.status_code != 200:
            return False
        # Cap the HTML we scan — head section is the only place og: tags
        # legally live, and we don't want to load a 5 MB article.
        html = r.text[:200_000]
    except Exception as e:
        log.debug("og_image fetch %s: %s", article_url[:60], e)
        return False

    candidates: list[str] = []
    for m in _OG_IMAGE_RE.finditer(html):
        candidates.append(m.group(1).strip())
    for m in _OG_IMAGE_REVERSED.finditer(html):
        candidates.append(m.group(1).strip())

    for raw in candidates:
        # Resolve relative URLs against the article URL.
        if raw.startswith("//"):
            scheme = urllib.parse.urlparse(article_url).scheme or "https"
            raw = f"{scheme}:{raw}"
        elif raw.startswith("/"):
            base = urllib.parse.urlparse(article_url)
            raw = f"{base.scheme}://{base.netloc}{raw}"
        if not raw.startswith(("http://", "https://")):
            continue
        if _download(raw, dest):
            log.info("  📰 OG image acquired from %s", article_url[:50])
            return True
    return False


# ── Wikipedia / Wikimedia Commons ─────────────────────────────────
#
# Wikipedia REST API returns a summary endpoint that often includes
# a `thumbnail.source` URL. Free, no key, ~200 req/s soft cap.

_WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
_WIKI_SEARCH  = "https://en.wikipedia.org/w/rest.php/v1/search/title"


def fetch_wikipedia_image(query: str, dest: Path) -> bool:
    """Look up `query` on Wikipedia, download its summary thumbnail if any.

    Uses the title-search endpoint so we don't have to guess the exact
    article slug. The search API is unauthenticated and rate-limited
    very generously.
    """
    if not query:
        return False
    s = _session()
    try:
        r = s.get(
            _WIKI_SEARCH,
            params={"q": query[:120], "limit": 1},
            timeout=_TIMEOUT,
            headers={"Accept": "application/json"},
        )
        if r.status_code != 200:
            return False
        results = r.json().get("pages", [])
        if not results:
            return False
        page_key = results[0].get("key") or results[0].get("title")
        if not page_key:
            return False
    except Exception as e:
        log.debug("wiki_search %s: %s", query[:40], e)
        return False

    try:
        slug = urllib.parse.quote(page_key.replace(" ", "_"), safe="")
        url = _WIKI_SUMMARY.format(title=slug)
        r = s.get(url, timeout=_TIMEOUT, headers={"Accept": "application/json"})
        if r.status_code != 200:
            return False
        thumb = r.json().get("originalimage", {}) or r.json().get("thumbnail", {})
        img_url = thumb.get("source", "")
        if not img_url:
            return False
        if _download(img_url, dest):
            log.info("  📚 Wikipedia image acquired for %s", page_key[:50])
            return True
    except Exception as e:
        log.debug("wiki_summary %s: %s", query[:40], e)
    return False


# ── Openverse — Creative Commons image search ────────────────────
#
# Openverse aggregates 700M+ CC-licensed images across Wikimedia,
# Flickr, NASA, museums, etc. Public API, no auth required for the
# common-rate tier.

_OPENVERSE_API = "https://api.openverse.org/v1/images/"


def fetch_openverse_image(query: str, dest: Path,
                           license_type: str = "by-sa,by,cc0,pdm") -> bool:
    """Search Openverse for `query`, download the top result if any.

    Free, no key. We bias the search toward landscape-oriented results
    (better for vertical Short with center-crop) and exclude NSFW.
    """
    if not query or len(query) < 3:
        return False
    s = _session()
    try:
        r = s.get(
            _OPENVERSE_API,
            params={
                "q": query[:200],
                "page_size": "5",
                "license": license_type,
                "mature": "false",
                "aspect_ratio": "tall,wide",  # both work post-crop
                "size": "large",
            },
            timeout=_TIMEOUT,
            headers={"Accept": "application/json"},
        )
        if r.status_code != 200:
            return False
        items = r.json().get("results", []) or []
    except Exception as e:
        log.debug("openverse %s: %s", query[:40], e)
        return False

    for item in items:
        for key in ("url", "thumbnail"):
            img = item.get(key, "")
            if not img:
                continue
            if _download(img, dest):
                log.info("  🌐 Openverse image acquired for %s", query[:50])
                return True
    return False


# ── Unified fallback chain ───────────────────────────────────────

def fetch_any_free_image(
    article_url: str,
    query: str,
    dest: Path,
) -> bool:
    """Try every free image source in order. First success wins.

    Order is chosen by relevance × reliability:
      1. Open Graph from the article — most editorially relevant when present.
      2. Wikipedia thumbnail — clean, well-cropped, recognisable subjects.
      3. Openverse — broad coverage, less editorial but always something.
    """
    if article_url and fetch_og_image(article_url, dest):
        return True
    if query and fetch_wikipedia_image(query, dest):
        return True
    if query and fetch_openverse_image(query, dest):
        return True
    return False
