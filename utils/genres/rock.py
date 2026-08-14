"""Rock preset: distorted guitars, punchy drums, power-chord progressions."""

from __future__ import annotations

from utils.genres.base import GenrePreset

ROCK = GenrePreset(
    name="rock",
    instruments={
        "lead": "DistortedGuitar",
        "rhythm": "DistortedGuitar",
        "bass": "BassGuitar",
        "drums": "rock",
        "pad": "Pad",
    },
    drum_pattern="rock",
    modes=[
        (0, 2, 4, 5, 7, 9, 11),  # ionian
        (0, 2, 3, 5, 7, 8, 10),  # aeolian
        (0, 2, 4, 5, 7, 9, 10),  # mixolydian
        (0, 3, 5, 6, 7, 10),  # blues
    ],
    chord_types=[
        [0, 7],  # power chord
        [0, 4, 7],
        [0, 3, 7],
        [0, 4, 7, 10],
    ],
    progressions=[
        (0, 4, 5, 4),  # I-V-vi-IV
        (0, 5, 6, 4),  # I-IV-V
        (0, 3, 4, 4),
        (5, 3, 0, 4),
    ],
    tempo_range=(90.0, 160.0),
    meter_options=[4],
    song_form="verse_chorus_bridge",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 1.0, "pan": 0.0, "eq_low": 2.0, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.12},
            "bass": {"gain": 0.9, "pan": 0.0, "eq_low": 2.0, "eq_mid": 0.0, "eq_high": -3.0, "reverb_send": 0.0},
            "guitar": {"gain": 1.0, "pan": 0.0, "eq_low": -2.0, "eq_mid": 2.0, "eq_high": 2.0, "reverb_send": 0.15},
            "pads": {"gain": 0.5, "pan": 0.0, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 1.0, "reverb_send": 0.4},
            "lead": {"gain": 0.95, "pan": 0.1, "eq_low": -1.0, "eq_mid": 1.5, "eq_high": 1.5, "reverb_send": 0.2},
        },
        "master": {"gain": 1.0, "reverb_wet": 0.05},
        "reverb": {"room_size": 0.4, "damping": 0.5, "wet": 0.12, "width": 0.4},
        "sidechain": None,
        "saturation": "tube",
    },
    effects_chain=["tube_saturation", "hard_clip", "master_compressor"],
    arrangement={
        "verse": ["rhythm", "bass", "drums", "pad"],
        "chorus": ["lead", "rhythm", "bass", "drums", "pad"],
        "bridge": ["rhythm", "bass", "drums"],
    },
    description="Guitar-forward, punchy drums, power-chord driven rock.",
)
