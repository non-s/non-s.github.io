"""Country preset: upbeat acoustic guitars with shuffle drums."""

from __future__ import annotations

from utils.genres.base import GenrePreset

COUNTRY = GenrePreset(
    name="country",
    instruments={
        "lead": "AcousticGuitar",
        "bass": "BassGuitar",
        "rhythm": "AcousticGuitar",
        "drums": "drums",
    },
    drum_pattern="shuffle_blues",
    modes=[
        (0, 2, 4, 5, 7, 9, 11),  # ionian (major)
        (0, 2, 4, 5, 7, 9, 10),  # mixolydian
        (0, 2, 4, 7, 9),  # pentatonic major
    ],
    chord_types=[
        [0, 4, 7],
        [0, 4, 7, 9],
        [0, 4, 7, 11],
        [0, 7, 4],
    ],
    progressions=[
        (0, 4, 5, 4),
        (0, 3, 4, 0),
        (0, 5, 3, 4),
        (1, 4, 0, 0),
    ],
    tempo_range=(90.0, 130.0),
    meter_options=[4],
    song_form="verse_chorus",
    swing=0.2,
    mix_config={
        "buses": {
            "drums": {"gain": 0.85, "pan": 0.0, "eq_low": 1.0, "eq_mid": 0.0, "eq_high": 1.0, "reverb_send": 0.15},
            "bass": {"gain": 0.9, "pan": 0.0, "eq_low": 1.5, "eq_mid": 0.0, "eq_high": -2.0, "reverb_send": 0.05},
            "keys": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "guitar": {"gain": 0.9, "pan": 0.0, "eq_low": -1.0, "eq_mid": 1.0, "eq_high": 1.5, "reverb_send": 0.2},
            "pads": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "lead": {"gain": 0.9, "pan": -0.15, "eq_low": -1.5, "eq_mid": 1.5, "eq_high": 2.0, "reverb_send": 0.3},
            "fx": {"gain": 0.4, "pan": 0.2, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.5},
        },
        "master": {"gain": 0.9, "reverb_wet": 0.2},
        "reverb": {"room_size": 0.55, "damping": 0.5, "wet": 0.25, "width": 0.7},
        "sidechain": None,
        "saturation": "warm",
    },
    effects_chain=["warm_saturation", "plate_reverb", "high_shelf_air"],
    arrangement={
        "verse": ["rhythm", "bass", "drums"],
        "chorus": ["lead", "rhythm", "bass", "drums"],
    },
    description="Upbeat country with acoustic guitars and shuffle drums.",
)
