"""Free animal metadata and thumbnail enrichment."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)
_TIMEOUT = 15
_CACHE_DIR = Path(os.environ.get("ANIMAL_ENRICHMENT_CACHE_DIR", "_data/enrichment_cache"))
_CACHE_TTL_S = 86400 * 14
_GBIF_API = "https://api.gbif.org/v1/species/match"
_COMMONS_API = "https://commons.wikimedia.org/w/api.php"
_USER_AGENT = "WildBrief-Bot/4.0 (+https://non-s.github.io)"


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT})
    return session


def _cache_path(kind: str, subject: str) -> Path:
    clean = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")[:60] or "unknown"
    return _CACHE_DIR / f"{kind}-{clean}.json"


def _cached(kind: str, subject: str) -> dict | None:
    path = _cache_path(kind, subject)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("value") if time.time() - float(data.get("ts", 0)) < _CACHE_TTL_S else None
    except Exception:
        return None


def _store(kind: str, subject: str, value: dict) -> dict:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(kind, subject).write_text(
            json.dumps({"ts": time.time(), "value": value}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        log.debug("enrichment cache write failed: %s", exc)
    return value


def gbif_species_context(subject: str) -> dict:
    """Return a compact best-effort GBIF taxonomy match."""
    if not subject:
        return {}
    cached = _cached("gbif", subject)
    if cached is not None:
        return cached
    try:
        response = _session().get(_GBIF_API, params={"name": subject}, timeout=_TIMEOUT)
        if response.status_code != 200:
            return {}
        data = response.json()
        if str(data.get("matchType") or "").upper() == "NONE":
            return _store("gbif", subject, {})
        value = {
            "source": "GBIF",
            "usage_key": data.get("usageKey"),
            "scientific_name": data.get("scientificName") or data.get("canonicalName") or "",
            "canonical_name": data.get("canonicalName") or "",
            "rank": data.get("rank") or "",
            "kingdom": data.get("kingdom") or "",
            "family": data.get("family") or "",
            "confidence": data.get("confidence"),
        }
        return _store("gbif", subject, {k: v for k, v in value.items() if v not in ("", None)})
    except Exception as exc:
        log.debug("GBIF lookup failed: %s", exc)
        return {}


def _commons_reusable(license_name: str) -> bool:
    value = (license_name or "").lower()
    if any(term in value for term in ("-nc", " nc ", "-nd", " nd ")):
        return False
    return any(term in value for term in ("public domain", "cc0", "cc by", "cc-by"))


def commons_image(subject: str) -> dict:
    """Find one commercially reusable Commons image for a subject."""
    if not subject:
        return {}
    cached = _cached("commons", subject)
    if cached is not None:
        return cached
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": subject,
        "gsrnamespace": "6",
        "gsrlimit": "8",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": "1280",
    }
    try:
        response = _session().get(_COMMONS_API, params=params, timeout=_TIMEOUT)
        if response.status_code != 200:
            return {}
        pages = (response.json().get("query") or {}).get("pages") or {}
        for page in pages.values():
            info = ((page.get("imageinfo") or [{}])[0]) or {}
            metadata = info.get("extmetadata") or {}
            license_name = str((metadata.get("LicenseShortName") or {}).get("value") or "")
            image_url = str(info.get("thumburl") or info.get("url") or "")
            if not image_url or not _commons_reusable(license_name):
                continue
            value = {
                "source": "Wikimedia Commons",
                "image_url": image_url,
                "page_url": str(info.get("descriptionurl") or ""),
                "license": license_name,
                "artist": re.sub(r"<[^>]+>", "", str((metadata.get("Artist") or {}).get("value") or "")).strip(),
                "title": str(page.get("title") or ""),
            }
            return _store("commons", subject, value)
    except Exception as exc:
        log.debug("Commons lookup failed: %s", exc)
    return _store("commons", subject, {})


def enrich_subject(subject: str) -> dict:
    return {"gbif": gbif_species_context(subject), "commons": commons_image(subject)}


def taxonomy_prompt(enrichment: dict) -> str:
    gbif = enrichment.get("gbif") or {}
    if not gbif:
        return ""
    return (
        "GBIF taxonomy hint (use only to confirm the visible subject, never invent facts): "
        f"scientific_name={gbif.get('scientific_name', '')}; "
        f"family={gbif.get('family', '')}; rank={gbif.get('rank', '')}."
    )


def download_commons_image(story: dict, dest: Path, max_bytes: int = 8 * 1024 * 1024) -> bool:
    url = str(story.get("commons_image_url") or "").strip()
    if not url:
        return False
    try:
        response = _session().get(url, timeout=_TIMEOUT)
        body = response.content
        if response.status_code != 200 or len(body) < 5 * 1024 or len(body) > max_bytes:
            return False
        dest.write_bytes(body)
        return True
    except Exception as exc:
        log.debug("Commons image download failed: %s", exc)
        return False
