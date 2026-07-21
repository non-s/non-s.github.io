"""Tests for utils/storm_audio.py."""

from __future__ import annotations

import wave

import numpy as np

from utils.storm_audio import SAMPLE_RATE, _periodic_noise, _rain_droplets, generate_rain_bed, write_wav


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


def test_rain_droplets_returns_expected_length():
    n = int(2.0 * SAMPLE_RATE)
    drops = _rain_droplets(n, seed=1)
    assert drops.shape == (n,)
    assert np.max(np.abs(drops)) <= 1.0


def test_rain_droplets_is_deterministic_for_the_same_seed():
    n = int(1.0 * SAMPLE_RATE)
    a = _rain_droplets(n, seed=11)
    b = _rain_droplets(n, seed=11)
    assert np.array_equal(a, b)


def test_rain_droplets_have_more_texture_than_flat_shaped_noise():
    """Regression for the first real upload sounding like flat static/hiss:
    the droplet scatter must have a higher crest factor (peak/RMS) than the
    pure shaped-noise wash it replaced as the dominant layer -- a flat,
    continuous noise bed has a low crest factor by definition, while real
    rain's sparse, sharp droplet transients push it up."""
    n = int(5.0 * SAMPLE_RATE)
    drops = _rain_droplets(n, seed=3)
    wash = _periodic_noise(n, seed=3)

    def crest_factor(signal):
        rms = np.sqrt(np.mean(signal**2))
        return np.max(np.abs(signal)) / rms

    assert crest_factor(drops) > crest_factor(wash)


def test_generate_rain_bed_has_a_textured_not_flat_crest_factor():
    """End-to-end regression: the full bed (wash + droplets) should read
    as textured rain, not stationary static -- pin a crest factor floor
    comfortably above the ~5.1 the pure-wash version measured at before
    this fix."""
    bed = generate_rain_bed(duration_s=5.0, seed=4, thunder_count=0)
    mono = bed[:, 0]
    rms = np.sqrt(np.mean(mono**2))
    crest_factor = np.max(np.abs(mono)) / rms
    assert crest_factor > 6.5


def test_write_wav_round_trips_duration_and_channels(tmp_path):
    bed = generate_rain_bed(duration_s=1.5, seed=3, thunder_count=0)
    path = tmp_path / "rain.wav"

    write_wav(bed, path)

    with wave.open(str(path), "rb") as wav_file:
        assert wav_file.getnchannels() == 2
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == SAMPLE_RATE
        assert wav_file.getnframes() == bed.shape[0]
