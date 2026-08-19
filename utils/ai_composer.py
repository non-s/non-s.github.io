"""AI Composer: Gemini generates musical structure as JSON, procedural engine renders it.

The AI provides high-level musical direction (narrative arc, sections, motif,
chord progression, tempo/dynamic curves, arrangement) and the procedural
engine renders that structure into a :class:`CompositionPlan` with NoteEvents.
Falls back gracefully to :func:`build_composition_extended` when Gemini is
unavailable.
"""

from __future__ import annotations

import json
import logging

import numpy as np

from utils.ai_helper import ai_text
from utils.composer_extended import (
    _arpeggiator,
    _counter_melody,
    _ostinato,
    _progression_pad,
    _walking_bass,
    build_composition_extended,
)
from utils.liquid_wire_composer import (
    MODES,
    SONG_FORMS,
    CompositionPlan,
    NoteEvent,
    Section,
    _bpm_to_beat,
    _section_at,
)

log = logging.getLogger(__name__)

_VALID_VOICES = (
    "motif",
    "bass",
    "pad",
    "counter_melody",
    "arpeggio",
    "ostinato",
    "walking_bass",
    "gesture",
)
_VALID_TRANSFORMS = (
    "statement",
    "variation",
    "expansion",
    "fragmentation",
    "development",
)
_GROOVE_FORMS = ("head_solos_head", "groove_based")


def _build_prompt(seed: int, duration: float, genre_preset) -> str:
    genre_name = getattr(genre_preset, "name", "unknown")
    description = getattr(genre_preset, "description", "")
    tempo_lo, tempo_hi = genre_preset.tempo_range
    suggested_bpm = round((tempo_lo + tempo_hi) * 0.5)
    mode_names = sorted(MODES.keys())
    form_names = list(SONG_FORMS.keys())
    n_sections_hint = len(SONG_FORMS.get(genre_preset.song_form, [genre_preset.song_form]))

    return f"""You are the musical director for a generative-art YouTube channel
(non-s.github.io) that produces original procedural music videos. You design
high-level musical structure; a deterministic procedural engine renders your
plan into actual notes. You do NOT write audio or lyrics.

Context:
- Channel focus: generative art and procedural music. No vocals, no lyrics.
- NEVER make medical, therapeutic, healing, sleep, anxiety-relief, or outcome
  claims. Describe music structurally, not as treatment.
- All output must be valid JSON only (no markdown, no prose outside JSON).
- Be creative but musically coherent. Temperature is 0.8.

Task: design a complete musical structure for a {duration:.0f}-second piece in
the "{genre_name}" genre ({description}). Seed for determinism: {seed}.

Available modes (scales): {mode_names}
Available song forms: {form_names}
Suggested BPM range: {tempo_lo:.0f}-{tempo_hi:.0f} (suggested: {suggested_bpm})
Number of sections: {n_sections_hint} (you may use 3-7 sections).
Available voices: motif, bass, pad, counter_melody, arpeggio, ostinato,
walking_bass, gesture.
Valid transformations per section: statement, variation, expansion,
fragmentation, development.

Return a single JSON object with these exact keys:

{{
  "narrative_arc": "one-sentence description of the emotional arc",
  "sections": [
    {{"name": "string", "energy": 0.0-1.0, "transformation": "one of the valid transforms",
      "duration_fraction": 0.0-1.0 (fractions must sum to ~1.0)}}
  ],
  "motif": [list of 4-8 integers; semitone offsets from the tonic, each 0-24],
  "chord_progression": [list of degree indices 0-6],
  "tempo_curve": [
    {{"section": "section name", "bpm_multiplier": 0.85-1.15}}
  ],
  "dynamic_plan": [
    {{"section": "section name", "velocity_multiplier": 0.5-1.3}}
  ],
  "arrangement": [
    {{"section": "section name", "active_voices": ["motif", "bass", ...]}}
  ]
}}

Rules:
- sections[].duration_fraction values must be positive and sum to ~1.0.
- motif intervals should fit the suggested mode family; keep them singable.
- chord_progression degrees reference scale degrees (0 = tonic).
- active_voices must be from the valid voices list above.
- Keep the narrative arc under 120 characters.
- Match section names across sections, tempo_curve, dynamic_plan, and
  arrangement so the procedural engine can join them.
"""


