"""Search/suggested metadata enrichment without external calls."""

from __future__ import annotations

COMMON_SYNONYMS = {
    "octopus": ("cephalopod", "marine animal"),
    "wolf": ("canid", "pack animal"),
    "frog": ("amphibian", "wetland animal"),
    "bird": ("avian", "wild bird"),
    "shark": ("marine predator", "cartilaginous fish"),
}


def enrich_search_terms(story: dict | None = None) -> dict:
    story = story or {}
    text = " ".join(str(story.get(key) or "") for key in ("title", "hook", "script", "category")).lower()
    terms = set(story.get("yt_tags") or [])
    scientific = str(story.get("scientific_name") or (story.get("gbif") or {}).get("scientificName") or "").strip()
    if scientific:
        terms.add(scientific)
    for key, values in COMMON_SYNONYMS.items():
        if key in text:
            terms.add(key)
            terms.update(values)
    category = str(story.get("category") or "").strip()
    if category:
        terms.add(category.lower())
    return {
        "search_terms": sorted(str(term).strip().lower() for term in terms if str(term).strip())[:15],
        "scientific_name": scientific,
        "internal_link_hint": str(story.get("series") or category or "Wild Brief"),
    }
