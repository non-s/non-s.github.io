"""Tests for the drum sequencer."""

from __future__ import annotations

import numpy as np

from utils.drums import PATTERNS, DrumSequencer

SR = 44100
BPM = 100.0


def test_sequencer_renders_correct_length() -> None:
    seq = DrumSequencer("four_on_floor", swing=0.0, steps=16)
    bars = 2
    y = seq.render(BPM, bars, SR)
    beat_duration = 60.0 / BPM
    bar_duration = 4.0 * beat_duration
    expected = int(round(bar_duration * bars * SR))
    # Allow a tolerance of a few samples for rounding.
    assert abs(y.shape[0] - expected) <= 2
    assert y.dtype == np.float64
    assert y.ndim == 1


def test_sequencer_output_in_range() -> None:
    seq = DrumSequencer("rock", swing=0.0)
    y = seq.render(BPM, 1, SR)
    assert np.all(np.abs(y) <= 1.0 + 1e-6)


def test_swing_delays_off_beats() -> None:
    """Swing should delay the off-beat hits (step 2) compared to straight timing."""
    straight = DrumSequencer("four_on_floor", swing=0.0, steps=16)
    swung = DrumDequencer_alt("four_on_floor", swing=0.5, steps=16)
    y_straight = straight.render(BPM, 1, SR)
    y_swung = swung.render(BPM, 1, SR)
    # The outputs should differ because swing shifts the off-beat hats.
    assert not np.allclose(y_straight, y_swung)
    # Find the first significant onset after step 0 (after 50ms) to confirm a
    # timing shift: the swung pattern should have its off-beat hit later.
    onset_straight = _first_onset_after(y_straight, int(0.08 * SR))
    onset_swung = _first_onset_after(y_swung, int(0.08 * SR))
    assert onset_swung >= onset_straight - SR // 1000  # 1ms tolerance


def _first_onset_after(signal: np.ndarray, start_i: int) -> int:
    """Return the index of the first sample exceeding 0.05 after ``start_i``."""
    for i in range(start_i, signal.size):
        if abs(signal[i]) > 0.05:
            return i
    return signal.size


class DrumDequencer_alt(DrumSequencer):
    """Alias used only to verify swing via a second instance."""


def test_different_patterns_produce_different_output() -> None:
    rock = DrumSequencer("rock", swing=0.0)
    funk = DrumSequencer("funk_16ths", swing=0.0)
    y_rock = rock.render(BPM, 1, SR)
    y_funk = funk.render(BPM, 1, SR)
    assert not np.allclose(y_rock, y_funk)


def test_determinism() -> None:
    seq_a = DrumSequencer("four_on_floor", swing=0.0)
    seq_b = DrumSequencer("four_on_floor", swing=0.0)
    a = seq_a.render(BPM, 2, SR)
    b = seq_b.render(BPM, 2, SR)
    assert np.array_equal(a, b)


def test_all_patterns_render() -> None:
    for name in PATTERNS:
        seq = DrumSequencer(name, swing=0.0)
        y = seq.render(BPM, 1, SR)
        assert y.dtype == np.float64
        assert y.ndim == 1
        assert y.size > 0


def test_unknown_pattern_raises() -> None:
    try:
        DrumSequencer("does_not_exist")
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown pattern")


def test_swing_value_clamped() -> None:
    seq = DrumSequencer("rock", swing=5.0)
    assert seq.swing <= 0.95
    y = seq.render(BPM, 1, SR)
    assert y.dtype == np.float64


def test_more_bars_produces_longer_output() -> None:
    seq = DrumSequencer("rock", swing=0.0)
    one = seq.render(BPM, 1, SR)
    two = seq.render(BPM, 2, SR)
    assert two.size > one.size
