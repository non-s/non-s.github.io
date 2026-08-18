"""Techno preset: driving four-on-the-floor with deep bass and evolving pads."""

from __future__ import annotations

from utils.genres.base import GenrePreset

TECHNO = GenrePreset(
    name="techno",
    instruments={
        "lead": "Lead",
        "pad": "Pad",
        "bass": "SubBass",
        "drums": "drums",
    },
    drum_pattern="four_on_floor",
    modes=[
        (0, 2, 3, 5, 7, 9, 10),  # dorian
        (0, 2, 3, 5, 7, 8, 10),  # aeolian (minor)
        (0, 1, 3, 5, 7, 8, 10),  # phrygian
    ],
    chord_types=[
        [0, 3, 7],
        [0, 3, 7, 10],
        [0, 2, 5],
        [0, 4, 7, 11],
    ],
    progressions=[
        (0, 0, 0, 0),
        (0, 5, 3, 4),
        (0, 1, 0, 1),
        (0, 6, 5, 0),
    ],
    tempo_range=(130.0, 140.0),
    meter_options=[4],
    song_form="intro_build_drop_outro",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 0.9, "pan": 0.0, "eq_low": 1.5, "eq_mid": 0.0, "eq_high": 1.0, "reverb_send": 0.1},
            "bass": {"gain": 1.0, "pan": 0.0, "eq_low": 2.0, "eq_mid": -1.0, "eq_high": -4.0, "reverb_send": 0.0},
            "keys": {"gain": 0.6, "pan": 0.0, "eq_low": -2.0, "eq_mid": 1.0, "eq_high": 1.5, "reverb_send": 0.3},
            "guitar": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "pads": {"gain": 0.8, "pan": 0.0, "eq_low": -2.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.5},
            "lead": {"gain": 0.8, "pan": -0.15, "eq_low": -2.0, "eq_mid": 1.5, "eq_high": 2.0, "reverb_send": 0.4},
            "fx": {"gain": 0.6, "pan": 0.2, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.7},
        },
        "master": {"gain": 0.95, "reverb_wet": 0.25},
        "reverb": {"room_size": 0.7, "damping": 0.5, "wet": 0.3, "width": 0.8},
        "sidechain": {"source": "drums", "target": "bass", "depth": 0.6, "attack": 0.005, "release": 0.15},
        "saturation": "analog",
    },
    effects_chain=["sidechain_comp", "analog_saturation", "stereo_widen", "lowcut_master"],
    arrangement={
        "intro": ["pad", "drums"],
        "build": ["pad", "bass", "drums", "lead"],
        "drop": ["bass", "lead", "pad", "drums"],
        "outro": ["pad", "drums"],
    },
    description="Driving four-on-the-floor techno with deep bass and evolving pads.",
)