def _parse_ai_structure(raw: str) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        log.warning("ai_composer: JSON invalido do Gemini: %s", exc)
        return None
    if not isinstance(data, dict):
        log.warning("ai_composer: resposta do Gemini nao e um objeto.")
        return None

    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        log.warning("ai_composer: sections ausente ou vazia.")
        return None

    norm_sections: list[dict] = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        name = str(sec.get("name", "")).strip()
        if not name:
            continue
        energy = sec.get("energy", 0.6)
        try:
            energy = float(energy)
        except (TypeError, ValueError):
            energy = 0.6
        energy = max(0.0, min(1.0, energy))
        transform = str(sec.get("transformation", "statement")).strip()
        if transform not in _VALID_TRANSFORMS:
            transform = "statement"
        frac = sec.get("duration_fraction", 0.25)
        try:
            frac = float(frac)
        except (TypeError, ValueError):
            frac = 0.25
        frac = max(0.01, frac)
        norm_sections.append(
            {
                "name": name,
                "energy": energy,
                "transformation": transform,
                "duration_fraction": frac,
            }
        )

    if not norm_sections:
        log.warning("ai_composer: nenhuma secao valida apos normalizar.")
        return None

    total_frac = sum(s["duration_fraction"] for s in norm_sections)
    if total_frac <= 0:
        total_frac = 1.0
    for s in norm_sections:
        s["duration_fraction"] = s["duration_fraction"] / total_frac

    motif_raw = data.get("motif")
    motif: list[int] = []
    if isinstance(motif_raw, list):
        for v in motif_raw:
            try:
                iv = int(v)
            except (TypeError, ValueError):
                continue
            if 0 <= iv <= 36:
                motif.append(iv)
    if len(motif) < 3:
        motif = [0, 2, 4, 7]
    data["motif"] = motif

    prog_raw = data.get("chord_progression")
    progression: list[int] = []
    if isinstance(prog_raw, list):
        for v in prog_raw:
            try:
                deg = int(v)
            except (TypeError, ValueError):
                continue
            if 0 <= deg <= 6:
                progression.append(deg)
    if not progression:
        progression = [0, 4, 5, 3]
    data["chord_progression"] = progression

    tempo_curve = data.get("tempo_curve")
    if not isinstance(tempo_curve, list):
        tempo_curve = []
    norm_tempo: list[dict] = []
    for entry in tempo_curve:
        if not isinstance(entry, dict):
            continue
        section = str(entry.get("section", "")).strip()
        mult = entry.get("bpm_multiplier", 1.0)
        try:
            mult = float(mult)
        except (TypeError, ValueError):
            mult = 1.0
        mult = max(0.5, min(1.5, mult))
        if section:
            norm_tempo.append({"section": section, "bpm_multiplier": mult})
    data["tempo_curve"] = norm_tempo

    dynamic_plan = data.get("dynamic_plan")
    if not isinstance(dynamic_plan, list):
        dynamic_plan = []
    norm_dyn: list[dict] = []
    for entry in dynamic_plan:
        if not isinstance(entry, dict):
            continue
        section = str(entry.get("section", "")).strip()
        mult = entry.get("velocity_multiplier", 1.0)
        try:
            mult = float(mult)
        except (TypeError, ValueError):
            mult = 1.0
        mult = max(0.2, min(2.0, mult))
        if section:
            norm_dyn.append({"section": section, "velocity_multiplier": mult})
    data["dynamic_plan"] = norm_dyn

    arrangement = data.get("arrangement")
    if not isinstance(arrangement, list):
        arrangement = []
    norm_arr: list[dict] = []
    for entry in arrangement:
        if not isinstance(entry, dict):
            continue
        section = str(entry.get("section", "")).strip()
        voices_raw = entry.get("active_voices", [])
        if not isinstance(voices_raw, list):
            voices_raw = []
        voices = [str(v).strip() for v in voices_raw if str(v).strip() in _VALID_VOICES]
        if section and voices:
            norm_arr.append({"section": section, "active_voices": voices})
    data["arrangement"] = norm_arr
    data["sections"] = norm_sections

    arc = data.get("narrative_arc")
    if not isinstance(arc, str) or not arc.strip():
        data["narrative_arc"] = ""
    else:
        data["narrative_arc"] = arc.strip()[:200]

    return data


