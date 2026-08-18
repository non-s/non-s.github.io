"""Extended composer: richer harmony, counter-melody, arpeggiator, ostinato.

This module builds on top of `utils.liquid_wire_composer` to add voices
that the base composer omits:

- A **progression-following pad** that changes chord per progression step
  (the base composer's pad plays only the tonic for an entire section).
- A **counter-melody** voice (call-and-response phrases that answer the
  main motif).
- An **arpeggiator** voice that cycles chord tones.
- An **ostinato** voice — a repeating rhythmic pattern.
- **Walking bass** for jazz/groove genres.

The ``build_composition_extended`` function produces a CompositionPlan
that integrates with the existing pipeline.
"""

from __future__ import annotations

import numpy as np

from utils.liquid_wire_composer import (
    MODES,
    SONG_FORMS,
    CompositionPlan,
    NoteEvent,
    Section,
    _bpm_to_beat,
    _genre_sections,
    _section_at,
    _tempo_map_from_sections,
)
from utils.liquid_wire_timeline import CreativeEvent


def _phrase(seed: int, scale: tuple[int, ...], length: int) -> tuple[int, ...]:
    """Generate a melodic phrase (question or answer) from the scale."""
    rng = np.random.default_rng(seed)
    phrase = tuple(int(v) for v in rng.choice(scale, size=length, replace=True))
    return phrase


def _counter_melody(
    rng: np.random.Generator,
    motif_notes: list[int],
    scale: tuple[int, ...],
    tonic: int,
    section: Section,
    beat: float,
    duration: float,
    existing_starts: set[float],
) -> list[NoteEvent]:
    """Generate a counter-melody that answers the main motif.

    The counter-melody starts where the motif pauses (rests), using
    higher register notes and shorter durations for a call-and-response
    feel.
    """
    notes: list[NoteEvent] = []
    if not motif_notes:
        return notes
    # Place counter-melody notes in the "gaps" between motif notes.
    for i, motif_note in enumerate(motif_notes):
        # Skip every other motif note to create space.
        if i % 2 == 0:
            continue
        start = section.start + (i + 0.5) * beat
        if start >= duration or start in existing_starts:
            continue
        # Counter-melody is a 3rd or 6th above/below the motif note.
        interval = int(rng.choice((3, 4, 5, 9)))
        direction = int(rng.choice((-1, 1)))
        counter_note = motif_note + direction * interval
        counter_note = max(36, min(96, counter_note))
        notes.append(
            NoteEvent(
                note=counter_note,
                start=start,
                duration=min(beat * float(rng.uniform(0.3, 0.6)), duration - start),
                velocity=float(rng.uniform(0.025, 0.045) * section.energy),
                voice="counter_melody",
            )
        )
        existing_starts.add(start)
    return notes


def _arpeggiator(
    rng: np.random.Generator,
    chord_root: int,
    chord_shape: list[int],
    section: Section,
    beat: float,
    duration: float,
) -> list[NoteEvent]:
    """Generate arpeggiated notes cycling through a chord shape."""
    notes: list[NoteEvent] = []
    if not chord_shape:
        return notes
    step = beat * 0.25  # 16th notes
    cursor = section.start
    idx = 0
    while cursor < min(section.end, duration):
        note = chord_root + chord_shape[idx % len(chord_shape)]
        notes.append(
            NoteEvent(
                note=note,
                start=cursor,
                duration=step * 0.9,
                velocity=float(rng.uniform(0.02, 0.04) * section.energy),
                voice="arpeggio",
            )
        )
        cursor += step
        idx += 1
    return notes


def _ostinato(
    rng: np.random.Generator,
    pattern_notes: list[int],
    section: Section,
    beat: float,
    duration: float,
    energy: float,
) -> list[NoteEvent]:
    """Generate an ostinato (repeating rhythmic pattern)."""
    notes: list[NoteEvent] = []
    if not pattern_notes:
        return notes
    step = beat * 0.5  # 8th notes
    cursor = section.start
    idx = 0
    while cursor < min(section.end, duration):
        note = pattern_notes[idx % len(pattern_notes)]
        notes.append(
            NoteEvent(
                note=note,
                start=cursor,
                duration=step * 0.7,
                velocity=float(rng.uniform(0.025, 0.05) * energy),
                voice="ostinato",
            )
        )
        cursor += step
        idx += 1
    return notes


