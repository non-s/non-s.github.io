"""Base dataclass for genre presets.

A :class:`GenrePreset` bundles together the musical DNA of a genre: which
instruments play which role, which drum pattern is used, the allowed
scales/modes, chord shapes, chord progressions, tempo/meter ranges, the song
form template, swing amount, mix-bus configuration and per-section
arrangement. Presets are frozen (immutable) so they can be safely shared and
cached.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenrePreset:
    name: str
    instruments: dict[str, str]  # role -> instrument registry name (e.g., "lead" -> "AcousticPiano")
    drum_pattern: str  # key into drums.PATTERNS
    modes: list[tuple[int, ...]]  # allowed scales/modes
    chord_types: list[list[int]]  # allowed chord shapes
    progressions: list[tuple[int, ...]]  # allowed progressions (degree indices)
    tempo_range: tuple[float, float]  # BPM range
    meter_options: list[int]  # time signatures
    song_form: str  # form template key
    swing: float  # 0.0-0.66
    mix_config: dict  # bus gains, pan, reverb sends, sidechain
    effects_chain: list[str]  # effects on master bus
    arrangement: dict[str, list[str]]  # section -> list of active instrument roles
    description: str = ""
