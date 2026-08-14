"""Structured creative briefs for every Liquid Wire asset.

The brief makes the editorial intent explicit before publication, so analytics
can later distinguish a repeatable series from a one-off generated video.
"""

from __future__ import annotations

from utils.format_strategy import format_strategy


def build_editorial_brief(*, scene: str, mood: str, kind: str, duration: int, hook: str) -> dict[str, str]:
    """Return a concise, factual creative brief suitable for metadata storage."""
    scene_lower = scene.lower()
    is_long = kind == "long"
    if any(word in scene_lower for word in ("wireframe", "wire", "geometric", "crystal")):
        pillar = "geometric-generative"
    elif any(word in scene_lower for word in ("organic", "coral", "fluid", "growth")):
        pillar = "organic-generative"
    elif any(word in scene_lower for word in ("nebula", "particle", "cloud")):
        pillar = "cosmic-generative"
    else:
        pillar = "ambient-generative"
    strategy = format_strategy(kind=kind, duration=duration, mood=mood, scene=scene)
    return {
        "pillar": pillar,
        "audience": "people who enjoy generative art with original procedural music",
        "creative_angle": f"{scene.strip() or 'procedural'} paired with {mood or 'ambient'} music",
        "hook": hook,
        "format_role": "retention session" if is_long else "discovery and funnel entry",
        "primary_metric": "average view duration" if is_long else "stayed to watch",
        "funnel_destination": "playlist and matching long-form" if not is_long else "playlist continuation",
        "duration_seconds": str(duration),
        "orientation": strategy["orientation"],
        "viewer_need": strategy["viewer_need"],
        "opening_contract": strategy["opening_contract"],
        "rhythm": strategy["rhythm"],
        "success_signal": strategy["success_signal"],
    }
