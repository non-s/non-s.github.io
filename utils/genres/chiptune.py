"""Chiptune preset: square-wave leads and bleepy arpeggios."""

from __future__ import annotations

from utils.genres.base import GenrePreset

CHIPTUNE = GenrePreset(
    name="chiptune",
    instruments={
        "lead": "Lead",
        "bass": "SynthBass",
        "pad": "Bell",
        "drums": "four_on_floor",
    },
    drum_pattern="four_on_floor",
    modes=[
        (0, 2, 4, 5, 7, 9, 11),  # ionian
        (0, 2, 3, 5, 7, 8, 10),  # aeolian
        (0, 2, 4, 6, 7, 9, 11),  # lydian
    ],
    chord_types=[
        [0, 4, 7],
        [0, 3, 7],
        [0, 4, 7, 9],
        [0, 3, 7, 10],
    ],
    progressions=[
        (0, 4, 5, 3),
        (0, 5, 6, 4),
        (0, 3, 4, 0),
    ],
    tempo_range=(120.0, 180.0),
    meter_options=[4],
    song_form="verse_chorus",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 0.9, "pan": 0.0, "eq_low": 1.5, "eq_mid": 0.5, "eq_high": 2.0, "reverb_send": 0.05},
            "bass": {"gain": 0.95, "pan": 0.0, "eq_low": 1.5, "eq_mid": 0.0, "eq_high": -3.0, "reverb_send": 0.0},
            "keys": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "pads": {"gain": 0.55, "pan": 0.0, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.3},
            "lead": {"gain": 1.0, "pan": -0.1, "eq_low": -1.0, "eq_mid": 1.5, "eq_high": 2.0, "reverb_send": 0.1},
        },
        "master": {"gain": 0.95, "reverb_wet": 0.05},
        "reverb": {"room_size": 0.25, "damping": 0.6, "wet": 0.1, "width": 0.4},
        "sidechain": None,
        "saturation": "clean",
    },
    effects_chain=["bitcrush", "tight_compressor", "master_compressor", "limiter"],
    arrangement={
        "verse": ["lead", "bass", "drums"],
        "chorus": ["lead", "bass", "pad", "drums"],
    },
    description="8-bit chiptune with square-wave leads and bleepy arpeggios.",
)
