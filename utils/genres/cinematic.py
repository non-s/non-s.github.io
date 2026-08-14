"""Cinematic preset: epic reverb, wide stereo, dynamic orchestral swells."""

from __future__ import annotations

from utils.genres.base import GenrePreset

CINEMATIC = GenrePreset(
    name="cinematic",
    instruments={
        "strings": "StringEnsemble",
        "brass": "BrassSection",
        "choir": "Choir",
        "timpani": "Timpani",
        "pad": "Pad",
    },
    drum_pattern="cinematic_percussion",
    modes=[
        (0, 2, 3, 5, 7, 8, 10),  # aeolian
        (0, 2, 3, 5, 7, 8, 11),  # harmonic minor
        (0, 2, 3, 5, 7, 9, 10),  # dorian
        (0, 1, 3, 5, 7, 8, 10),  # phrygian
    ],
    chord_types=[
        [0, 3, 7],
        [0, 4, 7],
        [0, 3, 6],  # diminished
        [0, 4, 8],  # augmented
        [0, 5, 7],  # suspended
    ],
    progressions=[
        (0, 5, 3, 6),
        (0, 6, 5, 3),
        (5, 3, 0, 6),
        (0, 3, 4, 5),
    ],
    tempo_range=(40.0, 180.0),
    meter_options=[3, 4],
    song_form="through_composed",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 0.6, "pan": 0.0, "eq_low": 2.0, "eq_mid": 0.0, "eq_high": 1.0, "reverb_send": 0.55},
            "bass": {"gain": 0.75, "pan": -0.15, "eq_low": 2.0, "eq_mid": 0.0, "eq_high": -2.0, "reverb_send": 0.45},
            "keys": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "guitar": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "pads": {"gain": 0.7, "pan": 0.25, "eq_low": -2.0, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.65},
            "lead": {"gain": 0.95, "pan": -0.25, "eq_low": -1.0, "eq_mid": 1.5, "eq_high": 1.5, "reverb_send": 0.55},
            "percussion": {"gain": 0.8, "pan": 0.2, "eq_low": 1.5, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.5},
            "fx": {"gain": 0.7, "pan": 0.0, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.7},
        },
        "master": {"gain": 0.95, "reverb_wet": 0.25},
        "reverb": {"room_size": 0.9, "damping": 0.35, "wet": 0.4, "width": 0.85},
        "sidechain": None,
        "saturation": "clean",
    },
    effects_chain=["epic_reverb", "stereo_widen", "dynamic_compressor", "limiter"],
    arrangement={
        "through_composed": ["strings", "brass", "choir", "timpani", "pad"],
    },
    description="Epic reverb, wide stereo, dynamic orchestral swells and crescendos.",
)
