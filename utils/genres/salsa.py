"""Salsa preset: brass stabs, montuno piano and Latin percussion."""

from __future__ import annotations

from utils.genres.base import GenrePreset

SALSA = GenrePreset(
    name="salsa",
    instruments={
        "lead": "Trumpet",
        "brass": "BrassSection",
        "bass": "BassGuitar",
        "piano": "AcousticPiano",
        "drums": "samba",
    },
    drum_pattern="samba",
    modes=[
        (0, 2, 4, 5, 7, 9, 11),  # ionian
        (0, 2, 3, 5, 7, 9, 10),  # dorian
        (0, 2, 4, 5, 7, 9, 10),  # mixolydian
    ],
    chord_types=[
        [0, 4, 7],
        [0, 3, 7, 10],
        [0, 4, 7, 10],
        [0, 3, 7],
    ],
    progressions=[
        (0, 4, 5, 3),
        (0, 1, 4, 0),
        (5, 1, 4, 0),
    ],
    tempo_range=(160.0, 200.0),
    meter_options=[4],
    song_form="groove_based",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 1.0, "pan": 0.0, "eq_low": 1.5, "eq_mid": 1.0, "eq_high": 2.0, "reverb_send": 0.15},
            "bass": {"gain": 1.0, "pan": 0.0, "eq_low": 2.0, "eq_mid": 0.5, "eq_high": -3.0, "reverb_send": 0.05},
            "keys": {"gain": 0.85, "pan": -0.15, "eq_low": -2.0, "eq_mid": 1.5, "eq_high": 1.5, "reverb_send": 0.2},
            "pads": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "lead": {"gain": 0.85, "pan": 0.2, "eq_low": -1.0, "eq_mid": 1.5, "eq_high": 2.0, "reverb_send": 0.25},
            "brass": {"gain": 0.8, "pan": -0.2, "eq_low": -1.0, "eq_mid": 2.0, "eq_high": 2.0, "reverb_send": 0.2},
            "percussion": {"gain": 0.7, "pan": 0.15, "eq_low": -2.0, "eq_mid": 0.5, "eq_high": 2.0, "reverb_send": 0.2},
        },
        "master": {"gain": 1.0, "reverb_wet": 0.08},
        "reverb": {"room_size": 0.35, "damping": 0.55, "wet": 0.15, "width": 0.5},
        "sidechain": None,
        "saturation": "warm",
    },
    effects_chain=["tight_compressor", "plate_reverb", "master_compressor", "limiter"],
    arrangement={
        "groove": ["lead", "brass", "bass", "piano", "drums"],
        "break": ["bass", "piano", "drums"],
    },
    description="Energetic salsa with brass stabs, montuno piano and Latin percussion.",
)
