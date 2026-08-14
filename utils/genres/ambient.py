"""Ambient preset: heavy reverb, no drums, slowly evolving textures."""

from __future__ import annotations

from utils.genres.base import GenrePreset

AMBIENT = GenrePreset(
    name="ambient",
    instruments={
        "pad": "Pad",
        "drone": "SubBass",
        "bell": "Bell",
        "reverb_heavy": "Pad",
    },
    drum_pattern="ambient_sparse",
    modes=[
        (0, 2, 4, 6, 7, 9, 11),  # lydian
        (0, 2, 3, 5, 7, 9, 10),  # dorian
        (0, 2, 4, 6, 8, 10),  # whole tone
    ],
    chord_types=[
        [0, 4, 7, 11],
        [0, 2, 5],
        [0, 4, 7, 9],
        [0, 3, 7, 10],
    ],
    progressions=[
        (0,),
        (0, 4),
        (0, 5, 3),
        (0, 0),
    ],
    tempo_range=(40.0, 80.0),
    meter_options=[4],
    song_form="through_composed",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "bass": {"gain": 0.5, "pan": 0.0, "eq_low": 1.0, "eq_mid": -2.0, "eq_high": -4.0, "reverb_send": 0.4},
            "keys": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "pads": {"gain": 0.9, "pan": 0.0, "eq_low": -2.0, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.75},
            "lead": {"gain": 0.7, "pan": -0.2, "eq_low": -2.0, "eq_mid": 1.0, "eq_high": 2.0, "reverb_send": 0.7},
            "fx": {"gain": 0.6, "pan": 0.2, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.8},
        },
        "master": {"gain": 0.9, "reverb_wet": 0.4},
        "reverb": {"room_size": 0.92, "damping": 0.3, "wet": 0.5, "width": 0.9},
        "sidechain": None,
        "saturation": "soft",
    },
    effects_chain=["heavy_reverb", "stereo_widen", "lowpass_tone"],
    arrangement={
        "through_composed": ["pad", "drone", "bell", "reverb_heavy"],
    },
    description="Heavy reverb, no drums, slowly evolving drone-based textures.",
)
