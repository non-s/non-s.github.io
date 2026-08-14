"""Hip-hop preset: boom-bap drums, 808 sub bass, sidechained pads."""

from __future__ import annotations

from utils.genres.base import GenrePreset

HIP_HOP = GenrePreset(
    name="hip_hop",
    instruments={
        "lead": "ElectricPiano",
        "bass": "SubBass",
        "pad": "Pad",
        "drums": "boom_bap",
    },
    drum_pattern="boom_bap",
    modes=[
        (0, 2, 3, 5, 7, 9, 10),  # dorian
        (0, 2, 3, 5, 7, 8, 10),  # aeolian
        (0, 3, 5, 7, 10),  # minor pentatonic
        (0, 3, 5, 6, 7, 10),  # blues
    ],
    chord_types=[
        [0, 3, 7, 10],
        [0, 3, 7],
        [0, 5, 7, 10],
    ],
    progressions=[
        (0, 3, 6, 3),
        (0, 5, 3, 5),
        (0, 3, 0, 3),
    ],
    tempo_range=(70.0, 90.0),
    meter_options=[4],
    song_form="loop_hook",
    swing=0.1,
    mix_config={
        "buses": {
            "drums": {"gain": 1.1, "pan": 0.0, "eq_low": 3.0, "eq_mid": 0.5, "eq_high": 1.5, "reverb_send": 0.1},
            "bass": {"gain": 1.2, "pan": 0.0, "eq_low": 4.0, "eq_mid": -1.0, "eq_high": -6.0, "reverb_send": 0.0},
            "keys": {"gain": 0.7, "pan": -0.15, "eq_low": -2.0, "eq_mid": 1.5, "eq_high": 1.0, "reverb_send": 0.3},
            "pads": {"gain": 0.5, "pan": 0.2, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 1.0, "reverb_send": 0.45},
            "lead": {"gain": 0.8, "pan": 0.1, "eq_low": -1.0, "eq_mid": 2.0, "eq_high": 1.5, "reverb_send": 0.25},
        },
        "master": {"gain": 1.0, "reverb_wet": 0.06},
        "reverb": {"room_size": 0.4, "damping": 0.6, "wet": 0.15, "width": 0.5},
        "sidechain": {
            "source": "drums",
            "target": "bass",
            "threshold": -28.0,
            "ratio": 4.0,
            "attack_ms": 5.0,
            "release_ms": 150.0,
        },
        "saturation": "warm",
    },
    effects_chain=["sidechain_duck", "master_compressor", "limiter"],
    arrangement={
        "loop": ["lead", "bass", "drums", "pad"],
        "hook": ["lead", "bass", "drums", "pad"],
    },
    description="Boom-bap drums, loud 808 sub bass, sidechained pads and keys.",
)
