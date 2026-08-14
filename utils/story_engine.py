"""Original series and audience-participation system for Liquid Wire."""

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
        "id": "wireframe-dreams",
        "name": "Wireframe Dreams",
        "visual_direction": "slow liquid wireframe motion, soft glow, hypnotic geometry",
        "interaction": "Which should return next: Wireframe Dreams or Organic Bloom?",
        "community_prompt": "Comment WIREFRAME or ORGANIC so the next piece is chosen by the community.",
    },
    {
        "id": "organic-bloom",
        "name": "Organic Bloom",
        "visual_direction": "coral growth and L-system branching, living procedural forms",
        "interaction": "What kind of organic form do you want to see next?",
        "community_prompt": "Tell us one organic shape you'd like to see grow.",
    },
    {
        "id": "crystal-resonance",
        "name": "Crystal Resonance",
        "visual_direction": "geometric lattices, refraction patterns, precise angular beauty",
        "interaction": "Team geometric or team organic today?",
        "community_prompt": "Comment GEOMETRIC or ORGANIC to choose a future Crystal session.",
    },
    {
        "id": "fluid-morphogenesis",
        "name": "Fluid Morphogenesis",
        "visual_direction": "wave propagation, fluid deformation, slow liquid transformation",
        "interaction": "What should the next fluid form feel like?",
        "community_prompt": "Leave one word for the next fluid piece: WAVE, DROP, or FLOW.",
    },
    {
        "id": "nebula-birth",
        "name": "Nebula Birth",
        "visual_direction": "particle clouds, cosmic drift, deep space ambient",
        "interaction": "Which cosmic form should we generate next?",
        "community_prompt": "Comment NEBULA or PARTICLE to help choose the next cosmic piece.",
    },
    {
        "id": "geometric-drift",
        "name": "Geometric Drift",
        "visual_direction": "slow rotation, shifting polyhedra, clean mathematical motion",
        "interaction": "What geometry should drift next?",
        "community_prompt": "Suggest one shape: CUBE, SPHERE, TORUS, or KNOT.",
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
        "mood": mood or "ambient",
        "micro_story": f"{hook} becomes a small moment inside {series['name']}.",
        "ritual_id": ritual["id"],
        "ritual_name": ritual["name"],
        "viewer_intent": ritual["viewer_intent"],
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
