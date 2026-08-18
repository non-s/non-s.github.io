"""Metal preset: aggressive riffs with double-kick drums and dark harmonic minor lead."""

from __future__ import annotations

from utils.genres.base import GenrePreset

METAL = GenrePreset(
    name="metal",
    instruments={
        "lead": "DistortedGuitar",
        "rhythm": "DistortedGuitar",
        "bass": "BassGuitar",
        "drums": "drums",
    },
    drum_pattern="rock",
    modes=[
        (0, 1, 3, 5, 7, 8, 10),  # phrygian
        (0, 2, 3, 5, 7, 8, 10),  # aeolian (minor)
        (0, 2, 3, 5, 7, 8, 11),  # harmonic minor
    ],
    chord_types=[
        [0, 3, 7],
        [0, 3, 6],
        [0, 2, 3, 7],
        [0, 3, 7, 10],
    ],
    progressions=[
        (0, 0, 6, 5),
        (0, 6, 5, 4),
        (0, 1, 0, 6),
        (0, 5, 6, 0),
    ],
    tempo_range=(140.0, 180.0),
    meter_options=[4],
    song_form="verse_chorus_bridge",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 1.0, "pan": 0.0, "eq_low": 2.0, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.05},
            "bass": {"gain": 0.9, "pan": 0.0, "eq_low": 2.0, "eq_mid": 1.0, "eq_high": -2.0, "reverb_send": 0.0},
            "keys": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "guitar": {"gain": 1.0, "pan": 0.0, "eq_low": -1.5, "eq_mid": 1.5, "eq_high": 2.0, "reverb_send": 0.1},
            "pads": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "lead": {"gain": 0.95, "pan": -0.1, "eq_low": -2.0, "eq_mid": 2.0, "eq_high": 2.5, "reverb_send": 0.25},
            "fx": {"gain": 0.5, "pan": 0.2, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.6},
        },
        "master": {"gain": 0.95, "reverb_wet": 0.15},
        "reverb": {"room_size": 0.5, "damping": 0.6, "wet": 0.2, "width": 0.7},
        "sidechain": None,
        "saturation": "tube",
    },
    effects_chain=["tube_saturation", "amp_cab_sim", "lowcut_master", "bus_comp"],
    arrangement={
        "verse": ["rhythm", "bass", "drums"],
        "chorus": ["lead", "rhythm", "bass", "drums"],
        "bridge": ["rhythm", "bass", "drums"],
    },
    description="Aggressive metal with double-kick drums, down-tuned riffs and dark harmonic minor lead.",
)
