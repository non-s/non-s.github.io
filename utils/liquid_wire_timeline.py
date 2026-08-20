"""Shared audiovisual score for Liquid Wire works."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

EVENT_KINDS = ("bloom", "compression", "rupture", "tide", "stillness")
NARRATIVE_ARC_VERSION = 1


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
    return ensure_narrative_arc(events, duration, seed)


def ensure_narrative_arc(
    events: list[CreativeEvent], duration: float, seed: int = 0
) -> list[CreativeEvent]:
    """Guarantee opening, development, climax and resolution beats.

    Gemini remains free to direct the work, but malformed or dramatically flat
    plans are completed deterministically instead of silently becoming a loop.
    """
    duration = max(1.0, float(duration))
    result = [event for event in events if 0 <= event.start < duration]
    rng = np.random.default_rng(seed ^ 0x415243)

    def add(kind: str, fraction: float, length: float, intensity: float) -> None:
        result.append(CreativeEvent(
            kind=kind,
            start=round(duration * fraction, 6),
            duration=max(.5, round(duration * length, 6)),
            intensity=intensity,
            direction=float(rng.uniform(-np.pi, np.pi)),
            pitch_offset=int(rng.choice((-12, -7, 5, 7, 12))),
        ))

    if not any(event.start <= duration * .22 for event in result):
        add("tide", .08, .14, .48)
    if not any(duration * .22 < event.start < duration * .48 for event in result):
        add("compression", .32, .13, .62)
    if not any(
        duration * .48 <= event.start <= duration * .72
        and event.kind in {"rupture", "bloom"}
        and event.intensity >= .76
        for event in result
    ):
        add("rupture", .61, .10, .94)
    if not any(
        event.start >= duration * .76 and event.kind in {"stillness", "tide"}
        for event in result
    ):
        add("stillness", .84, .12, .56)
    return sorted(result, key=lambda event: (event.start, event.kind))


def audit_narrative_arc(events: list[CreativeEvent], duration: float) -> dict[str, object]:
    """Machine-readable proof that a planned timeline has a dramatic grammar."""
    duration = max(1.0, float(duration))
    criteria = {
        "opening": any(event.start <= duration * .22 for event in events),
        "development": any(duration * .22 < event.start < duration * .48 for event in events),
        "climax": any(
            duration * .48 <= event.start <= duration * .72
            and event.kind in {"rupture", "bloom"}
            and event.intensity >= .76
            for event in events
        ),
        "resolution": any(
            event.start >= duration * .76 and event.kind in {"stillness", "tide"}
            for event in events
        ),
        "variety": len({event.kind for event in events}) >= 3,
    }
    return {
        "version": NARRATIVE_ARC_VERSION,
        "passed": all(criteria.values()),
        "criteria": criteria,
        "event_count": len(events),
    }


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


def narrative_state(t: float, events: list[CreativeEvent]) -> dict[str, float]:
    """Cumulative visual memory: transformations leave a lasting trace."""
    cumulative = {kind: 0.0 for kind in EVENT_KINDS}
    for event in events:
        phase = float(np.clip((t - event.start) / max(event.duration, 1e-6), 0.0, 1.0))
        progress = phase * phase * (3.0 - 2.0 * phase)
        cumulative[event.kind] += progress * event.intensity
    metamorphosis = np.tanh(
        .52 * cumulative["bloom"] - .35 * cumulative["compression"]
        + .28 * cumulative["rupture"] + .16 * cumulative["tide"]
    )
    return {
        **cumulative,
        "metamorphosis": float(metamorphosis),
        "scar": float(np.tanh(.65 * cumulative["rupture"])),
        "settling": float(np.tanh(.55 * cumulative["stillness"])),
    }
