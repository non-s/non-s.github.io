"""Bossa nova preset: nylon guitar, soft brush drums and gentle piano."""

from __future__ import annotations

from utils.genres.base import GenrePreset

BOSSA_NOVA = GenrePreset(
    name="bossa_nova",
    instruments={
        "lead": "AcousticGuitar",
        "bass": "BassGuitar",
        "piano": "AcousticPiano",
        "drums": "bossa_nova",
    },
    drum_pattern="bossa_nova",
    modes=[
        (0, 2, 4, 5, 7, 9, 11),  # ionian
        (0, 2, 3, 5, 7, 9, 10),  # dorian
        (0, 2, 4, 7, 9),  # pentatonic major
    ],
    chord_types=[
        [0, 4, 7, 9],
        [0, 3, 7, 9],
        [0, 4, 7, 11],
        [0, 3, 7, 10],
    ],
    progressions=[
        (0, 4, 5, 3),
        (1, 4, 0, 3),
        (0, 1, 4, 0),
    ],
    tempo_range=(100.0, 140.0),
    meter_options=[4],
    song_form="verse_chorus",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 0.7, "pan": 0.0, "eq_low": 0.5, "eq_mid": 0.5, "eq_high": 1.5, "reverb_send": 0.3},
            "bass": {"gain": 0.85, "pan": 0.0, "eq_low": 1.5, "eq_mid": 0.0, "eq_high": -3.0, "reverb_send": 0.1},
            "keys": {"gain": 0.7, "pan": -0.2, "eq_low": -2.0, "eq_mid": 1.0, "eq_high": 1.0, "reverb_send": 0.35},
            "pads": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "lead": {"gain": 0.9, "pan": 0.2, "eq_low": -2.0, "eq_mid": 1.5, "eq_high": 1.5, "reverb_send": 0.4},
        },
        "master": {"gain": 0.95, "reverb_wet": 0.15},
        "reverb": {"room_size": 0.55, "damping": 0.5, "wet": 0.25, "width": 0.6},
        "sidechain": None,
        "saturation": "warm",
    },
    effects_chain=["plate_reverb", "soft_compressor", "master_compressor"],
    arrangement={
        "verse": ["lead", "bass", "piano", "drums"],
        "chorus": ["lead", "bass", "piano", "drums"],
    },
    description="Smooth Brazilian bossa nova with nylon guitar and soft brush drums.",
)
