"""Trance preset: uplifting trance with soaring lead and sidechain pumping."""

from __future__ import annotations

from utils.genres.base import GenrePreset

TRANCE = GenrePreset(
    name="trance",
    instruments={
        "lead": "Lead",
        "pad": "Pad",
        "bass": "SubBass",
        "pluck": "Bell",
        "drums": "drums",
    },
    drum_pattern="four_on_floor",
    modes=[
        (0, 2, 3, 5, 7, 8, 10),  # aeolian (minor)
        (0, 2, 3, 5, 7, 9, 10),  # dorian
    ],
    chord_types=[
        [0, 4, 7, 11],
        [0, 3, 7, 10],
        [0, 4, 7, 9],
        [0, 5, 7, 10],
    ],
    progressions=[
        (0, 5, 3, 4),
        (0, 3, 5, 4),
        (0, 6, 5, 4),
        (0, 4, 5, 3),
    ],
    tempo_range=(138.0, 145.0),
    meter_options=[4],
    song_form="intro_build_drop_outro",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 0.9, "pan": 0.0, "eq_low": 1.5, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.1},
            "bass": {"gain": 1.0, "pan": 0.0, "eq_low": 2.0, "eq_mid": -1.0, "eq_high": -4.0, "reverb_send": 0.0},
            "keys": {"gain": 0.6, "pan": 0.0, "eq_low": -2.0, "eq_mid": 1.0, "eq_high": 1.5, "reverb_send": 0.3},
            "guitar": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "pads": {"gain": 0.85, "pan": 0.0, "eq_low": -2.0, "eq_mid": 0.5, "eq_high": 2.0, "reverb_send": 0.6},
            "lead": {"gain": 0.9, "pan": -0.1, "eq_low": -2.0, "eq_mid": 1.5, "eq_high": 2.5, "reverb_send": 0.45},
            "fx": {"gain": 0.6, "pan": 0.2, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.75},
        },
        "master": {"gain": 0.95, "reverb_wet": 0.25},
        "reverb": {"room_size": 0.75, "damping": 0.4, "wet": 0.3, "width": 0.9},
        "sidechain": {"source": "drums", "target": "bass", "depth": 0.7, "attack": 0.005, "release": 0.18},
        "saturation": "analog",
    },
    effects_chain=["sidechain_comp", "analog_saturation", "stereo_widen", "high_shelf_air"],
    arrangement={
        "intro": ["pad", "pluck", "drums"],
        "build": ["pad", "bass", "pluck", "drums", "lead"],
        "drop": ["bass", "lead", "pad", "pluck", "drums"],
        "outro": ["pad", "pluck", "drums"],
    },
    description="Uplifting trance with soaring lead, sidechain pumping and big supersaw chords.",
)
