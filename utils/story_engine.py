"""Original series and audience-participation system for Pata Jazz."""

from __future__ import annotations

import json
import random
from datetime import date
from pathlib import Path

from utils.community_rituals import ritual_for_date
from utils.paths import data_dir
from utils.state_lock import state_lock

_MEMORY_LIMIT = 16

_SERIES = (
    {
        "id": "window-seat-sessions",
        "name": "Window Seat Sessions",
        "visual_direction": "soft daylight, a quiet pause by a window, unhurried framing",
        "interaction": "Which should return next: Window Seat or Golden Hour?",
        "community_prompt": "Comment WINDOW or GOLDEN so the next session is chosen by the community.",
    },
    {
        "id": "tiny-rituals",
        "name": "Tiny Rituals",
        "visual_direction": "a small everyday pet ritual, intimate details, gentle pacing",
        "interaction": "What is your pet's tiny daily ritual?",
        "community_prompt": "Tell us one tiny ritual your pet never skips.",
    },
    {
        "id": "golden-hour-paws",
        "name": "Golden Hour Paws",
        "visual_direction": "warm light, playful calm, a brighter late-day mood",
        "interaction": "Team cat jazz or team dog jazz today?",
        "community_prompt": "Comment CAT or DOG to choose a future Golden Hour session.",
    },
    {
        "id": "after-rain-room",
        "name": "After-Rain Room",
        "visual_direction": "cozy indoor atmosphere, reflective pacing, soft instrumental texture",
        "interaction": "What should the next cozy room feel like?",
        "community_prompt": "Leave one word for the next room: SUN, RAIN, or NIGHT.",
    },
)


def _memory_file() -> Path:
    return data_dir() / "story_memory.json"


def _recent_series() -> list[str]:
    try:
        data = json.loads(_memory_file().read_text(encoding="utf-8"))
        return [str(item) for item in data if isinstance(item, str)] if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def choose_story_card(scene: str, mood: str, hook: str) -> dict[str, str]:
    """Choose a non-recent proprietary series and a concrete interaction cue."""
    recent = set(_recent_series()[:4])
    candidates = [series for series in _SERIES if series["id"] not in recent] or list(_SERIES)
    series = random.choice(candidates)
    ritual = ritual_for_date(date.today())
    return {
        **series,
        "scene": scene,
        "mood": mood or "cozy",
        "micro_story": f"{hook} becomes a small moment inside {series['name']}.",
        "ritual_id": ritual["id"],
        "ritual_name": ritual["name"],
        "viewer_intent": ritual["viewer_intent"],
        # A weekly ritual creates continuity while the series prompt keeps
        # individual videos distinct; never ask viewers to engage compulsively.
        "community_prompt": ritual["community_prompt"],
    }


def record_story_card(card: dict[str, str]) -> None:
    """Persist series rotation only after the asset was successfully generated."""
    series_id = card.get("id", "")
    if not series_id:
        return
    path = _memory_file()
    with state_lock(path):
        recent = _recent_series()
        updated = [series_id, *(item for item in recent if item != series_id)][:_MEMORY_LIMIT]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
