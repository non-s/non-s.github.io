"""Drum and bass preset: fast breakbeat-driven with deep sub bass."""

from __future__ import annotations

from utils.genres.base import GenrePreset

DNB = GenrePreset(
    name="dnb",
    instruments={
        "bass": "SubBass",
        "pad": "Pad",
        "lead": "Lead",
        "drums": "drums",
    },
    drum_pattern="boom_bap",
    modes=[
        (0, 2, 3, 5, 7, 8, 10),  # aeolian (minor)
        (0, 2, 3, 5, 7, 9, 10),  # dorian
    ],
    chord_types=[
        [0, 3, 7],
        [0, 3, 7, 10],
        [0, 2, 5],
        [0, 4, 7, 9],
    ],
    progressions=[
        (0, 5, 3, 4),
        (0, 3, 5, 4),
        (0, 0, 5, 4),
        (0, 6, 5, 0),
    ],
    tempo_range=(160.0, 180.0),
    meter_options=[4],
    song_form="groove_based",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 1.0, "pan": 0.0, "eq_low": 1.5, "eq_mid": 1.0, "eq_high": 2.0, "reverb_send": 0.1},
            "bass": {"gain": 1.0, "pan": 0.0, "eq_low": 2.0, "eq_mid": -1.5, "eq_high": -4.0, "reverb_send": 0.0},
            "keys": {"gain": 0.5, "pan": 0.0, "eq_low": -2.0, "eq_mid": 1.0, "eq_high": 1.5, "reverb_send": 0.3},
            "guitar": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "pads": {"gain": 0.75, "pan": 0.0, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.6},
            "lead": {"gain": 0.8, "pan": -0.15, "eq_low": -2.0, "eq_mid": 1.5, "eq_high": 2.0, "reverb_send": 0.4},
            "fx": {"gain": 0.6, "pan": 0.2, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.7},
        },
        "master": {"gain": 0.95, "reverb_wet": 0.2},
        "reverb": {"room_size": 0.6, "damping": 0.5, "wet": 0.25, "width": 0.85},
        "sidechain": {"source": "drums", "target": "bass", "depth": 0.5, "attack": 0.005, "release": 0.12},
        "saturation": "tight",
    },
    effects_chain=["sidechain_comp", "tight_saturation", "stereo_widen", "reese_bass_eq"],
    arrangement={
        "groove": ["bass", "pad", "lead", "drums"],
        "break": ["pad", "lead"],
        "drop": ["bass", "drums", "lead"],
        "outro": ["pad", "drums"],
    },
    description="Fast breakbeat-driven drum and bass with deep sub bass.",
)
