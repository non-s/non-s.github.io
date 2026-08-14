"""Reggae/dub preset: one-drop drums, skank guitar, bass forward, delay throws."""

from __future__ import annotations

from utils.genres.base import GenrePreset

REGGAE_DUB = GenrePreset(
    name="reggae_dub",
    instruments={
        "rhythm": "AcousticGuitar",
        "bass": "BassGuitar",
        "organ": "Organ",
        "drums": "one_drop",
    },
    drum_pattern="one_drop",
    modes=[
        (0, 2, 4, 5, 7, 9, 11),  # ionian
        (0, 2, 3, 5, 7, 8, 10),  # aeolian
        (0, 2, 3, 5, 7, 9, 10),  # dorian
    ],
    chord_types=[
        [0, 4, 7],
        [0, 3, 7],
        [0, 4, 7, 10],
    ],
    progressions=[
        (0, 3, 4, 0),  # I-IV-V-I
        (0, 4, 5, 3),
    ],
    tempo_range=(70.0, 90.0),
    meter_options=[4],
    song_form="verse_dub_break",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 0.85, "pan": 0.0, "eq_low": 1.5, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.2},
            "bass": {"gain": 1.2, "pan": 0.0, "eq_low": 3.0, "eq_mid": 0.0, "eq_high": -4.0, "reverb_send": 0.05},
            "keys": {"gain": 0.6, "pan": -0.2, "eq_low": -2.0, "eq_mid": 1.5, "eq_high": 1.0, "reverb_send": 0.3},
            "guitar": {"gain": 0.7, "pan": 0.2, "eq_low": -3.0, "eq_mid": 1.0, "eq_high": 1.5, "reverb_send": 0.25},
            "lead": {"gain": 0.6, "pan": -0.1, "eq_low": -2.0, "eq_mid": 1.5, "eq_high": 1.5, "reverb_send": 0.35},
        },
        "master": {"gain": 1.0, "reverb_wet": 0.08},
        "reverb": {"room_size": 0.45, "damping": 0.55, "wet": 0.18, "width": 0.5},
        "sidechain": None,
        "saturation": "warm",
        "delay_throws": True,
    },
    effects_chain=["delay_throws", "plate_reverb", "master_compressor"],
    arrangement={
        "verse": ["rhythm", "bass", "organ", "drums"],
        "dub_break": ["bass", "drums", "organ"],
    },
    description="One-drop drums, skank guitar, bass-forward mix with delay throws.",
)
