"""Dubstep preset: half-time with heavy wobble bass and sparse drums."""

from __future__ import annotations

from utils.genres.base import GenrePreset

DUBSTEP = GenrePreset(
    name="dubstep",
    instruments={
        "lead": "Lead",
        "bass": "SynthBass",
        "pad": "Pad",
        "drums": "drums",
    },
    drum_pattern="trap",
    modes=[
        (0, 2, 3, 5, 7, 8, 10),  # aeolian (minor)
        (0, 1, 3, 5, 7, 8, 10),  # phrygian
    ],
    chord_types=[
        [0, 3, 7],
        [0, 3, 7, 10],
        [0, 2, 5],
        [0, 1, 5],
    ],
    progressions=[
        (0, 0, 0, 0),
        (0, 6, 5, 0),
        (0, 1, 0, 1),
        (0, 5, 6, 5),
    ],
    tempo_range=(70.0, 75.0),
    meter_options=[4],
    song_form="groove_based",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 0.95, "pan": 0.0, "eq_low": 2.0, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.1},
            "bass": {"gain": 1.0, "pan": 0.0, "eq_low": 2.5, "eq_mid": -1.0, "eq_high": -3.0, "reverb_send": 0.0},
            "keys": {"gain": 0.5, "pan": 0.0, "eq_low": -2.0, "eq_mid": 1.0, "eq_high": 1.5, "reverb_send": 0.3},
            "guitar": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "pads": {"gain": 0.7, "pan": 0.0, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.6},
            "lead": {"gain": 0.8, "pan": -0.15, "eq_low": -2.0, "eq_mid": 1.5, "eq_high": 2.0, "reverb_send": 0.35},
            "fx": {"gain": 0.6, "pan": 0.2, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.7},
        },
        "master": {"gain": 0.95, "reverb_wet": 0.2},
        "reverb": {"room_size": 0.6, "damping": 0.5, "wet": 0.25, "width": 0.8},
        "sidechain": {"source": "drums", "target": "bass", "depth": 0.5, "attack": 0.01, "release": 0.25},
        "saturation": "tube",
    },
    effects_chain=["sidechain_comp", "tube_saturation", "sub_bass_boost", "stereo_widen"],
    arrangement={
        "groove": ["bass", "pad", "lead", "drums"],
        "break": ["pad", "lead"],
        "drop": ["bass", "drums", "lead"],
        "outro": ["pad", "drums"],
    },
    description="Half-time dubstep with heavy wobble bass and sparse drums.",
)
