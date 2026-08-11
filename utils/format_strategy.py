"""Human-centred editorial contracts for vertical and horizontal video.

The formats serve different viewer needs. These contracts are stored with each
asset so analytics can evaluate the correct promise instead of optimizing all
videos for a single attention metric.
"""

from __future__ import annotations


def format_strategy(*, kind: str, duration: int, mood: str, scene: str) -> dict[str, str]:
    """Return the editorial role and quality contract for one video format."""
    animal = "cat" if "cat" in scene.lower() or "kitten" in scene.lower() else "dog"
    if kind == "long":
        return {
            "orientation": "horizontal 16:9",
            "viewer_need": "an unhurried companion for focus, rest or a quiet room",
            "opening_contract": "establish the setting gently; do not use a disruptive hook",
            "rhythm": "slow visual changes, clear chapters and an honest calm promise",
            "success_signal": "average view duration and returning viewers, interpreted with viewer feedback",
            "community_bridge": "invite viewers to name the ritual or atmosphere they want next",
            "session_label": f"{mood or 'calm'} {animal} companion session",
            "duration_seconds": str(duration),
        }
    return {
        "orientation": "vertical 9:16",
        "viewer_need": "a small, self-contained moment of delight or calm",
        "opening_contract": "show the real animal moment immediately and match the title honestly",
        "rhythm": "one clear emotional beat, concise captions and no artificial urgency",
        "success_signal": "viewed-versus-swiped behaviour, completion and meaningful comments",
        "community_bridge": "ask one optional, specific question that lets viewers share their own ritual",
        "session_label": f"{mood or 'gentle'} {animal} discovery moment",
        "duration_seconds": str(duration),
    }
