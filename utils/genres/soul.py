"""Soul preset: smooth soul with warm electric piano, funky bass and brass stabs."""

from __future__ import annotations

from utils.genres.base import GenrePreset

SOUL = GenrePreset(
    name="soul",
    instruments={
        "lead": "ElectricPiano",
        "bass": "BassGuitar",
        "brass": "BrassSection",
        "pad": "Pad",
        "drums": "drums",
    },
    drum_pattern="funk_16ths",
    modes=[
        (0, 2, 3, 5, 7, 9, 10),  # dorian
        (0, 3, 5, 7, 10),  # pentatonic minor
        (0, 3, 5, 6, 7, 10),  # blues
    ],
    chord_types=[
        [0, 3, 7, 9],
        [0, 4, 7, 9],
        [0, 3, 7, 10],
        [0, 3, 6, 10],
    ],
    progressions=[
        (0, 3, 4, 0),
        (0, 4, 3, 0),
        (0, 5, 3, 4),
        (1, 4, 0, 0),
    ],
    tempo_range=(80.0, 110.0),
    meter_options=[4],
    song_form="verse_chorus",
    swing=0.15,
    mix_config={
        "buses": {
            "drums": {"gain": 0.85, "pan": 0.0, "eq_low": 1.0, "eq_mid": 0.5, "eq_high": 1.5, "reverb_send": 0.15},
            "bass": {"gain": 0.95, "pan": 0.0, "eq_low": 1.5, "eq_mid": 0.5, "eq_high": -2.0, "reverb_send": 0.05},
            "keys": {"gain": 0.85, "pan": -0.1, "eq_low": -1.5, "eq_mid": 1.0, "eq_high": 1.5, "reverb_send": 0.3},
            "guitar": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "pads": {"gain": 0.6, "pan": 0.1, "eq_low": -2.0, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.5},
            "lead": {"gain": 0.8, "pan": -0.15, "eq_low": -1.5, "eq_mid": 1.5, "eq_high": 2.0, "reverb_send": 0.35},
            "fx": {"gain": 0.5, "pan": 0.2, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.55},
        },
        "master": {"gain": 0.9, "reverb_wet": 0.22},
        "reverb": {"room_size": 0.5, "damping": 0.5, "wet": 0.28, "width": 0.75},
        "sidechain": None,
        "saturation": "warm",
    },
    effects_chain=["warm_saturation", "plate_reverb", "stereo_widen", "bus_comp"],
    arrangement={
        "verse": ["lead", "bass", "drums", "pad"],
        "chorus": ["lead", "brass", "bass", "pad", "drums"],
    },
    description="Smooth soul with warm electric piano, funky bass and brass stabs.",
)
