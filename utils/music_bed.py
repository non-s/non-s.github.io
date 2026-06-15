"""Stable no-op background music hook for Shorts.

Wild Brief no longer uses external music sources. The generator still calls
this module so the production pipeline keeps one stable integration point,
but the hook intentionally returns the original narration file.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

MUSIC_ENABLED = os.environ.get("MUSIC_BED_ENABLED", "0").strip().lower() not in {"0", "false", "no", "off"}


def _mood_for_story(story: dict) -> str:
    """Keep the mood classifier for analytics/tests without sourcing music."""
    if story.get("breaking"):
        return "tense"
    sentiment = (story.get("sentiment") or "").lower()
    if sentiment == "negative":
        return "tense"
    cat = (story.get("category") or "").lower()
    if cat in ("ocean", "birds", "wildlife"):
        return "reflective"
    return "upbeat"


def add_music_bed(tts_path: Path, story: dict, tmp_dir: Path) -> Path:
    """Return the narration unchanged; external music beds are unsupported."""
    if MUSIC_ENABLED:
        log.info("  Music bed skipped: no external music source is configured")
    story.setdefault("music_bed_track", {})
    return tts_path