def ai_compose_structure(seed: int, duration: float, genre_preset) -> dict | None:
    """Ask Gemini for a complete musical structure as JSON.

    Returns a validated dict, or None if Gemini failed or produced invalid
    output (caller falls back to the procedural composer).
    """
    prompt = _build_prompt(seed, duration, genre_preset)
    raw = ai_text(prompt, json_mode=True, task="ai_composer")
    if not raw:
        log.info("ai_composer: Gemini retornou vazio; usando fallback procedural.")
        return None
    structure = _parse_ai_structure(raw)
    if structure is None:
        log.info("ai_composer: parse do JSON falhou; usando fallback procedural.")
    else:
        arc = structure.get("narrative_arc", "")
        log.info(
            "ai_composer: estrutura Gemini OK (%d secoes, %d notas motif, arco: %s)",
            len(structure.get("sections", [])),
            len(structure.get("motif", [])),
            arc[:60],
        )
    return structure


def _sections_from_ai(duration: float, ai_sections: list[dict]) -> tuple[Section, ...]:
    """Build Section objects from the AI-provided section descriptors."""
    boundaries = []
    acc = 0.0
    for sec in ai_sections:
        frac = sec["duration_fraction"]
        boundaries.append((acc, acc + frac))
        acc += frac
    if acc < 0.999 or acc > 1.001:
        scale = 1.0 / acc if acc > 0 else 1.0
        boundaries = [(s * scale, e * scale) for s, e in boundaries]
    sections: list[Section] = []
    for i, sec in enumerate(ai_sections):
        start = float(boundaries[i][0]) * duration
        end = float(boundaries[i][1]) * duration
        sections.append(
            Section(
                name=sec["name"],
                start=start,
                end=end,
                energy=sec["energy"],
                transformation=sec["transformation"],
            )
        )
    return tuple(sections)


def _velocity_multiplier_for(section_name: str, dynamic_plan: list[dict]) -> float:
    for entry in dynamic_plan:
        if entry["section"] == section_name:
            return entry["velocity_multiplier"]
    return 1.0


def _bpm_multiplier_for(section_name: str, tempo_curve: list[dict]) -> float:
    for entry in tempo_curve:
        if entry["section"] == section_name:
            return entry["bpm_multiplier"]
    return 1.0


def _active_voices_for(section_name: str, arrangement: list[dict]) -> list[str]:
    for entry in arrangement:
        if entry["section"] == section_name:
            return entry["active_voices"]
    return []


def _apply_transformation(
    interval: int,
    transformation: str,
    motif_index: int,
    scale: tuple[int, ...],
    rng: np.random.Generator,
) -> int:
    scale_len = len(scale)
    if transformation == "variation":
        if interval in scale:
            interval = scale[(scale.index(interval) + 2) % scale_len]
        else:
            interval = scale[(motif_index % scale_len)]
    elif transformation == "expansion":
        interval += 12 if motif_index % 3 == 0 else 0
    elif transformation == "development":
        neighbor = int(rng.choice((-1, 1, 2, -2)))
        interval = max(0, interval + neighbor)
    return interval


