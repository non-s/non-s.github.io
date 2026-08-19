"""Smoke tests for the 39 extended instruments.

For each class: render a short NoteEvent and verify shape, max abs > 1e-6 and
finiteness. Parametrized by class for clear per-instrument failures.
"""

from __future__ import annotations

import numpy as np
import pytest

from utils.instruments.base import NoteEvent
from utils.instruments.drums_extended import (
    Agogo,
    Bongo,
    Caixa,
    China,
    Clave,
    Conga,
    Cowbell,
    Cuica,
    Rimshot,
    Shaker,
    Sidestick,
    Splash,
    Surdo,
    Tamborim,
    Tambourine,
    Woodblock,
)
from utils.instruments.strings_extended import (
    Banjo,
    Cello,
    Harp,
    Koto,
    Mandolin,
    Ukulele,
    Violin,
)
from utils.instruments.synth_extended import (
    FMSynth,
    GranularPad,
    ShimmerPad,
    SupersawStereo,
    VocoderSynth,
    WavetableSynth,
)
from utils.instruments.winds_extended import (
    Accordion,
    Clarinet,
    Harmonica,
    Oboe,
    Ocarina,
    Panpipes,
    Saxophone,
    Shakuhachi,
    Trombone,
    Trumpet,
)

WINDS = [Clarinet, Oboe, Saxophone, Trumpet, Trombone, Harmonica, Accordion, Shakuhachi, Ocarina, Panpipes]
STRINGS = [Violin, Cello, Harp, Koto, Banjo, Mandolin, Ukulele]
SYNTHS = [VocoderSynth, WavetableSynth, FMSynth, GranularPad, SupersawStereo, ShimmerPad]
DRUMS = [
    Tambourine, Conga, Bongo, Cowbell, Shaker, Woodblock, Clave, Agogo,
    Rimshot, Sidestick, China, Splash, Surdo, Caixa, Cuica, Tamborim,
]

ALL_INSTRUMENTS = WINDS + STRINGS + SYNTHS + DRUMS

SR = 44100
DURATION = 0.2
EXPECTED_N = int(round(DURATION * SR))


@pytest.mark.parametrize(
    "cls",
    ALL_INSTRUMENTS,
    ids=[c.__name__ for c in ALL_INSTRUMENTS],
)
def test_instrument_smoke(cls):
    inst = cls(seed=0)
    note = NoteEvent(note=60, start=0.0, duration=DURATION, velocity=0.7)
    out = inst.render(note, sample_rate=SR)
    assert out.shape == (EXPECTED_N,), f"{cls.__name__} produced shape {out.shape}"
    assert np.all(np.isfinite(out)), f"{cls.__name__} produced non-finite values"
    assert np.max(np.abs(out)) > 1e-6, f"{cls.__name__} produced silent output"


def test_instrument_count_is_39():
    assert len(ALL_INSTRUMENTS) == 39


@pytest.mark.parametrize(
    "cls",
    WINDS + STRINGS + SYNTHS,
    ids=[c.__name__ for c in WINDS + STRINGS + SYNTHS],
)
def test_instrument_determinism(cls):
    inst = cls(seed=3)
    note = NoteEvent(note=60, start=0.0, duration=0.1, velocity=0.7)
    a = inst.render(note, sample_rate=SR)
    b = inst.render(note, sample_rate=SR)
    assert np.allclose(a, b)
