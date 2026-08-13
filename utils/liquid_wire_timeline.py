"""Shared audiovisual score for Liquid Wire works."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

EVENT_KINDS = ("bloom", "compression", "rupture", "tide", "stillness")


@dataclass(frozen=True)
class CreativeEvent:
    kind: str
    start: float
    duration: float
    intensity: float
    direction: float
    pitch_offset: int

    def to_dict(self) -> dict:
        return asdict(self)


def build_timeline(seed: int, duration: float, music: dict) -> list[CreativeEvent]:
    """Create a deterministic dramatic arc aligned to musical bars."""
    rng = np.random.default_rng(seed ^ 0x4C4951554944)
    bar = float(music["beat_seconds"]) * int(music["meter"])
    event_count = max(3, min(12, round(duration / max(4.0, bar * 2.2))))
    anchors = np.linspace(duration * 0.08, duration * 0.88, event_count)
    events: list[CreativeEvent] = []
    previous_kind = ""
    for index, anchor in enumerate(anchors):
        choices = [kind for kind in EVENT_KINDS if kind != previous_kind]
        kind = str(rng.choice(choices))
        previous_kind = kind
        snapped = round(float(anchor) / bar) * bar
        start = max(0.25, min(duration - 0.5, snapped + float(rng.uniform(-0.12, 0.12)) * bar))
        arc = np.sin(np.pi * (index + 1) / (event_count + 1))
        events.append(
            CreativeEvent(
                kind=kind,
                start=start,
                duration=float(rng.uniform(0.75, 1.8) * bar),
                intensity=float(rng.uniform(0.38, 0.72) + 0.24 * arc),
                direction=float(rng.uniform(-np.pi, np.pi)),
                pitch_offset=int(rng.choice((-12, -7, -5, 5, 7, 12))),
            )
        )
    return events


def event_envelope(t: float | np.ndarray, event: CreativeEvent) -> float | np.ndarray:
    """Smooth attack/release envelope with no discontinuity at event edges."""
    phase = (np.asarray(t) - event.start) / max(event.duration, 1e-6)
    active = (phase >= 0.0) & (phase <= 1.0)
    envelope = np.where(active, np.sin(np.pi * np.clip(phase, 0.0, 1.0)) ** 2, 0.0)
    if np.ndim(envelope) == 0:
        return float(envelope)
    return envelope


def visual_state(t: float, events: list[CreativeEvent]) -> dict[str, float]:
    state = {kind: 0.0 for kind in EVENT_KINDS}
    direction_x = 0.0
    direction_y = 0.0
    for event in events:
        energy = float(event_envelope(t, event)) * event.intensity
        state[event.kind] += energy
        direction_x += energy * float(np.cos(event.direction))
        direction_y += energy * float(np.sin(event.direction))
    state["direction_x"] = direction_x
    state["direction_y"] = direction_y
    state["total"] = sum(state[kind] for kind in EVENT_KINDS)
    return state
