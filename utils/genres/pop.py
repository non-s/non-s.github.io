"""Pop preset: modern pop with bright electric piano and catchy synth plucks."""

from __future__ import annotations

from utils.genres.base import GenrePreset

POP = GenrePreset(
    name="pop",
    instruments={
        "lead": "ElectricPiano",
        "pad": "Pad",
        "bass": "SynthBass",
        "pluck": "Bell",
        "drums": "drums",
    },
    drum_pattern="four_on_floor",
    modes=[
        (0, 2, 4, 5, 7, 9, 11),  # ionian (major)
        (0, 2, 4, 5, 7, 9, 10),  # mixolydian
        (0, 2, 3, 5, 7, 9, 10),  # dorian
    ],
    chord_types=[
        [0, 4, 7],
        [0, 4, 7, 9],
        [0, 3, 7, 10],
        [0, 5, 7, 10],
    ],
    progressions=[
        (0, 4, 5, 3),
        (0, 5, 3, 4),
        (0, 3, 4, 0),
        (5, 3, 0, 4),
    ],
    tempo_range=(100.0, 130.0),
    meter_options=[4],
    song_form="verse_chorus",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 0.9, "pan": 0.0, "eq_low": 1.5, "eq_mid": 0.5, "eq_high": 1.5, "reverb_send": 0.1},
            "bass": {"gain": 0.9, "pan": 0.0, "eq_low": 1.5, "eq_mid": -1.0, "eq_high": -3.0, "reverb_send": 0.0},
            "keys": {"gain": 0.8, "pan": -0.1, "eq_low": -1.0, "eq_mid": 1.0, "eq_high": 1.5, "reverb_send": 0.25},
            "guitar": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "pads": {"gain": 0.7, "pan": 0.1, "eq_low": -2.0, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.5},
            "lead": {"gain": 0.85, "pan": -0.15, "eq_low": -1.5, "eq_mid": 1.5, "eq_high": 2.0, "reverb_send": 0.3},
            "fx": {"gain": 0.5, "pan": 0.2, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.6},
        },
        "master": {"gain": 0.92, "reverb_wet": 0.22},
        "reverb": {"room_size": 0.55, "damping": 0.5, "wet": 0.28, "width": 0.8},
        "sidechain": {"source": "drums", "target": "bass", "depth": 0.3, "attack": 0.01, "release": 0.15},
        "saturation": "soft",
    },
    effects_chain=["sidechain_comp", "soft_saturation", "stereo_widen", "high_shelf_air"],
    arrangement={
        "verse": ["lead", "bass", "pluck", "drums"],
        "chorus": ["lead", "pad", "bass", "pluck", "drums"],
    },
    description="Modern pop with bright electric piano, catchy synth plucks and tight drums.",
)
