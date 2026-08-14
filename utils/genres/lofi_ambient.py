"""Lo-fi ambient preset: warm, soft, tape-saturated downtempo."""

from __future__ import annotations

from utils.genres.base import GenrePreset

LOFI_AMBIENT = GenrePreset(
    name="lofi_ambient",
    instruments={
        "lead": "AcousticPiano",
        "pad": "Pad",
        "bass": "BassGuitar",
        "drums": "light",
    },
    drum_pattern="light",
    modes=[
        (0, 2, 3, 5, 7, 9, 10),  # dorian
        (0, 2, 3, 5, 7, 8, 10),  # aeolian
        (0, 2, 4, 6, 7, 9, 11),  # lydian
        (0, 2, 4, 5, 7, 9, 10),  # mixolydian
    ],
    chord_types=[
        [0, 3, 7, 10],
        [0, 4, 7, 11],
        [0, 3, 7, 10, 14],
        [0, 5, 7, 10],
    ],
    progressions=[
        (0, 5, 3, 6),
        (0, 3, 6, 4),
        (0, 6, 5, 3),
        (0, 4, 3, 5),
        (0, 2, 5, 4),
    ],
    tempo_range=(54.0, 83.0),
    meter_options=[3, 4, 5],
    song_form="four_section_arc",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 0.7, "pan": 0.0, "eq_low": 1.0, "eq_mid": -1.0, "eq_high": -2.0, "reverb_send": 0.35},
            "bass": {"gain": 0.85, "pan": 0.0, "eq_low": 1.5, "eq_mid": 0.0, "eq_high": -2.0, "reverb_send": 0.1},
            "keys": {"gain": 0.8, "pan": -0.15, "eq_low": -1.0, "eq_mid": 1.0, "eq_high": 0.5, "reverb_send": 0.4},
            "pads": {"gain": 0.6, "pan": 0.25, "eq_low": -2.0, "eq_mid": 0.0, "eq_high": 1.0, "reverb_send": 0.55},
            "lead": {"gain": 0.85, "pan": 0.0, "eq_low": -1.0, "eq_mid": 1.5, "eq_high": 1.0, "reverb_send": 0.45},
        },
        "master": {"gain": 0.9, "reverb_wet": 0.18},
        "reverb": {"room_size": 0.72, "damping": 0.65, "wet": 0.28, "width": 0.6},
        "sidechain": None,
        "saturation": "tape",
    },
    effects_chain=["tape_saturation", "soft_clip", "lowpass_tone"],
    arrangement={
        "emergence": ["pad", "bass"],
        "drift": ["pad", "bass", "lead", "drums"],
        "transformation": ["pad", "bass", "lead", "drums"],
        "release": ["pad", "bass", "lead"],
    },
    description="Warm, soft, tape-saturated downtempo with jazzy chords and light drums.",
)