def build_ai_composition(
    seed: int,
    duration: float,
    genre_preset,
    ai_structure: dict,
) -> CompositionPlan:
    """Render a Gemini-provided structure into a CompositionPlan."""
    rng = np.random.default_rng(seed ^ 0x4149434F4D)

    scale = tuple(genre_preset.modes[int(rng.integers(0, len(genre_preset.modes)))])
    scale_len = len(scale)
    mode = "custom"
    for mode_name, intervals in MODES.items():
        if tuple(intervals) == scale:
            mode = mode_name
            break

    tonic = 48 + int(rng.integers(0, 12))
    tempo_lo, tempo_hi = genre_preset.tempo_range
    base_bpm = float(rng.uniform(tempo_lo, tempo_hi))
    beat = _bpm_to_beat(base_bpm)
    meter = int(genre_preset.meter_options[int(rng.integers(0, len(genre_preset.meter_options)))])
    swing = float(genre_preset.swing)

    ai_sections = ai_structure["sections"]
    sections = _sections_from_ai(duration, ai_sections)
    tempo_curve = ai_structure.get("tempo_curve", [])
    dynamic_plan = ai_structure.get("dynamic_plan", [])
    arrangement = ai_structure.get("arrangement", [])

    progression = tuple(ai_structure.get("chord_progression", [0, 4, 5, 3]))
    motif = tuple(ai_structure.get("motif", [0, 2, 4, 7]))
    if not motif:
        motif = (0, 2, 4, 7)

    tempo_map_points: list[tuple[float, float]] = []
    for section in sections:
        mult = _bpm_multiplier_for(section.name, tempo_curve)
        bpm_here = base_bpm * mult
        jitter = float(rng.uniform(-0.02, 0.02)) * bpm_here
        tempo_map_points.append((section.start, float(bpm_here + jitter)))
    if not tempo_map_points:
        tempo_map_points = [(0.0, base_bpm)]
    tempo_map = tuple(tempo_map_points)

    arrangement_tuple: list[tuple[str, tuple[str, ...]]] = []
    for section in sections:
        voices = _active_voices_for(section.name, arrangement)
        if not voices:
            voices = list(genre_preset.arrangement.get(section.name, list(genre_preset.instruments.keys())))
        arrangement_tuple.append((section.name, tuple(voices)))

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
        interval = _apply_transformation(
            interval, section.transformation, motif_index, scale, rng
        )
        if section.transformation == "fragmentation" and motif_index % 2:
            cursor += step
            motif_index += 1
            continue

        vel_mult = _velocity_multiplier_for(section.name, dynamic_plan)
        active = _active_voices_for(section.name, arrangement)
        if not active:
            active = list(genre_preset.instruments.keys())

        humanize = float(rng.uniform(-0.035, 0.035))
        if swing > 0.0 and motif_index % 2 == 1:
            humanize += swing * (step * 0.5)
        degree = (progression[motif_index % len(progression)] + current_shift) % scale_len
        root_note = tonic + scale[degree] - 12
        motif_note = tonic + 24 + interval

        if "bass" in active:
            notes.append(
                NoteEvent(
                    note=root_note,
                    start=max(0.0, cursor + humanize),
                    duration=min(beat * float(rng.uniform(0.6, 1.4)), duration - cursor),
                    velocity=float(rng.uniform(0.03, 0.06) * section.energy * vel_mult),
                    voice="bass",
                )
            )
        if "motif" in active:
            notes.append(
                NoteEvent(
                    note=motif_note,
                    start=max(0.0, cursor + humanize),
                    duration=min(beat * float(rng.uniform(0.38, 1.15)), duration - cursor),
                    velocity=float(rng.uniform(0.026, 0.052) * section.energy * vel_mult),
                    voice="motif",
                )
            )
            motif_notes_log.append(motif_note)
            motif_start_times.append(cursor)
            existing_starts.add(round(cursor + humanize, 4))

        cursor += step * float(rng.choice((1.0, 1.0, 1.5, 2.0)))
        motif_index += 1

    if "pad" in _all_active_voices(arrangement_tuple) or not arrangement:
        pad_notes = _progression_pad(
            rng, progression, scale, tonic, genre_preset.chord_types,
            sections, beat, duration, current_shift,
        )
        pad_notes = [n for n in pad_notes if _voice_active_in(n, arrangement_tuple, sections)]
        notes.extend(pad_notes)

    if "counter_melody" in _all_active_voices(arrangement_tuple):
        for section in sections:
            active = _active_voices_for(section.name, arrangement)
            if "counter_melody" not in active:
                continue
            section_motif_notes = [
                motif_notes_log[i]
                for i, t in enumerate(motif_start_times)
                if section.start <= t < section.end
            ]
            counter = _counter_melody(
                rng, section_motif_notes, scale, tonic, section, beat, duration, existing_starts,
            )
            notes.extend(counter)

    if "arpeggio" in _all_active_voices(arrangement_tuple):
        for section in sections:
            active = _active_voices_for(section.name, arrangement)
            if "arpeggio" not in active and section.energy <= 0.8:
                continue
            if "arpeggio" in active or section.energy > 0.8:
                degree = (progression[0] + current_shift) % scale_len
                chord_root = tonic + scale[degree]
                chord_shape = genre_preset.chord_types[int(rng.integers(0, len(genre_preset.chord_types)))]
                arp = _arpeggiator(rng, chord_root, chord_shape, section, beat, duration)
                notes.extend(arp)

    if "ostinato" in _all_active_voices(arrangement_tuple):
        ostinato_pattern = [tonic + 12 + s for s in scale[:4]]
        for section in sections:
            active = _active_voices_for(section.name, arrangement)
            if "ostinato" not in active:
                continue
            ost = _ostinato(rng, ostinato_pattern, section, beat, duration, section.energy)
            notes.extend(ost)

    if genre_preset.song_form in _GROOVE_FORMS and "walking_bass" in _all_active_voices(arrangement_tuple):
        walking = _walking_bass(rng, progression, scale, tonic, sections, beat, duration, current_shift)
        if walking:
            notes = [n for n in notes if n.voice != "bass"]
            notes.extend(walking)

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
        arrangement=tuple(arrangement_tuple),
    )


