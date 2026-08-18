"""Afrobeat preset: interlocking guitar, funky sax and horn section."""

from __future__ import annotations

from utils.genres.base import GenrePreset

AFROBEAT = GenrePreset(
    name="afrobeat",
    instruments={
        "lead": "Saxophone",
        "brass": "BrassSection",
        "bass": "BassGuitar",
        "rhythm": "AcousticGuitar",
        "drums": "funk_16ths",
    },
    drum_pattern="funk_16ths",
    modes=[
        (0, 2, 3, 5, 7, 9, 10),  # dorian
        (0, 3, 5, 7, 10),  # pentatonic minor
        (0, 3, 5, 6, 7, 10),  # blues
    ],
    chord_types=[
        [0, 3, 7, 10],
        [0, 4, 7, 10],
        [0, 3, 7, 9],
        [0, 4, 7, 9],
    ],
    progressions=[
        (0, 3, 0, 3),
        (0, 6, 3, 6),
        (0, 0, 3, 0),
    ],
    tempo_range=(110.0, 130.0),
    meter_options=[4],
    song_form="groove_based",
    swing=0.12,
    mix_config={
        "buses": {
            "drums": {"gain": 1.0, "pan": 0.0, "eq_low": 2.0, "eq_mid": 1.0, "eq_high": 2.0, "reverb_send": 0.15},
            "bass": {"gain": 1.1, "pan": 0.0, "eq_low": 2.5, "eq_mid": 1.5, "eq_high": -2.0, "reverb_send": 0.0},
            "keys": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "guitar": {"gain": 0.85, "pan": -0.2, "eq_low": -3.0, "eq_mid": 1.5, "eq_high": 1.5, "reverb_send": 0.2},
            "pads": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "lead": {"gain": 0.9, "pan": 0.2, "eq_low": -1.0, "eq_mid": 2.0, "eq_high": 2.0, "reverb_send": 0.2},
            "brass": {"gain": 0.85, "pan": -0.15, "eq_low": -1.0, "eq_mid": 2.0, "eq_high": 2.0, "reverb_send": 0.2},
            "percussion": {
                "gain": 0.6,
                "pan": 0.15,
                "eq_low": -2.0,
                "eq_mid": 0.5,
                "eq_high": 2.0,
                "reverb_send": 0.25,
            },
        },
        "master": {"gain": 1.0, "reverb_wet": 0.08},
        "reverb": {"room_size": 0.35, "damping": 0.55, "wet": 0.15, "width": 0.5},
        "sidechain": None,
        "saturation": "warm",
    },
    effects_chain=["tight_compressor", "plate_reverb", "master_compressor", "limiter"],
    arrangement={
        "groove": ["lead", "brass", "bass", "rhythm", "drums"],
        "break": ["bass", "rhythm", "drums"],
    },
    description="West African afrobeat with interlocking guitar, funky sax and horn section.",
)
