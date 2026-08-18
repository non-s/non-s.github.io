"""Disco preset: seventies disco with clavinet grooves, funky bass and sweeping strings."""

from __future__ import annotations

from utils.genres.base import GenrePreset

DISCO = GenrePreset(
    name="disco",
    instruments={
        "lead": "Clavinet",
        "bass": "BassGuitar",
        "brass": "BrassSection",
        "strings": "StringEnsemble",
        "drums": "drums",
    },
    drum_pattern="four_on_floor",
    modes=[
        (0, 2, 3, 5, 7, 9, 10),  # dorian
        (0, 2, 4, 5, 7, 9, 10),  # mixolydian
        (0, 2, 4, 5, 7, 9, 11),  # ionian (major)
    ],
    chord_types=[
        [0, 4, 7, 9],
        [0, 3, 7, 10],
        [0, 4, 7, 11],
        [0, 5, 7, 10],
    ],
    progressions=[
        (0, 3, 4, 0),
        (0, 4, 5, 4),
        (0, 5, 3, 4),
        (5, 3, 0, 4),
    ],
    tempo_range=(110.0, 130.0),
    meter_options=[4],
    song_form="verse_chorus",
    swing=0.1,
    mix_config={
        "buses": {
            "drums": {"gain": 0.9, "pan": 0.0, "eq_low": 1.5, "eq_mid": 0.5, "eq_high": 2.0, "reverb_send": 0.15},
            "bass": {"gain": 0.95, "pan": 0.0, "eq_low": 1.5, "eq_mid": 0.5, "eq_high": -2.0, "reverb_send": 0.05},
            "keys": {"gain": 0.85, "pan": -0.1, "eq_low": -1.0, "eq_mid": 1.0, "eq_high": 1.5, "reverb_send": 0.25},
            "guitar": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "pads": {"gain": 0.7, "pan": 0.1, "eq_low": -2.0, "eq_mid": 0.5, "eq_high": 2.0, "reverb_send": 0.5},
            "lead": {"gain": 0.85, "pan": -0.15, "eq_low": -1.0, "eq_mid": 1.5, "eq_high": 2.0, "reverb_send": 0.3},
            "fx": {"gain": 0.5, "pan": 0.2, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.6},
        },
        "master": {"gain": 0.92, "reverb_wet": 0.22},
        "reverb": {"room_size": 0.55, "damping": 0.45, "wet": 0.28, "width": 0.85},
        "sidechain": {"source": "drums", "target": "bass", "depth": 0.25, "attack": 0.01, "release": 0.12},
        "saturation": "clean",
    },
    effects_chain=["sidechain_comp", "clean_saturation", "stereo_widen", "high_shelf_air"],
    arrangement={
        "verse": ["lead", "bass", "strings", "drums"],
        "chorus": ["lead", "brass", "bass", "strings", "drums"],
    },
    description="Seventies disco with clavinet grooves, funky bass and sweeping strings.",
)
