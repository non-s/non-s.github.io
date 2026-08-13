"""Deterministic sectional composer for original Liquid Wire scores."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from utils.liquid_wire_timeline import CreativeEvent

MODES = {
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "aeolian": (0, 2, 3, 5, 7, 8, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
}
PROGRESSIONS = (
    (0, 5, 3, 6),
    (0, 3, 6, 4),
    (0, 6, 5, 3),
    (0, 4, 3, 5),
    (0, 2, 5, 4),
)


@dataclass(frozen=True)
class Section:
    name: str
    start: float
    end: float
    energy: float
    transformation: str


@dataclass(frozen=True)
class NoteEvent:
    note: int
    start: float
    duration: float
    velocity: float
    voice: str


@dataclass(frozen=True)
class CompositionPlan:
    mode: str
    tonic: int
    meter: int
    beat_seconds: float
    progression: tuple[int, ...]
    sections: tuple[Section, ...]
    notes: tuple[NoteEvent, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _sections(duration: float) -> tuple[Section, ...]:
    boundaries = (0.0, 0.16, 0.56, 0.82, 1.0)
    names = ("emergence", "drift", "transformation", "release")
    energies = (0.48, 0.68, 0.92, 0.42)
    transforms = ("statement", "variation", "expansion", "fragmentation")
    return tuple(
        Section(names[i], duration * boundaries[i], duration * boundaries[i + 1], energies[i], transforms[i])
        for i in range(4)
    )


def _section_at(time: float, sections: tuple[Section, ...]) -> Section:
    return next((section for section in sections if section.start <= time < section.end), sections[-1])


def build_composition(
    seed: int, duration: float, music: dict, timeline: list[CreativeEvent]
) -> CompositionPlan:
    rng = np.random.default_rng(seed ^ 0x5049414E4F)
    mode = str(rng.choice(tuple(MODES)))
    scale = MODES[mode]
    tonic = 48 + int(music["key_shift"])
    beat = float(music["beat_seconds"])
    meter = int(music["meter"])
    density = float(music["density"])
    progression = tuple(int(value) for value in PROGRESSIONS[int(rng.integers(0, len(PROGRESSIONS)))])
    sections = _sections(duration)
    motif = tuple(int(value) for value in rng.choice(scale, size=4, replace=False))
    notes: list[NoteEvent] = []
    step = beat * (1.0 if density < 0.72 else 0.5)
    cursor = beat * 0.75
    motif_index = 0
    while cursor < max(0.0, duration - 0.2):
        section = _section_at(cursor, sections)
        interval = motif[motif_index % len(motif)]
        if section.transformation == "variation":
            interval = scale[(scale.index(interval) + 2) % len(scale)]
        elif section.transformation == "expansion":
            interval += 12 if motif_index % 3 == 0 else 0
        elif section.transformation == "fragmentation" and motif_index % 2:
            cursor += step
            motif_index += 1
            continue
        humanize = float(rng.uniform(-0.035, 0.035))
        notes.append(
            NoteEvent(
                note=tonic + 24 + interval,
                start=max(0.0, cursor + humanize),
                duration=min(beat * float(rng.uniform(0.38, 1.15)), duration - cursor),
                velocity=float(rng.uniform(0.026, 0.052) * section.energy),
                voice="motif",
            )
        )
        cursor += step * float(rng.choice((1.0, 1.0, 1.5, 2.0)))
        motif_index += 1
    for event in timeline:
        center = event.start + event.duration * 0.5
        if center >= duration or event.kind == "stillness":
            continue
        notes.append(
            NoteEvent(
                note=tonic + 24 + event.pitch_offset,
                start=center,
                duration=min(beat * 1.8, duration - center),
                velocity=0.025 + 0.025 * event.intensity,
                voice="gesture",
            )
        )
    notes.sort(key=lambda note: note.start)
    return CompositionPlan(mode, tonic, meter, beat, progression, sections, tuple(notes))
