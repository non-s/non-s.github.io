"""Internet Archive public-domain media discovery helpers.

The Archive is useful as a primary visual source and a supplemental
sound/music source, but uploads there are not automatically safe. This
module only admits items whose metadata carries explicit public-domain,
CC0, or U.S. Government evidence, then returns direct downloadable files
with provenance attached.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

log = logging.getLogger(__name__)

ADVANCED_SEARCH_URL = "https://archive.org/advancedsearch.php"
METADATA_URL = "https://archive.org/metadata/{identifier}"
DOWNLOAD_URL = "https://archive.org/download/{identifier}/{filename}"
USER_AGENT = os.environ.get("INTERNET_ARCHIVE_USER_AGENT", "WildBrief-Bot/4.0")

ARCHIVE_CACHE_DIR = Path(os.environ.get("ARCHIVE_AUDIO_CACHE_DIR", "_data/archive_audio_cache"))
ARCHIVE_AUDIO_MAX_BYTES = int(os.environ.get("ARCHIVE_AUDIO_MAX_BYTES", str(20 * 1024 * 1024)))
ARCHIVE_AUDIO_MIN_BYTES = int(os.environ.get("ARCHIVE_AUDIO_MIN_BYTES", str(25 * 1024)))
ARCHIVE_VIDEO_MAX_BYTES = int(os.environ.get("ARCHIVE_VIDEO_MAX_BYTES", str(90 * 1024 * 1024)))
ARCHIVE_VIDEO_MIN_BYTES = int(os.environ.get("ARCHIVE_VIDEO_MIN_BYTES", str(50 * 1024)))

PUBLIC_DOMAIN_MARKERS = (
    "creativecommons.org/publicdomain/zero",
    "creativecommons.org/publicdomain/mark",
    "creativecommons.org/publicdomain/",
    "publicdomain",
    "public domain",
    "cc0",
    "pdm",
    "usgov",
    "u.s. government",
    "united states government",
)
RIGHTS_BLOCK_MARKERS = (
    "creativecommons.org/licenses/by-nc",
    "creativecommons.org/licenses/by-nd",
    "non-commercial",
    "noncommercial",
    "no derivatives",
    "no-derivatives",
    "all rights reserved",
    "permission required",
    "with permission",
    "no known copyright",
)

SAFE_AUDIO_SUFFIXES = (".mp3", ".ogg", ".oga", ".wav", ".flac", ".m4a", ".aac")
SAFE_AUDIO_FORMAT_HINTS = ("mp3", "ogg", "vorbis", "wave", "flac", "aac", "mpeg4 audio")
SAFE_VIDEO_SUFFIXES = (".mp4", ".m4v", ".mov")
SAFE_VIDEO_FORMAT_HINTS = ("mpeg4", "h.264", "h264", "quicktime")
UNSAFE_VIDEO_NAME_HINTS = ("thumb", "thumbnail", "sprite", "sample", "metadata")


@dataclass(frozen=True)
class ArchiveAudioAsset:
    identifier: str
    file_name: str
    title: str
    creator: str
    url: str
    source_url: str
    license: str
    license_evidence: str
    mediatype: str = "audio"
    mood: str = "upbeat"

    def to_manifest_row(self, asset_path: str = "") -> dict[str, Any]:
        row = asdict(self)
        row.update(
            {
                "name": self.title or self.identifier,
                "asset_path": asset_path,
                "safe_for_short": True,
                "source": "Internet Archive",
            }
        )
        return row


@dataclass(frozen=True)
class ArchiveVideoAsset:
    identifier: str
    file_name: str
    title: str
    creator: str
    url: str
    source_url: str
    license: str
    license_evidence: str
    mediatype: str = "movies"
    collection: str = ""
    description: str = ""
    downloads: int = 0
    width: int = 0
    height: int = 0
    duration_s: float = 0.0

    def to_manifest_row(self, asset_path: str = "") -> dict[str, Any]:
        row = asdict(self)
        row.update(
            {
                "name": self.title or self.identifier,
                "asset_path": asset_path,
                "safe_for_short": True,
                "source": "Internet Archive",
                "rights_policy": "explicit_public_domain_cc0_or_usgov_only",
            }
        )
        return row


def _first(value: Any) -> str:
    if isinstance(value, list):
        return str(value[0] if value else "")
    return str(value or "")


def _join_values(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if isinstance(value, list):
            parts.extend(str(item or "") for item in value)
        else:
            parts.append(str(value or ""))
    return " ".join(parts)


def _contains_public_domain_marker(*values: Any) -> str:
    haystack = _join_values(*values)
    lower = haystack.lower()
    for marker in PUBLIC_DOMAIN_MARKERS:
        if marker in lower:
            return marker
    return ""


def rights_block_reason(metadata: dict[str, Any]) -> str:
    haystack = _join_values(
        metadata.get("licenseurl"),
        metadata.get("rights"),
        metadata.get("usage"),
        metadata.get("copyright"),
        metadata.get("description"),
    ).lower()
    for marker in RIGHTS_BLOCK_MARKERS:
        if marker in haystack:
            return marker
    return ""


def public_domain_evidence(metadata: dict[str, Any]) -> str:
    """Return the matching license marker, or empty string when unsafe."""
    if rights_block_reason(metadata):
        return ""
    return _contains_public_domain_marker(
        metadata.get("licenseurl"),
        metadata.get("rights"),
        metadata.get("usage"),
        metadata.get("copyright"),
        metadata.get("description"),
    )


def is_public_domain_item(metadata: dict[str, Any]) -> bool:
    return bool(public_domain_evidence(metadata))


def _audio_file_score(file_row: dict[str, Any]) -> int:
    name = str(file_row.get("name") or "")
    fmt = str(file_row.get("format") or "").lower()
    suffix = Path(name).suffix.lower()
    if suffix not in SAFE_AUDIO_SUFFIXES and not any(hint in fmt for hint in SAFE_AUDIO_FORMAT_HINTS):
        return -1
    score = 10
    if suffix == ".mp3" or "mp3" in fmt:
        score += 20
    if str(file_row.get("source") or "").lower() == "original":
        score += 5
    try:
        size = int(file_row.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    if size:
        score += min(10, size // (1024 * 1024))
    return score


def choose_audio_file(files: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [(row, _audio_file_score(row)) for row in files if isinstance(row, dict)]
    candidates = [(row, score) for row, score in candidates if score >= 0]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[1], reverse=True)[0][0]


def _int_value(value: Any) -> int:
    try:
        return int(float(str(value or "0")))
    except (TypeError, ValueError):
        return 0


def _float_value(value: Any) -> float:
    try:
        return float(str(value or "0"))
    except (TypeError, ValueError):
        return 0.0


def _video_file_score(file_row: dict[str, Any]) -> int:
    name = str(file_row.get("name") or "")
    lower_name = name.lower()
    if any(hint in lower_name for hint in UNSAFE_VIDEO_NAME_HINTS):
        return -1
    fmt = str(file_row.get("format") or "").lower()
    suffix = Path(name).suffix.lower()
    if suffix not in SAFE_VIDEO_SUFFIXES and not any(hint in fmt for hint in SAFE_VIDEO_FORMAT_HINTS):
        return -1
    size = _int_value(file_row.get("size"))
    if size and (size < ARCHIVE_VIDEO_MIN_BYTES or size > ARCHIVE_VIDEO_MAX_BYTES):
        return -1
    score = 10
    if suffix == ".mp4" or "mpeg4" in fmt or "h.264" in fmt or "h264" in fmt:
        score += 25
    width = _int_value(file_row.get("width"))
    height = _int_value(file_row.get("height"))
    if height >= width and height:
        score += 20
    if height >= 720 or width >= 720:
        score += 10
    if str(file_row.get("source") or "").lower() == "original":
        score += 5
    if size:
        score += min(15, size // (2 * 1024 * 1024))
    return score


def choose_video_file(files: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [(row, _video_file_score(row)) for row in files if isinstance(row, dict)]
    candidates = [(row, score) for row, score in candidates if score >= 0]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[1], reverse=True)[0][0]


def advanced_search_audio(query: str, *, rows: int = 20, session=requests) -> list[str]:
    """Search Archive metadata and return item identifiers only."""
    q = f"mediatype:audio AND ({query}) AND licenseurl:*publicdomain*"
    params = {
        "q": q,
        "fl[]": ["identifier"],
        "rows": str(max(1, min(rows, 50))),
        "page": "1",
        "output": "json",
        "sort[]": "downloads desc",
    }
    try:
        resp = session.get(ADVANCED_SEARCH_URL, params=params, timeout=30, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        docs = ((resp.json() or {}).get("response") or {}).get("docs") or []
    except Exception as exc:
        log.debug("internet_archive search failed: %s", exc)
        return []
    return [str(doc.get("identifier") or "") for doc in docs if doc.get("identifier")]


def advanced_search_video(query: str, *, rows: int = 20, session=requests) -> list[str]:
    """Search Archive video metadata and return conservative item identifiers."""
    query_variants = (
        f"mediatype:movies AND ({query}) AND licenseurl:*publicdomain*",
        f'mediatype:movies AND ({query}) AND "U.S. Government"',
        f'mediatype:movies AND ({query}) AND "United States Government"',
        f"mediatype:movies AND collection:prelinger AND ({query})",
    )
    wanted = max(1, min(rows, 50))
    seen: set[str] = set()
    out: list[str] = []
    for q in query_variants:
        params = {
            "q": q,
            "fl[]": ["identifier", "title", "downloads", "date", "collection", "licenseurl", "rights"],
            "rows": str(wanted),
            "page": "1",
            "output": "json",
            "sort[]": "downloads desc",
        }
        try:
            resp = session.get(ADVANCED_SEARCH_URL, params=params, timeout=30, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            docs = ((resp.json() or {}).get("response") or {}).get("docs") or []
        except Exception as exc:
            log.debug("internet_archive video search failed: %s", exc)
            continue
        for doc in docs:
            identifier = str(doc.get("identifier") or "")
            if identifier and identifier not in seen:
                out.append(identifier)
                seen.add(identifier)
            if len(out) >= wanted:
                return out
    return out


def fetch_metadata(identifier: str, *, session=requests) -> dict[str, Any] | None:
    try:
        resp = session.get(
            METADATA_URL.format(identifier=quote(identifier, safe="")), timeout=30, headers={"User-Agent": USER_AGENT}
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        log.debug("internet_archive metadata failed for %s: %s", identifier, exc)
        return None
    return payload if isinstance(payload, dict) else None


def asset_from_metadata(payload: dict[str, Any], *, mood: str = "upbeat") -> ArchiveAudioAsset | None:
    metadata = payload.get("metadata") or {}
    files = payload.get("files") or []
    if not isinstance(metadata, dict) or not is_public_domain_item(metadata):
        return None
    identifier = str(metadata.get("identifier") or payload.get("item") or "")
    if not identifier:
        return None
    audio_file = choose_audio_file(files if isinstance(files, list) else [])
    if not audio_file:
        return None
    file_name = str(audio_file.get("name") or "")
    evidence = public_domain_evidence(metadata)
    encoded_identifier = quote(identifier, safe="")
    encoded_file = quote(file_name, safe="/")
    return ArchiveAudioAsset(
        identifier=identifier,
        file_name=file_name,
        title=_first(metadata.get("title")) or identifier,
        creator=_first(metadata.get("creator")),
        url=DOWNLOAD_URL.format(identifier=encoded_identifier, filename=encoded_file),
        source_url=f"https://archive.org/details/{encoded_identifier}",
        license=_first(metadata.get("licenseurl") or metadata.get("rights") or evidence),
        license_evidence=evidence,
        mediatype=_first(metadata.get("mediatype")) or "audio",
        mood=mood,
    )


def video_asset_from_metadata(payload: dict[str, Any]) -> ArchiveVideoAsset | None:
    metadata = payload.get("metadata") or {}
    files = payload.get("files") or []
    if not isinstance(metadata, dict) or not is_public_domain_item(metadata):
        return None
    identifier = str(metadata.get("identifier") or payload.get("item") or "")
    if not identifier:
        return None
    video_file = choose_video_file(files if isinstance(files, list) else [])
    if not video_file:
        return None
    file_name = str(video_file.get("name") or "")
    evidence = public_domain_evidence(metadata)
    encoded_identifier = quote(identifier, safe="")
    encoded_file = quote(file_name, safe="/")
    collection = metadata.get("collection")
    if isinstance(collection, list):
        collection_text = ", ".join(str(item) for item in collection[:6])
    else:
        collection_text = str(collection or "")
    return ArchiveVideoAsset(
        identifier=identifier,
        file_name=file_name,
        title=_first(metadata.get("title")) or identifier,
        creator=_first(metadata.get("creator")),
        url=DOWNLOAD_URL.format(identifier=encoded_identifier, filename=encoded_file),
        source_url=f"https://archive.org/details/{encoded_identifier}",
        license=_first(metadata.get("licenseurl") or metadata.get("rights") or evidence),
        license_evidence=evidence,
        mediatype=_first(metadata.get("mediatype")) or "movies",
        collection=collection_text,
        description=_first(metadata.get("description"))[:500],
        downloads=_int_value(metadata.get("downloads") or payload.get("downloads")),
        width=_int_value(video_file.get("width")),
        height=_int_value(video_file.get("height")),
        duration_s=_float_value(video_file.get("length") or metadata.get("runtime") or metadata.get("length")),
    )


def discover_public_domain_audio(
    query: str, *, mood: str = "upbeat", rows: int = 20, session=requests
) -> list[ArchiveAudioAsset]:
    assets: list[ArchiveAudioAsset] = []
    for identifier in advanced_search_audio(query, rows=rows, session=session):
        payload = fetch_metadata(identifier, session=session)
        if not payload:
            continue
        asset = asset_from_metadata(payload, mood=mood)
        if asset:
            assets.append(asset)
    return assets


def discover_public_domain_videos(query: str, *, rows: int = 20, session=requests) -> list[ArchiveVideoAsset]:
    assets: list[ArchiveVideoAsset] = []
    for identifier in advanced_search_video(query, rows=rows, session=session):
        payload = fetch_metadata(identifier, session=session)
        if not payload:
            continue
        asset = video_asset_from_metadata(payload)
        if asset:
            assets.append(asset)
    return assets


def cache_path_for_asset(asset: ArchiveAudioAsset, cache_dir: Path | None = None) -> Path:
    cache_dir = cache_dir or ARCHIVE_CACHE_DIR
    suffix = Path(asset.file_name).suffix.lower() or ".mp3"
    digest = hashlib.sha256(f"{asset.identifier}:{asset.file_name}".encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{digest}{suffix}"


def download_asset(asset: ArchiveAudioAsset, *, cache_dir: Path | None = None, session=requests) -> Path | None:
    cache_dir = cache_dir or ARCHIVE_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_path_for_asset(asset, cache_dir)
    if dest.exists() and dest.stat().st_size >= ARCHIVE_AUDIO_MIN_BYTES:
        return dest
    try:
        resp = session.get(asset.url, timeout=45, stream=True, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        total = 0
        chunks: list[bytes] = []
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > ARCHIVE_AUDIO_MAX_BYTES:
                log.debug("internet_archive asset too large: %s", asset.url)
                return None
            chunks.append(chunk)
    except Exception as exc:
        log.debug("internet_archive download failed for %s: %s", asset.identifier, exc)
        return None
    body = b"".join(chunks)
    if len(body) < ARCHIVE_AUDIO_MIN_BYTES:
        return None
    dest.write_bytes(body)
    return dest
