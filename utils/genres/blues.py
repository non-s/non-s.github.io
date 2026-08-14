"""Blues preset: 12-bar form, shuffle swing, dominant 7 chords."""

from __future__ import annotations

from utils.genres.base import GenrePreset

BLUES = GenrePreset(
    name="blues",
    instruments={
        "lead": "AcousticGuitar",
        "bass": "BassGuitar",
        "drums": "shuffle_blues",
        "piano": "AcousticPiano",
    },
    drum_pattern="shuffle_blues",
    modes=[
        (0, 3, 5, 6, 7, 10),  # blues
        (0, 2, 3, 5, 7, 8, 10),  # aeolian
        (0, 2, 3, 5, 7, 9, 10),  # dorian
    ],
    chord_types=[
        [0, 3, 7, 10],
        [0, 4, 7, 10],  # dominant 7
        [0, 3, 6, 10],  # diminished
    ],
    progressions=[
        (0, 0, 0, 0, 3, 3, 0, 0, 4, 3, 0, 4),  # 12-bar blues
    ],
    tempo_range=(60.0, 120.0),
    meter_options=[4],
    song_form="twelve_bar",
    swing=0.33,
    mix_config={
        "buses": {
            "drums": {"gain": 0.85, "pan": 0.0, "eq_low": 1.5, "eq_mid": 0.5, "eq_high": 1.0, "reverb_send": 0.2},
            "bass": {"gain": 0.95, "pan": 0.0, "eq_low": 2.0, "eq_mid": 0.0, "eq_high": -3.0, "reverb_send": 0.05},
            "keys": {"gain": 0.75, "pan": -0.15, "eq_low": -1.0, "eq_mid": 1.5, "eq_high": 1.0, "reverb_send": 0.3},
            "guitar": {"gain": 0.9, "pan": 0.15, "eq_low": -2.0, "eq_mid": 2.0, "eq_high": 1.5, "reverb_send": 0.25},
            "lead": {"gain": 0.95, "pan": 0.0, "eq_low": -1.0, "eq_mid": 2.0, "eq_high": 1.5, "reverb_send": 0.25},
        },
        "master": {"gain": 0.95, "reverb_wet": 0.08},
        "reverb": {"room_size": 0.4, "damping": 0.5, "wet": 0.18, "width": 0.5},
        "sidechain": None,
        "saturation": "warm",
    },
    effects_chain=["room_reverb", "master_compressor"],
    arrangement={
        "twelve_bar": ["lead", "bass", "drums", "piano"],
    },
    description="12-bar blues form, shuffle swing, dominant 7 chords, guitar forward.",
)
