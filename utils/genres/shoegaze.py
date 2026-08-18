"""Shoegaze preset: wall-of-sound guitars and shimmering pads."""

from __future__ import annotations

from utils.genres.base import GenrePreset

SHOEGAZE = GenrePreset(
    name="shoegaze",
    instruments={
        "lead": "SupersawStereo",
        "rhythm": "SupersawStereo",
        "bass": "BassGuitar",
        "pad": "ShimmerPad",
        "drums": "light",
    },
    drum_pattern="light",
    modes=[
        (0, 2, 3, 5, 7, 9, 10),  # dorian
        (0, 2, 4, 5, 7, 9, 11),  # ionian
        (0, 2, 4, 6, 7, 9, 11),  # lydian
    ],
    chord_types=[
        [0, 4, 7, 9],
        [0, 3, 7, 9],
        [0, 4, 7, 11],
        [0, 5, 7, 11],
    ],
    progressions=[
        (0, 5, 3, 4),
        (1, 4, 0, 5),
        (0, 3, 6, 5),
    ],
    tempo_range=(70.0, 110.0),
    meter_options=[4],
    song_form="verse_chorus",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 0.75, "pan": 0.0, "eq_low": 1.0, "eq_mid": 0.5, "eq_high": 1.5, "reverb_send": 0.3},
            "bass": {"gain": 0.9, "pan": 0.0, "eq_low": 2.0, "eq_mid": 0.5, "eq_high": -3.0, "reverb_send": 0.1},
            "keys": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "guitar": {"gain": 1.0, "pan": -0.25, "eq_low": -3.0, "eq_mid": 1.5, "eq_high": 2.5, "reverb_send": 0.55},
            "pads": {"gain": 0.95, "pan": 0.2, "eq_low": -2.0, "eq_mid": 0.5, "eq_high": 2.5, "reverb_send": 0.7},
            "lead": {"gain": 0.95, "pan": -0.2, "eq_low": -2.0, "eq_mid": 1.5, "eq_high": 2.5, "reverb_send": 0.6},
            "fx": {"gain": 0.6, "pan": 0.25, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.8},
        },
        "master": {"gain": 0.95, "reverb_wet": 0.3},
        "reverb": {"room_size": 0.9, "damping": 0.35, "wet": 0.5, "width": 0.95},
        "sidechain": None,
        "saturation": "tube",
    },
    effects_chain=["heavy_reverb", "chorus", "stereo_widen", "tube_saturation", "master_compressor"],
    arrangement={
        "verse": ["rhythm", "bass", "pad", "drums"],
        "chorus": ["lead", "rhythm", "bass", "pad", "drums"],
    },
    description="Dreamy shoegaze with wall-of-sound guitars and shimmering pads.",
)
