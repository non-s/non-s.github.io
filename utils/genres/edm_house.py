"""EDM house preset: four-on-the-floor, sidechained bass, wide pads."""

from __future__ import annotations

from utils.genres.base import GenrePreset

EDM_HOUSE = GenrePreset(
    name="edm_house",
    instruments={
        "lead": "Lead",
        "pad": "Pad",
        "bass": "SubBass",
        "pluck": "Lead",
        "drums": "four_on_floor",
    },
    drum_pattern="four_on_floor",
    modes=[
        (0, 2, 3, 5, 7, 8, 10),  # aeolian
        (0, 2, 3, 5, 7, 9, 10),  # dorian
        (0, 3, 5, 7, 10),  # minor pentatonic
    ],
    chord_types=[
        [0, 3, 7],
        [0, 3, 7, 10],
        [0, 4, 7, 11],
    ],
    progressions=[
        (0, 5, 3, 6),  # i-VI-III-VII
        (0, 3, 6, 5),
        (5, 3, 0, 6),
    ],
    tempo_range=(120.0, 130.0),
    meter_options=[4],
    song_form="intro_build_drop_outro",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 1.1, "pan": 0.0, "eq_low": 2.5, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.08},
            "bass": {"gain": 0.9, "pan": 0.0, "eq_low": 2.0, "eq_mid": 0.0, "eq_high": -4.0, "reverb_send": 0.0},
            "keys": {"gain": 0.7, "pan": 0.0, "eq_low": -2.0, "eq_mid": 1.0, "eq_high": 1.0, "reverb_send": 0.25},
            "pads": {"gain": 0.65, "pan": 0.3, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.5},
            "lead": {"gain": 0.9, "pan": 0.0, "eq_low": -1.0, "eq_mid": 1.0, "eq_high": 2.0, "reverb_send": 0.2},
        },
        "master": {"gain": 1.0, "reverb_wet": 0.05},
        "reverb": {"room_size": 0.5, "damping": 0.4, "wet": 0.15, "width": 0.7},
        "sidechain": {
            "source": "drums",
            "target": "bass",
            "threshold": -30.0,
            "ratio": 6.0,
            "attack_ms": 3.0,
            "release_ms": 120.0,
        },
        "saturation": "soft",
    },
    effects_chain=["sidechain_duck", "stereo_widen", "master_compressor", "limiter"],
    arrangement={
        "intro": ["pad", "drums"],
        "build": ["pad", "bass", "drums", "pluck"],
        "drop": ["lead", "bass", "drums", "pad"],
        "breakdown": ["pad", "pluck"],
        "outro": ["pad", "drums"],
    },
    description="Four-on-the-floor house with sidechained sub bass and wide pads.",
)