def _walking_bass(
    rng: np.random.Generator,
    progression: tuple[int, ...],
    scale: tuple[int, ...],
    tonic: int,
    sections: list[Section] | tuple[Section, ...],
    beat: float,
    duration: float,
    current_shift: int,
) -> list[NoteEvent]:
    """Generate a walking bass line that approaches each chord change by step.

    Classic jazz walking bass: play the root on beat 1, then approach the
    next chord by scale step (or chromatic) on beats 2-4.
    """
    notes: list[NoteEvent] = []
    scale_len = len(scale)
    chord_idx = 0
    for section in sections:
        cursor = section.start
        while cursor < min(section.end, duration):
            degree = (progression[chord_idx % len(progression)] + current_shift) % scale_len
            root = tonic + scale[degree] - 12
            # Beat 1: root, beats 2-4: approach notes.
            for b in range(4):
                if cursor + b * beat >= duration:
                    break
                if b == 0:
                    note = root
                elif b == 1:
                    note = root + int(rng.choice((-2, 2, 3)))
                elif b == 2:
                    note = root + int(rng.choice((-4, 4, 5)))
                else:
                    # Approach next chord.
                    next_degree = (progression[(chord_idx + 1) % len(progression)] + current_shift) % scale_len
                    next_root = tonic + scale[next_degree] - 12
                    note = next_root + int(rng.choice((-1, 1, -2, 2)))
                notes.append(
                    NoteEvent(
                        note=note,
                        start=cursor + b * beat,
                        duration=beat * 0.9,
                        velocity=float(rng.uniform(0.04, 0.07) * section.energy),
                        voice="walking_bass",
                    )
                )
            cursor += beat * 4
            chord_idx += 1
    return notes


def _progression_pad(
    rng: np.random.Generator,
    progression: tuple[int, ...],
    scale: tuple[int, ...],
    tonic: int,
    chord_types: list[list[int]],
    sections: list[Section] | tuple[Section, ...],
    beat: float,
    duration: float,
    current_shift: int,
    section_energy: float = 0.7,
) -> list[NoteEvent]:
    """A pad that follows the chord progression (one chord per progression step).

    Unlike the base composer's pad (which plays only the tonic for the whole
    section), this pad cycles through the progression, changing chords every
    ``beat * meter`` or every section — whichever is shorter. This makes the
    harmonic motion audible in the pad voice.
    """
    notes: list[NoteEvent] = []
    scale_len = len(scale)
    chord_idx = 0
    for section in sections:
        section_duration = min(section.end, duration) - section.start
        chord_duration = beat * 4  # one chord per bar
        if chord_duration > section_duration:
            chord_duration = section_duration
        cursor = section.start
        while cursor < min(section.end, duration):
            degree = (progression[chord_idx % len(progression)] + current_shift) % scale_len
            chord_root = tonic + scale[degree]
            chord_shape = chord_types[int(rng.integers(0, len(chord_types)))]
            for offset in chord_shape:
                note = chord_root + offset
                dur = min(chord_duration, duration - cursor)
                if dur > 0:
                    notes.append(
                        NoteEvent(
                            note=note,
                            start=cursor,
                            duration=dur,
                            velocity=float(0.018 * section.energy),
                            voice="pad",
                        )
                    )
            cursor += chord_duration
            chord_idx += 1
    return notes


