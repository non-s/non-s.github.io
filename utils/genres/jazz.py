"""Jazz preset: swing rhythm, extended chords, ii-V-I progressions."""

from __future__ import annotations

from utils.genres.base import GenrePreset

JAZZ = GenrePreset(
    name="jazz",
    instruments={
        "lead": "AcousticPiano",
        "bass": "BassGuitar",
        "drums": "jazz_swing",
    },
    drum_pattern="jazz_swing",
    modes=[
        (0, 2, 3, 5, 7, 9, 10),  # dorian
        (0, 2, 3, 5, 7, 8, 10),  # aeolian
        (0, 2, 4, 5, 7, 9, 11),  # ionian
        (0, 2, 4, 6, 7, 9, 11),  # lydian
        (0, 2, 4, 5, 7, 9, 10),  # mixolydian
        (0, 2, 3, 5, 7, 8, 11),  # harmonic minor
        (0, 2, 3, 5, 7, 9, 11),  # melodic minor
    ],
    chord_types=[
        [0, 3, 7, 10],
        [0, 4, 7, 11],
        [0, 3, 7, 10, 14],
        [0, 4, 7, 11, 14],
        [0, 3, 6, 10],  # half-diminished
        [0, 4, 7, 10],  # dominant 7
    ],
    progressions=[
        (1, 4, 0),  # ii-V-I
        (1, 4, 0, 1),
        (3, 6, 1, 4),  # iii-vi-ii-V
        (0, 1, 4, 0),
    ],
    tempo_range=(100.0, 280.0),
    meter_options=[3, 4],
    song_form="head_solos_head",
    swing=0.66,
    mix_config={
        "buses": {
            "drums": {"gain": 0.8, "pan": 0.0, "eq_low": 0.0, "eq_mid": 1.0, "eq_high": 1.5, "reverb_send": 0.3},
            "bass": {"gain": 0.9, "pan": 0.0, "eq_low": 1.5, "eq_mid": 0.5, "eq_high": -2.0, "reverb_send": 0.05},
            "keys": {"gain": 0.95, "pan": -0.1, "eq_low": -1.0, "eq_mid": 2.0, "eq_high": 1.0, "reverb_send": 0.35},
            "lead": {"gain": 0.95, "pan": 0.1, "eq_low": -1.0, "eq_mid": 2.0, "eq_high": 1.0, "reverb_send": 0.3},
        },
        "master": {"gain": 0.95, "reverb_wet": 0.12},
        "reverb": {"room_size": 0.45, "damping": 0.5, "wet": 0.2, "width": 0.5},
        "sidechain": None,
        "saturation": "warm",
    },
    effects_chain=["room_reverb", "master_compressor"],
    arrangement={
        "head": ["lead", "bass", "drums"],
        "solo": ["lead", "bass", "drums"],
    },
    description="Swing rhythm, extended chords, ii-V-I progressions, room reverb.",
)
