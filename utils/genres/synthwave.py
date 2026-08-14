"""Synthwave preset: gated reverb snares, analog warmth, retro 80s vibes."""

from __future__ import annotations

from utils.genres.base import GenrePreset

SYNTHWAVE = GenrePreset(
    name="synthwave",
    instruments={
        "lead": "Lead",
        "bass": "SynthBass",
        "drums": "synthwave_gated",
        "pad": "Pad",
    },
    drum_pattern="synthwave_gated",
    modes=[
        (0, 2, 3, 5, 7, 8, 10),  # aeolian
        (0, 2, 4, 5, 7, 9, 11),  # ionian
        (0, 2, 3, 5, 7, 9, 10),  # dorian
    ],
    chord_types=[
        [0, 3, 7],
        [0, 4, 7],
        [0, 3, 7, 10],
        [0, 4, 7, 11],
    ],
    progressions=[
        (0, 5, 2, 6),  # i-VI-III-VII
        (0, 6, 2, 5),
        (5, 3, 0, 4),
    ],
    tempo_range=(90.0, 120.0),
    meter_options=[4],
    song_form="verse_chorus",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 1.0, "pan": 0.0, "eq_low": 2.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.4},
            "bass": {"gain": 0.9, "pan": 0.0, "eq_low": 2.0, "eq_mid": 0.0, "eq_high": -3.0, "reverb_send": 0.0},
            "keys": {"gain": 0.75, "pan": 0.0, "eq_low": -1.0, "eq_mid": 1.0, "eq_high": 1.5, "reverb_send": 0.3},
            "pads": {"gain": 0.7, "pan": 0.25, "eq_low": -2.0, "eq_mid": 0.0, "eq_high": 1.0, "reverb_send": 0.5},
            "lead": {"gain": 0.9, "pan": -0.1, "eq_low": -1.0, "eq_mid": 1.5, "eq_high": 2.0, "reverb_send": 0.25},
        },
        "master": {"gain": 1.0, "reverb_wet": 0.1},
        "reverb": {"room_size": 0.55, "damping": 0.3, "wet": 0.2, "width": 0.6},
        "sidechain": None,
        "saturation": "analog",
    },
    effects_chain=["gated_reverb", "analog_warmth", "chorus", "master_compressor"],
    arrangement={
        "verse": ["bass", "drums", "pad"],
        "chorus": ["lead", "bass", "drums", "pad"],
    },
    description="Gated reverb snare, analog warmth, retro 80s synthwave.",
)
