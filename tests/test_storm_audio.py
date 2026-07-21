"""Tests for utils/storm_audio.py."""

from __future__ import annotations

import wave

import numpy as np

from utils.storm_audio import SAMPLE_RATE, generate_rain_bed, write_wav


def test_generate_rain_bed_has_expected_shape_and_dtype():
    bed = generate_rain_bed(duration_s=2.0, seed=1, thunder_count=0)
    assert bed.shape == (int(2.0 * SAMPLE_RATE), 2)
    assert bed.dtype == np.float64


def test_generate_rain_bed_never_clips():
    bed = generate_rain_bed(duration_s=5.0, seed=7, thunder_count=3)
    assert np.max(np.abs(bed)) <= 1.0


def test_generate_rain_bed_is_deterministic_for_the_same_seed():
    a = generate_rain_bed(duration_s=1.0, seed=42, thunder_count=1)
    b = generate_rain_bed(duration_s=1.0, seed=42, thunder_count=1)
    assert np.array_equal(a, b)


def test_generate_rain_bed_differs_across_seeds():
    a = generate_rain_bed(duration_s=1.0, seed=1, thunder_count=0)
    b = generate_rain_bed(duration_s=1.0, seed=2, thunder_count=0)
    assert not np.array_equal(a, b)


def test_rain_bed_loops_seamlessly():
    """The sample-to-sample jump exactly at the loop seam must not be an
    outlier compared to ordinary adjacent-sample jumps elsewhere in the
    signal -- broadband noise has no reason to be smooth sample-to-sample
    (a fixed near-zero threshold would be wrong), but a real seam
    discontinuity would show up as a jump far outside the signal's normal
    range. The periodic-noise construction (see _periodic_noise's
    docstring) guarantees no such outlier for the bed itself; thunder
    bursts are kept away from the loop edges by generate_rain_bed's
    `margin_s`."""
    bed = generate_rain_bed(duration_s=8.0, seed=5, thunder_count=2)
    interior_jumps = np.abs(np.diff(bed, axis=0))
    p999 = np.quantile(interior_jumps, 0.999)
    seam_jump = np.abs(bed[0] - bed[-1])
    assert np.all(seam_jump <= p999 * 1.5)


def test_generate_rain_bed_with_zero_thunder_is_quieter_on_average():
    with_thunder = generate_rain_bed(duration_s=10.0, seed=9, thunder_count=3, thunder_level=0.9)
    without_thunder = generate_rain_bed(duration_s=10.0, seed=9, thunder_count=0)
    assert np.abs(with_thunder).max() >= np.abs(without_thunder).max()


def test_write_wav_round_trips_duration_and_channels(tmp_path):
    bed = generate_rain_bed(duration_s=1.5, seed=3, thunder_count=0)
    path = tmp_path / "rain.wav"

    write_wav(bed, path)

    with wave.open(str(path), "rb") as wav_file:
        assert wav_file.getnchannels() == 2
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == SAMPLE_RATE
        assert wav_file.getnframes() == bed.shape[0]
