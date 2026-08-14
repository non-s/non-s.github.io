"""Deterministic sectional composer for original Liquid Wire scores."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

import numpy as np

from utils.liquid_wire_timeline import CreativeEvent

if TYPE_CHECKING:
    from utils.genres.base import GenrePreset

MODES = {
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "aeolian": (0, 2, 3, 5, 7, 8, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "ionian": (0, 2, 4, 5, 7, 9, 11),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "locrian": (0, 1, 3, 5, 6, 8, 10),
    "pentatonic_major": (0, 2, 4, 7, 9),
    "pentatonic_minor": (0, 3, 5, 7, 10),
    "blues": (0, 3, 5, 6, 7, 10),
    "harmonic_minor": (0, 2, 3, 5, 7, 8, 11),
    "melodic_minor": (0, 2, 3, 5, 7, 9, 11),
    "diminished": (0, 2, 3, 5, 6, 8, 9, 11),
    "whole_tone": (0, 2, 4, 6, 8, 10),
}
PROGRESSIONS = (
    (0, 5, 3, 6),
    (0, 3, 6, 4),
    (0, 6, 5, 3),
    (0, 4, 3, 5),
    (0, 2, 5, 4),
)

# Song-form templates: each form maps to an ordered list of section names.
# "through_composed" is a single free-form section spanning the whole duration.
SONG_FORMS: dict[str, list[str]] = {
    "four_section_arc": ["emergence", "drift", "transformation", "release"],
    "verse_chorus_bridge": ["verse", "chorus", "verse", "chorus", "bridge", "chorus"],
    "head_solos_head": ["head", "solo", "solo", "head"],
    "intro_build_drop_outro": ["intro", "build", "drop", "breakdown", "drop", "outro"],
    "verse_chorus": ["verse", "chorus", "verse", "chorus"],
    "loop_hook": ["loop", "loop", "hook", "loop"],
    "twelve_bar": ["twelve_bar"],
    "through_composed": ["through_composed"],
    "rondo": ["a", "b", "a", "c", "a", "b", "a"],
    "sonata": ["exposition", "development", "recapitulation"],
    "groove_based": ["groove", "groove", "break", "groove"],
    "verse_dub_break": ["verse", "dub_break", "verse", "dub_break"],
}

# Energy curves per section type, used by genre compositions to shape dynamics.
_SECTION_ENERGIES: dict[str, float] = {
    "emergence": 0.48,
    "drift": 0.68,
    "transformation": 0.92,
    "release": 0.42,
    "intro": 0.35,
    "build": 0.65,
    "drop": 0.95,
    "breakdown": 0.4,
    "outro": 0.3,
    "verse": 0.6,
    "chorus": 0.9,
    "bridge": 0.7,
    "head": 0.7,
    "solo": 0.85,
    "loop": 0.6,
    "hook": 0.9,
    "groove": 0.8,
    "break": 0.45,
    "twelve_bar": 0.75,
    "through_composed": 0.6,
    "exposition": 0.6,
    "development": 0.85,
    "recapitulation": 0.7,
    "a": 0.6,
    "b": 0.75,
    "c": 0.85,
    "dub_break": 0.5,
}

# Transformation labels per section type (used to vary the motif).
_SECTION_TRANSFORMS: dict[str, str] = {
    "emergence": "statement",
    "drift": "variation",
    "transformation": "expansion",
    "release": "fragmentation",
    "intro": "statement",
    "build": "variation",
    "drop": "expansion",
    "breakdown": "fragmentation",
    "outro": "fragmentation",
    "verse": "statement",
    "chorus": "expansion",
    "bridge": "variation",
    "head": "statement",
    "solo": "variation",
    "loop": "statement",
    "hook": "expansion",
    "groove": "statement",
    "break": "fragmentation",
    "twelve_bar": "variation",
    "through_composed": "variation",
    "exposition": "statement",
    "development": "expansion",
    "recapitulation": "variation",
    "a": "statement",
    "b": "variation",
    "c": "expansion",
    "dub_break": "fragmentation",
}


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
    # Optional genre-driven extensions (defaults keep backwards compatibility).
    tempo_map: tuple[tuple[float, float], ...] = ()  # (time_seconds, bpm) control points
    swing: float = 0.0  # 0.0 = straight, 0.66 = jazz swing
    arrangement: tuple[tuple[str, tuple[str, ...]], ...] = ()  # (section, active roles)

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


def _genre_sections(
    duration: float, form_names: list[str]
) -> tuple[Section, ...]:
    """Split ``duration`` evenly across the sections named in ``form_names``."""
    n = len(form_names)
    if n == 0:
        return (Section("through_composed", 0.0, duration, 0.6, "variation"),)
    boundaries = np.linspace(0.0, 1.0, n + 1)
    sections: list[Section] = []
    for i, name in enumerate(form_names):
        energy = _SECTION_ENERGIES.get(name, 0.6)
        transform = _SECTION_TRANSFORMS.get(name, "statement")
        sections.append(
            Section(
                name,
                float(duration * boundaries[i]),
                float(duration * boundaries[i + 1]),
                energy,
                transform,
            )
        )
    return tuple(sections)


def _bpm_to_beat(bpm: float) -> float:
    return 60.0 / float(bpm)


def _tempo_map_from_sections(
    sections: tuple[Section, ...], base_bpm: float, rng: np.random.Generator
) -> tuple[tuple[float, float], ...]:
    """Build a (time, bpm) control-point tempo map.

    Adds a slight accelerando toward higher-energy sections and a ritardando
    toward the final release, so the composition breathes dynamically.
    """
    if not sections:
        return ((0.0, base_bpm),)
    points: list[tuple[float, float]] = []
    for section in sections:
        # Vary BPM by up to +/- 6% based on section energy.
        delta = (section.energy - 0.65) * 0.12 * base_bpm
        jitter = float(rng.uniform(-0.02, 0.02)) * base_bpm
        points.append((section.start, float(base_bpm + delta + jitter)))
    # Ensure the final point matches the last section's bpm.
    return tuple(points)


def _modulate_progression(
    progression: tuple[int, ...], shift: int, scale_len: int
) -> tuple[int, ...]:
    """Shift every degree index of a progression by ``shift`` (mod scale_len)."""
    return tuple((degree + shift) % scale_len for degree in progression)


def build_composition_for_genre(
    seed: int, duration: float, genre_preset: GenrePreset
) -> CompositionPlan:
    """Build a :class:`CompositionPlan` driven by a :class:`GenrePreset`.

    Selects a mode, progression, tempo and meter from the preset using ``seed``
    for deterministic variety, builds sections from the genre's song form,
    supports a tempo map (gentle accelerando/ritardando), inter-section
    modulation (pivot-chord shift), swing, and a per-section arrangement map
    of which instrument roles are active.
    """
    rng = np.random.default_rng(seed ^ 0x47454E5245)
    scale = tuple(genre_preset.modes[int(rng.integers(0, len(genre_preset.modes)))])
    scale_len = len(scale)
    # Find the mode name in MODES whose intervals match the chosen scale.
    mode = "custom"
    for mode_name, intervals in MODES.items():
        if tuple(intervals) == scale:
            mode = mode_name
            break
    tonic = 48 + int(rng.integers(0, 12))
    bpm = float(rng.uniform(genre_preset.tempo_range[0], genre_preset.tempo_range[1]))
    beat = _bpm_to_beat(bpm)
    meter = int(genre_preset.meter_options[int(rng.integers(0, len(genre_preset.meter_options)))])
    progression = tuple(
        int(v) for v in genre_preset.progressions[int(rng.integers(0, len(genre_preset.progressions)))]
    )
    form_names = SONG_FORMS.get(genre_preset.song_form, [genre_preset.song_form])
    sections = _genre_sections(duration, form_names)
    tempo_map = _tempo_map_from_sections(sections, bpm, rng)
    swing = float(genre_preset.swing)

    # Arrangement: which roles are active per section.
    arrangement: list[tuple[str, tuple[str, ...]]] = []
    for section in sections:
        roles = tuple(genre_preset.arrangement.get(section.name, list(genre_preset.instruments.keys())))
        arrangement.append((section.name, roles))

    # Build motif from the chosen scale.
    motif = tuple(int(v) for v in rng.choice(scale, size=min(4, scale_len), replace=False))
    if not motif:
        motif = (0,)

    notes: list[NoteEvent] = []
    step = beat * (1.0 if swing < 0.3 else 0.5)
    cursor = beat * 0.75
    motif_index = 0
    # Track modulation: shift progression degrees per section for variety.
    current_shift = 0
    prev_section_name = ""
    while cursor < max(0.0, duration - 0.2):
        section = _section_at(cursor, sections)
        # Pivot-chord modulation between sections: shift degrees when entering
        # a new section (bounded so we stay in a related key area).
        if section.name != prev_section_name:
            if prev_section_name:
                current_shift = (current_shift + int(rng.choice((-1, 1, 2)))) % scale_len
            prev_section_name = section.name
        interval = motif[motif_index % len(motif)]
        if section.transformation == "variation":
            interval = scale[(scale.index(interval) + 2) % scale_len]
        elif section.transformation == "expansion":
            interval += 12 if motif_index % 3 == 0 else 0
        elif section.transformation == "fragmentation" and motif_index % 2:
            cursor += step
            motif_index += 1
            continue
        # Swing humanisation on off-beats.
        humanize = float(rng.uniform(-0.035, 0.035))
        if swing > 0.0 and motif_index % 2 == 1:
            humanize += swing * (step * 0.5)
        # Bass voice: root of the current chord (one octave below motif).
        degree = (progression[motif_index % len(progression)] + current_shift) % scale_len
        root_note = tonic + scale[degree] - 12
        notes.append(
            NoteEvent(
                note=root_note,
                start=max(0.0, cursor + humanize),
                duration=min(beat * float(rng.uniform(0.6, 1.4)), duration - cursor),
                velocity=float(rng.uniform(0.03, 0.06) * section.energy),
                voice="bass",
            )
        )
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

    # Pad/chord voice: sustained chord at the start of each section.
    for section in sections:
        chord_root = tonic + scale[(progression[0] + current_shift) % scale_len]
        chord_shape = genre_preset.chord_types[int(rng.integers(0, len(genre_preset.chord_types)))]
        for offset in chord_shape:
            notes.append(
                NoteEvent(
                    note=chord_root + offset,
                    start=section.start,
                    duration=min(beat * float(section.end - section.start), duration - section.start),
                    velocity=float(0.02 * section.energy),
                    voice="pad",
                )
            )

    notes.sort(key=lambda note: note.start)
    return CompositionPlan(
        mode,
        tonic,
        meter,
        beat,
        progression,
        sections,
        tuple(notes),
        tempo_map=tempo_map,
        swing=swing,
        arrangement=tuple(arrangement),
    )
