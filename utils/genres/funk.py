"""Funk preset: 16th-note drums, slap bass, tight punchy brass stabs."""

from __future__ import annotations

from utils.genres.base import GenrePreset

FUNK = GenrePreset(
    name="funk",
    instruments={
        "lead": "Clavinet",
        "bass": "BassGuitar",
        "brass": "BrassSection",
        "drums": "funk_16ths",
    },
    drum_pattern="funk_16ths",
    modes=[
        (0, 2, 3, 5, 7, 9, 10),  # dorian
        (0, 2, 4, 5, 7, 9, 10),  # mixolydian
        (0, 3, 5, 7, 10),  # minor pentatonic
        (0, 3, 5, 6, 7, 10),  # blues
    ],
    chord_types=[
        [0, 3, 7, 10],
        [0, 4, 7, 10],
        [0, 3, 7, 10, 14],
    ],
    progressions=[
        (0, 3, 0, 3),
        (0, 6, 3, 6),
        (0, 0, 3, 0),
    ],
    tempo_range=(90.0, 120.0),
    meter_options=[4],
    song_form="groove_based",
    swing=0.16,
    mix_config={
        "buses": {
            "drums": {"gain": 1.0, "pan": 0.0, "eq_low": 2.0, "eq_mid": 1.0, "eq_high": 2.0, "reverb_send": 0.1},
            "bass": {"gain": 1.1, "pan": 0.0, "eq_low": 2.5, "eq_mid": 1.5, "eq_high": -2.0, "reverb_send": 0.0},
            "keys": {"gain": 0.85, "pan": -0.2, "eq_low": -2.0, "eq_mid": 2.0, "eq_high": 1.5, "reverb_send": 0.15},
            "guitar": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "pads": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "lead": {"gain": 0.9, "pan": 0.2, "eq_low": -1.0, "eq_mid": 2.0, "eq_high": 2.0, "reverb_send": 0.15},
            "percussion": {"gain": 0.6, "pan": 0.1, "eq_low": -2.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.2},
        },
        "master": {"gain": 1.0, "reverb_wet": 0.04},
        "reverb": {"room_size": 0.3, "damping": 0.6, "wet": 0.1, "width": 0.4},
        "sidechain": None,
        "saturation": "tight",
    },
    effects_chain=["tight_compressor", "master_compressor", "limiter"],
    arrangement={
        "groove": ["lead", "bass", "brass", "drums"],
        "break": ["bass", "drums"],
    },
    description="16th-note drums, slap bass, tight punchy brass stabs, groove-based.",
)
