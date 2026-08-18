"""Folk preset: intimate fingerpicked acoustic guitar with soft pad backdrop."""

from __future__ import annotations

from utils.genres.base import GenrePreset

FOLK = GenrePreset(
    name="folk",
    instruments={
        "lead": "AcousticGuitar",
        "bass": "BassGuitar",
        "pad": "Pad",
        "drums": "drums",
    },
    drum_pattern="light",
    modes=[
        (0, 2, 4, 5, 7, 9, 11),  # ionian (major)
        (0, 2, 3, 5, 7, 9, 10),  # dorian
        (0, 2, 4, 7, 9),  # pentatonic major
    ],
    chord_types=[
        [0, 4, 7],
        [0, 4, 7, 9],
        [0, 3, 7],
        [0, 5, 7],
    ],
    progressions=[
        (0, 4, 5, 4),
        (0, 3, 4, 0),
        (0, 5, 3, 4),
        (0, 4, 0, 5),
    ],
    tempo_range=(70.0, 100.0),
    meter_options=[4],
    song_form="verse_chorus",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 0.6, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 1.0, "reverb_send": 0.2},
            "bass": {"gain": 0.75, "pan": 0.0, "eq_low": 1.0, "eq_mid": 0.0, "eq_high": -3.0, "reverb_send": 0.05},
            "keys": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "guitar": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "pads": {"gain": 0.6, "pan": 0.0, "eq_low": -2.0, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.6},
            "lead": {"gain": 0.9, "pan": -0.1, "eq_low": -1.5, "eq_mid": 1.0, "eq_high": 1.5, "reverb_send": 0.35},
            "fx": {"gain": 0.4, "pan": 0.2, "eq_low": -3.0, "eq_mid": 0.0, "eq_high": 1.5, "reverb_send": 0.55},
        },
        "master": {"gain": 0.85, "reverb_wet": 0.3},
        "reverb": {"room_size": 0.65, "damping": 0.5, "wet": 0.35, "width": 0.75},
        "sidechain": None,
        "saturation": "warm",
    },
    effects_chain=["warm_saturation", "plate_reverb", "stereo_widen"],
    arrangement={
        "verse": ["lead", "bass", "pad", "drums"],
        "chorus": ["lead", "bass", "pad", "drums"],
    },
    description="Intimate folk with fingerpicked acoustic guitar and soft pad backdrop.",
)
