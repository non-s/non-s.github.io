"""Collect free, attributable research and media leads for human review."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.gbif_research import species_card
from utils.openverse_catalog import search_open_images
from utils.paths import data_dir

log = logging.getLogger(__name__)
QUERIES = ("domestic cat", "domestic dog", "rabbit", "capybara", "parrot")


def collect_open_research() -> dict[str, object]:
    species, media = [], {}
    for query in QUERIES:
        try:
            species.append(species_card(query))
        except Exception as exc:
            log.warning("GBIF unavailable for %s: %s", query, exc)
        try:
            media[query] = search_open_images(query)
        except Exception as exc:
            log.warning("Openverse unavailable for %s: %s", query, exc)
    return {"generated_at": datetime.now(UTC).isoformat(), "species_research": species, "media_candidates": media}


def main() -> int:
    output = data_dir() / "open_research_catalog.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(collect_open_research(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Open research catalogue: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
