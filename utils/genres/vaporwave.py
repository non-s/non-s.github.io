"""Vaporwave preset: slowed pads, tape saturation and dreamy synth textures."""

from __future__ import annotations

from utils.genres.base import GenrePreset

VAPORWAVE = GenrePreset(
    name="vaporwave",
    instruments={
        "lead": "Pad",
        "pad": "Pad",
        "bass": "SubBass",
        "drums": "synthwave_gated",
    },
    drum_pattern="synthwave_gated",
    modes=[
        (0, 2, 3, 5, 7, 9, 10),  # dorian
        (0, 2, 4, 5, 7, 9, 11),  # ionian
        (0, 2, 4, 6, 7, 9, 11),  # lydian
    ],
    chord_types=[
        [0, 4, 7, 9],
        [0, 4, 7, 11],
        [0, 3, 7, 9],
        [0, 4, 7],
    ],
    progressions=[
        (0, 5, 3, 4),
        (1, 4, 0, 5),
        (0, 3, 6, 5),
    ],
    tempo_range=(60.0, 90.0),
    meter_options=[4],
    song_form="through_composed",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 0.7, "pan": 0.0, "eq_low": 1.0, "eq_mid": -1.0, "eq_high": 0.5, "reverb_send": 0.4},
            "bass": {"gain": 0.85, "pan": 0.0, "eq_low": 2.0, "eq_mid": -1.0, "eq_high": -4.0, "reverb_send": 0.2},
            "keys": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "pads": {"gain": 1.0, "pan": 0.0, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.7},
            "lead": {"gain": 0.85, "pan": -0.2, "eq_low": -2.0, "eq_mid": 1.0, "eq_high": 2.0, "reverb_send": 0.65},
            "fx": {"gain": 0.6, "pan": 0.2, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.8},
        },
        "master": {"gain": 0.9, "reverb_wet": 0.35},
        "reverb": {"room_size": 0.85, "damping": 0.4, "wet": 0.45, "width": 0.9},
        "sidechain": None,
        "saturation": "tape",
    },
    effects_chain=["tape_saturation", "chorus", "stereo_widen", "lowpass_tone"],
    arrangement={
        "through_composed": ["lead", "pad", "bass", "drums"],
    },
    description="Nostalgic vaporwave with slowed-down pads, tape saturation and dreamy synth textures.",
)
