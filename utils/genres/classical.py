"""Classical preset: orchestral ensembles, hall reverb, wide stereo."""

from __future__ import annotations

from utils.genres.base import GenrePreset

CLASSICAL = GenrePreset(
    name="classical",
    instruments={
        "lead": "StringEnsemble",
        "bass": "StringEnsemble",
        "brass": "BrassSection",
        "timpani": "Timpani",
        "choir": "Choir",
    },
    drum_pattern="cinematic_percussion",
    modes=[
        (0, 2, 4, 5, 7, 9, 11),  # ionian
        (0, 2, 3, 5, 7, 8, 10),  # aeolian
        (0, 2, 3, 5, 7, 9, 10),  # dorian
        (0, 2, 4, 6, 7, 9, 11),  # lydian
        (0, 2, 4, 5, 7, 9, 10),  # mixolydian
        (0, 1, 3, 5, 7, 8, 10),  # phrygian
        (0, 2, 3, 5, 7, 8, 11),  # harmonic minor
    ],
    chord_types=[
        [0, 4, 7],
        [0, 3, 7],
        [0, 4, 7, 10],
        [0, 3, 6],  # diminished
        [0, 4, 8],  # augmented
    ],
    progressions=[
        (0, 3, 4, 0),  # I-IV-V-I
        (0, 4, 3, 0),
        (1, 4, 0),  # ii-V-I
        (0, 5, 3, 4),
    ],
    tempo_range=(40.0, 200.0),
    meter_options=[2, 3, 4],
    song_form="sonata",
    swing=0.0,
    mix_config={
        "buses": {
            "drums": {"gain": 0.7, "pan": 0.0, "eq_low": 2.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.5},
            "bass": {"gain": 0.8, "pan": -0.1, "eq_low": 1.5, "eq_mid": 0.0, "eq_high": -1.0, "reverb_send": 0.4},
            "keys": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "guitar": {"gain": 0.0, "pan": 0.0, "eq_low": 0.0, "eq_mid": 0.0, "eq_high": 0.0, "reverb_send": 0.0},
            "pads": {"gain": 0.7, "pan": 0.2, "eq_low": -1.0, "eq_mid": 1.0, "eq_high": 1.0, "reverb_send": 0.55},
            "lead": {"gain": 0.9, "pan": -0.2, "eq_low": -1.0, "eq_mid": 1.5, "eq_high": 1.5, "reverb_send": 0.5},
            "percussion": {
                "gain": 0.75,
                "pan": 0.15,
                "eq_low": 1.0,
                "eq_mid": 0.0,
                "eq_high": 1.0,
                "reverb_send": 0.45,
            },
            "fx": {"gain": 0.6, "pan": 0.0, "eq_low": -2.0, "eq_mid": 0.0, "eq_high": 2.0, "reverb_send": 0.6},
        },
        "master": {"gain": 0.95, "reverb_wet": 0.2},
        "reverb": {"room_size": 0.85, "damping": 0.4, "wet": 0.3, "width": 0.8},
        "sidechain": None,
        "saturation": "clean",
    },
    effects_chain=["hall_reverb", "stereo_widen", "master_compressor"],
    arrangement={
        "exposition": ["lead", "bass", "choir"],
        "development": ["lead", "bass", "brass", "timpani", "choir"],
        "recapitulation": ["lead", "bass", "brass", "timpani", "choir"],
    },
    description="Orchestral ensembles, hall reverb, wide stereo, sonata/rondo forms.",
)
