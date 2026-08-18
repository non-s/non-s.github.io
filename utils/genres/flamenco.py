"""Flamenco preset: rapid rasgueado guitar and phrygian harmony."""

from __future__ import annotations

from utils.genres.base import GenrePreset

FLAMENCO = GenrePreset(
    name="flamenco",
    instruments={
        "lead": "AcousticGuitar",
        "rhythm": "AcousticGuitar",
        "bass": "BassGuitar",
        "drums": "shuffle_blues",
    },
    drum_pattern="shuffle_blues",
    modes=[
        (0, 1, 3, 5, 7, 8, 10),  # phrygian
        (0, 2, 3, 5, 7, 8, 11),  # harmonic minor
        (0, 2, 3, 5, 7, 8, 10),  # aeolian
    ],
    chord_types=[
        [0, 3, 7],
        [0, 1, 5],
        [0, 3, 7, 10],
        [0, 4, 7],
    ],
    progressions=[
        (1, 0, 1, 0),
        (1, 4, 0, 3),
        (0, 1, 3, 1),
    ],
    tempo_range=(90.0, 120.0),
    meter_options=[4],
    song_form="through_composed",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 0.8, "pan": 0.0, "eq_low": 1.5, "eq_mid": 0.5, "eq_high": 1.5, "reverb_send": 0.25},
            "bass": {"gain": 0.9, "pan": 0.0, "eq_low": 2.0, "eq_mid": 0.5, "eq_high": -3.0, "reverb_send": 0.1},
            "keys": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "guitar": {"gain": 0.95, "pan": -0.2, "eq_low": -2.0, "eq_mid": 2.0, "eq_high": 2.0, "reverb_send": 0.3},
            "pads": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "lead": {"gain": 0.95, "pan": 0.2, "eq_low": -2.0, "eq_mid": 2.0, "eq_high": 2.0, "reverb_send": 0.3},
            "percussion": {"gain": 0.6, "pan": 0.15, "eq_low": -2.0, "eq_mid": 0.5, "eq_high": 2.0, "reverb_send": 0.3},
        },
        "master": {"gain": 1.0, "reverb_wet": 0.15},
        "reverb": {"room_size": 0.5, "damping": 0.45, "wet": 0.25, "width": 0.6},
        "sidechain": None,
        "saturation": "warm",
    },
    effects_chain=["plate_reverb", "tight_compressor", "master_compressor", "limiter"],
    arrangement={
        "through_composed": ["lead", "rhythm", "bass", "drums"],
    },
    description="Passionate flamenco with rapid rasgueado guitar and phrygian harmony.",
)
