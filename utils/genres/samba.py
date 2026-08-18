"""Samba preset: carnival tamborim, surdo and syncopated guitar."""

from __future__ import annotations

from utils.genres.base import GenrePreset

SAMBA = GenrePreset(
    name="samba",
    instruments={
        "lead": "AcousticGuitar",
        "bass": "BassGuitar",
        "percussion": "Tamborim",
        "drums": "samba",
    },
    drum_pattern="samba",
    modes=[
        (0, 2, 4, 5, 7, 9, 11),  # ionian
        (0, 2, 4, 5, 7, 9, 10),  # mixolydian
        (0, 2, 3, 5, 7, 9, 10),  # dorian
    ],
    chord_types=[
        [0, 4, 7],
        [0, 3, 7],
        [0, 4, 7, 9],
        [0, 3, 7, 10],
    ],
    progressions=[
        (0, 4, 5, 3),
        (0, 1, 4, 0),
        (5, 1, 4, 0),
    ],
    tempo_range=(100.0, 130.0),
    meter_options=[4],
    song_form="groove_based",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 1.0, "pan": 0.0, "eq_low": 2.0, "eq_mid": 1.0, "eq_high": 2.0, "reverb_send": 0.2},
            "bass": {"gain": 1.0, "pan": 0.0, "eq_low": 2.5, "eq_mid": 0.5, "eq_high": -3.0, "reverb_send": 0.1},
            "keys": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "pads": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "lead": {"gain": 0.85, "pan": 0.2, "eq_low": -2.0, "eq_mid": 1.5, "eq_high": 1.5, "reverb_send": 0.3},
            "percussion": {
                "gain": 0.8,
                "pan": 0.15,
                "eq_low": -2.0,
                "eq_mid": 1.0,
                "eq_high": 2.5,
                "reverb_send": 0.25,
            },
        },
        "master": {"gain": 1.0, "reverb_wet": 0.1},
        "reverb": {"room_size": 0.4, "damping": 0.5, "wet": 0.18, "width": 0.5},
        "sidechain": None,
        "saturation": "warm",
    },
    effects_chain=["tight_compressor", "plate_reverb", "master_compressor", "limiter"],
    arrangement={
        "groove": ["lead", "bass", "percussion", "drums"],
        "break": ["bass", "percussion", "drums"],
    },
    description="Carnival samba with tamborim, surdo and syncopated guitar.",
)
