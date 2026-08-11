"""Small, attributable GBIF research layer for animal editorial ideas."""

from __future__ import annotations

import requests

GBIF_MATCH_URL = "https://api.gbif.org/v2/species/match"


def species_card(name: str, *, timeout: int = 20) -> dict[str, str]:
    """Return conservative taxonomy data; never invent behavioural claims."""
    response = requests.get(GBIF_MATCH_URL, params={"name": name}, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    return {
        "query": name,
        "scientific_name": str(data.get("scientificName") or ""),
        "canonical_name": str(data.get("canonicalName") or ""),
        "rank": str(data.get("rank") or ""),
        "status": str(data.get("status") or ""),
        "source": "GBIF Backbone Taxonomy",
        "source_url": "https://www.gbif.org/",
        "editorial_rule": (
            "Use this as a cited research lead; verify any behavioural or welfare claim "
            "with an appropriate primary source."
        ),
    }