def build_composition_extended(
    seed: int,
    duration: float,
    genre_preset,
    events: list[CreativeEvent] | None = None,
) -> CompositionPlan:
    """Build an extended CompositionPlan with 6-8 voices.

    Adds counter-melody, arpeggiator, ostinato and walking bass on top of
    the base composer's motif/bass/pad. Falls back to the base voices when
    a genre doesn't request the extended ones.
    """
    rng = np.random.default_rng(seed ^ 0x5854455254)
    scale = tuple(genre_preset.modes[int(rng.integers(0, len(genre_preset.modes)))])
    scale_len = len(scale)
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

    arrangement: list[tuple[str, tuple[str, ...]]] = []
    for section in sections:
        roles = tuple(genre_preset.arrangement.get(section.name, list(genre_preset.instruments.keys())))
        arrangement.append((section.name, roles))

    motif = tuple(int(v) for v in rng.choice(scale, size=min(4, scale_len), replace=False))
    if not motif:
        motif = (0,)

    notes: list[NoteEvent] = []
    step = beat * (1.0 if swing < 0.3 else 0.5)
    cursor = beat * 0.75
    motif_index = 0
    current_shift = 0
    prev_section_name = ""
    motif_notes_log: list[int] = []
    motif_start_times: list[float] = []
    existing_starts: set[float] = set()

    while cursor < max(0.0, duration - 0.2):
        section = _section_at(cursor, sections)
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
        humanize = float(rng.uniform(-0.035, 0.035))
        if swing > 0.0 and motif_index % 2 == 1:
            humanize += swing * (step * 0.5)
        degree = (progression[motif_index % len(progression)] + current_shift) % scale_len
        root_note = tonic + scale[degree] - 12
        motif_note = tonic + 24 + interval
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
                note=motif_note,
                start=max(0.0, cursor + humanize),
                duration=min(beat * float(rng.uniform(0.38, 1.15)), duration - cursor),
                velocity=float(rng.uniform(0.026, 0.052) * section.energy),
                voice="motif",
            )
        )
        motif_notes_log.append(motif_note)
        motif_start_times.append(cursor)
        existing_starts.add(round(cursor + humanize, 4))
        cursor += step * float(rng.choice((1.0, 1.0, 1.5, 2.0)))
        motif_index += 1

    # Extended voices.
    # 1. Progression-following pad (replaces the tonic-only pad).
    pad_notes = _progression_pad(
        rng, progression, scale, tonic, genre_preset.chord_types,
        sections, beat, duration, current_shift,
    )
    notes.extend(pad_notes)

    # 2. Counter-melody (call-and-response).
    for section in sections:
        section_motif_notes = [
            motif_notes_log[i]
            for i, t in enumerate(motif_start_times)
            if section.start <= t < section.end
        ]
        counter = _counter_melody(
            rng, section_motif_notes, scale, tonic, section, beat, duration, existing_starts,
        )
        notes.extend(counter)

    # 3. Arpeggiator (in sections with high energy only — drops).
    for section in sections:
        if section.energy > 0.75:
            degree = (progression[0] + current_shift) % scale_len
            chord_root = tonic + scale[degree]
            chord_shape = genre_preset.chord_types[int(rng.integers(0, len(genre_preset.chord_types)))]
            arp = _arpeggiator(rng, chord_root, chord_shape, section, beat, duration)
            notes.extend(arp)

    # 4. Ostinato (in groove-based or loop_hook genres).
    if genre_preset.song_form in ("groove_based", "loop_hook", "verse_chorus"):
        ostinato_pattern = [tonic + 12 + s for s in scale[:4]]
        for section in sections[:2]:  # only first 2 sections
            ost = _ostinato(rng, ostinato_pattern, section, beat, duration, section.energy)
            notes.extend(ost)

    # 5. Walking bass (for jazz and similar groove genres).
    if genre_preset.song_form in ("head_solos_head", "groove_based"):
        walking = _walking_bass(rng, progression, scale, tonic, sections, beat, duration, current_shift)
        if walking:
            # Replace the simple bass notes with walking bass.
            notes = [n for n in notes if n.voice != "bass"]
            notes.extend(walking)

    # 6. Gesture notes from creative events.
    if events:
        for event in events:
            if event.kind == "stillness":
                continue
            gesture_start = event.start + event.duration * 0.5
            if gesture_start >= duration:
                continue
            gesture_note = tonic + 24 + int(event.pitch_offset)
            notes.append(
                NoteEvent(
                    note=gesture_note,
                    start=gesture_start,
                    duration=min(beat * 0.8, duration - gesture_start),
                    velocity=float(0.05 * (0.5 + 0.5 * event.intensity)),
                    voice="gesture",
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
