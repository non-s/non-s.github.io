"""Industrial preset: metallic distortion, dark soundscapes and pounding beats."""

from __future__ import annotations

from utils.genres.base import GenrePreset

INDUSTRIAL = GenrePreset(
    name="industrial",
    instruments={
        "lead": "Lead",
        "bass": "SynthBass",
        "pad": "Pad",
        "drums": "trap",
    },
    drum_pattern="trap",
    modes=[
        (0, 1, 3, 5, 7, 8, 10),  # phrygian
        (0, 1, 3, 5, 6, 8, 10),  # locrian
        (0, 2, 4, 6, 8, 10),  # whole tone
    ],
    chord_types=[
        [0, 3, 7],
        [0, 1, 5],
        [0, 3, 6],
        [0, 1, 3, 7],
    ],
    progressions=[
        (0, 1, 0, 1),
        (0, 6, 5, 0),
        (1, 0, 1, 6),
    ],
    tempo_range=(100.0, 140.0),
    meter_options=[4],
    song_form="groove_based",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 1.15, "pan": 0.0, "eq_low": 3.0, "eq_mid": 1.0, "eq_high": 2.5, "reverb_send": 0.1},
            "bass": {"gain": 1.0, "pan": 0.0, "eq_low": 2.5, "eq_mid": 1.0, "eq_high": -4.0, "reverb_send": 0.05},
            "keys": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "pads": {"gain": 0.7, "pan": 0.0, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.5},
            "lead": {"gain": 0.9, "pan": -0.15, "eq_low": -2.0, "eq_mid": 2.0, "eq_high": 2.5, "reverb_send": 0.3},
            "fx": {"gain": 0.6, "pan": 0.2, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.6},
        },
        "master": {"gain": 1.0, "reverb_wet": 0.1},
        "reverb": {"room_size": 0.55, "damping": 0.6, "wet": 0.2, "width": 0.7},
        "sidechain": {
            "source": "drums",
            "target": "bass",
            "threshold": -30.0,
            "ratio": 6.0,
            "attack_ms": 3.0,
            "release_ms": 120.0,
        },
        "saturation": "tube",
    },
    effects_chain=["distortion", "sidechain_duck", "stereo_widen", "master_compressor", "limiter"],
    arrangement={
        "groove": ["lead", "bass", "pad", "drums"],
        "break": ["bass", "pad", "drums"],
    },
    description="Harsh industrial with metallic distortion, dark soundscapes and pounding beats.",
)
