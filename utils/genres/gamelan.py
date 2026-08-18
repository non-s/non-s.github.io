"""Gamelan preset: bell timbres and pentatonic modes."""

from __future__ import annotations

from utils.genres.base import GenrePreset

GAMELAN = GenrePreset(
    name="gamelan",
    instruments={
        "lead": "Bell",
        "bell": "Mallet",
        "drone": "SubBass",
        "pad": "Pad",
    },
    drum_pattern="ambient_sparse",
    modes=[
        (0, 3, 5, 7, 10),  # pentatonic minor
        (0, 2, 4, 6, 8, 10),  # whole tone
        (0, 1, 3, 5, 7),  # slendro
    ],
    chord_types=[
        [0, 3, 7],
        [0, 5, 7],
        [0, 3, 5],
        [0, 2, 5],
    ],
    progressions=[
        (0,),
        (0, 4),
        (0, 5, 3),
    ],
    tempo_range=(60.0, 90.0),
    meter_options=[4],
    song_form="through_composed",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "bass": {"gain": 0.5, "pan": 0.0, "eq_low": 1.0, "eq_mid": -2.0, "eq_high": -4.0, "reverb_send": 0.4},
            "keys": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "pads": {"gain": 0.85, "pan": 0.0, "eq_low": -2.0, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.7},
            "lead": {"gain": 0.8, "pan": -0.2, "eq_low": -2.0, "eq_mid": 1.5, "eq_high": 2.5, "reverb_send": 0.65},
            "fx": {"gain": 0.6, "pan": 0.2, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.8},
        },
        "master": {"gain": 0.9, "reverb_wet": 0.4},
        "reverb": {"room_size": 0.9, "damping": 0.35, "wet": 0.55, "width": 0.85},
        "sidechain": None,
        "saturation": "soft",
    },
    effects_chain=["heavy_reverb", "stereo_widen", "lowpass_tone"],
    arrangement={
        "through_composed": ["lead", "bell", "drone", "pad"],
    },
    description="Indonesian gamelan-inspired textures with bell timbres and pentatonic modes.",
)