def _all_active_voices(arrangement_tuple: list[tuple[str, tuple[str, ...]]]) -> set[str]:
    voices: set[str] = set()
    for _, vs in arrangement_tuple:
        voices.update(vs)
    return voices


def _voice_active_in(
    note: NoteEvent,
    arrangement_tuple: list[tuple[str, tuple[str, ...]]],
    sections: tuple[Section, ...],
) -> bool:
    section = _section_at(note.start, sections)
    for sname, voices in arrangement_tuple:
        if sname == section.name and note.voice in voices:
            return True
    return not arrangement_tuple


def ai_compose(seed: int, duration: float, genre_preset) -> CompositionPlan:
    """Compose a piece using Gemini for structure, with procedural fallback.

    Tries :func:`ai_compose_structure`; on success renders via
    :func:`build_ai_composition`. If Gemini is unavailable or returns invalid
    data, falls back to :func:`build_composition_extended`.
    """
    structure = ai_compose_structure(seed, duration, genre_preset)
    if structure is not None:
        log.info("ai_compose: renderizando estrutura Gemini (seed=%d).", seed)
        try:
            return build_ai_composition(seed, duration, genre_preset, structure)
        except Exception as exc:
            log.warning("ai_compose: build_ai_composition falhou (%s); fallback procedural.", exc)
    log.info("ai_compose: usando build_composition_extended (seed=%d).", seed)
    return build_composition_extended(seed, duration, genre_preset)
