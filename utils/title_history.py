"""
utils/title_history.py — Track titles already used by the channel so we
can avoid publishing duplicates.

YouTube's algorithm and search ranking both penalize channels that upload
many videos with the same title. The generator scripts call
`select_title()` after `generate_video_copy()` / `generate_animal_short_copy()`
to pick the best variant that has not been used before, falling back to
the first variant (usually the AI's primary title) only if every variant
is exhausted.

Storage is read-only from `_data/upload_intents.jsonl`, so no new state
file is needed. The history includes every title ever prepared or uploaded,
weighted equally: a title prepared but not yet uploaded still counts as
"used" so we don't queue the same title twice.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_INTENTS_PATH = Path(os.environ.get("UPLOAD_INTENTS_PATH", "_data/upload_intents.jsonl"))


def _normalize(title: str) -> str:
    """Strip whitespace and lower-case for stable comparison."""
    return title.strip().lower()


def load_titles(path: Path = _INTENTS_PATH) -> set[str]:
    """Return the normalized set of titles already present in the ledger."""
    titles: set[str] = set()
    if not path.exists():
        return titles
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            title = entry.get("title")
            if isinstance(title, str) and title.strip():
                titles.add(_normalize(title))
    except Exception as exc:
        log.warning("title_history load failed: %s", exc)
    return titles


def select_title(variants: list[str], used: set[str] | None = None, path: Path = _INTENTS_PATH) -> str:
    """Return the first variant not already in `used`.

    If `used` is None, it is loaded from `path`. If every variant is
    already used, the last variant is returned anyway (never block a run
    because the history is full).
    """
    if used is None:
        used = load_titles(path)
    for variant in variants:
        if _normalize(variant) not in used:
            return variant
    log.warning("All %d title variants already used; returning the last one.", len(variants))
    return variants[-1] if variants else ""


def is_used(title: str, used: set[str] | None = None, path: Path = _INTENTS_PATH) -> bool:
    """Check whether a title already exists in the ledger."""
    if used is None:
        used = load_titles(path)
    return _normalize(title) in used
