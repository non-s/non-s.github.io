"""License-first discovery of open media candidates; never auto-downloads."""

from __future__ import annotations

import os

import requests

OPENVERSE_IMAGES_URL = "https://api.openverse.org/v1/images/"
ALLOWED_LICENSES = {"cc0", "pdm", "by", "by-sa"}


def search_open_images(query: str, *, page_size: int = 5, timeout: int = 20) -> list[dict[str, str]]:
    """Find reviewable image candidates compatible with a commercial catalogue."""
    headers = {"User-Agent": "LiquidWire/1.0 (open media catalogue)"}
    token = os.environ.get("OPENVERSE_ACCESS_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    params: dict[str, str | int] = {"q": query, "page_size": page_size}
    response = requests.get(OPENVERSE_IMAGES_URL, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    candidates: list[dict[str, str]] = []
    for item in response.json().get("results", []):
        license_code = str(item.get("license") or "").lower()
        if license_code not in ALLOWED_LICENSES:
            continue
        source_url = str(item.get("foreign_landing_url") or item.get("url") or "")
        if not source_url:
            continue
        candidates.append(
            {
                "title": str(item.get("title") or "Untitled"),
                "creator": str(item.get("creator") or "Unknown creator"),
                "license": license_code,
                "license_url": str(item.get("license_url") or ""),
                "source_url": source_url,
                "provider": str(item.get("source") or "Openverse"),
                "review_rule": "Manual visual and licence review required before download or publication.",
            }
        )
    return candidates
