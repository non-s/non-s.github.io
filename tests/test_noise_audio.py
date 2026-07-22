"""Tests for utils/noise_audio.py."""

from __future__ import annotations

import wave

import numpy as np
import pytest

from utils.noise_audio import NOISE_COLORS, SAMPLE_RATE, generate_noise_bed, write_wav


def test_generate_noise_bed_has_expected_shape_and_dtype():
    bed = generate_noise_bed(duration_s=2.0, seed=1, color="brown")
    assert bed.shape == (int(2.0 * SAMPLE_RATE), 2)
    assert bed.dtype == np.float64


def test_generate_noise_bed_never_clips():
    for color in NOISE_COLORS:
        bed = generate_noise_bed(duration_s=2.0, seed=7, color=color, level=1.0)
        assert np.max(np.abs(bed)) <= 1.0


def test_generate_noise_bed_is_deterministic_for_the_same_seed():
    a = generate_noise_bed(duration_s=1.0, seed=42, color="pink")
    b = generate_noise_bed(duration_s=1.0, seed=42, color="pink")
    assert np.array_equal(a, b)


def test_generate_noise_bed_differs_across_seeds():
    a = generate_noise_bed(duration_s=1.0, seed=1, color="white")
    b = generate_noise_bed(duration_s=1.0, seed=2, color="white")
    assert not np.array_equal(a, b)


def test_generate_noise_bed_rejects_unknown_color():
    with pytest.raises(ValueError):
        generate_noise_bed(duration_s=1.0, color="ultraviolet")


def test_noise_bed_loops_seamlessly():
    """Same reasoning as test_storm_audio.py's identical test: the
    periodic-FFT construction guarantees the seam jump is not an outlier
    compared to ordinary adjacent-sample jumps."""
    for color in NOISE_COLORS:
        bed = generate_noise_bed(duration_s=8.0, seed=5, color=color)
        interior_jumps = np.abs(np.diff(bed, axis=0))
        p999 = np.quantile(interior_jumps, 0.999)
        seam_jump = np.abs(bed[0] - bed[-1])
        assert np.all(seam_jump <= p999 * 1.5)


def _octave_band_db(mono: np.ndarray, sample_rate: int) -> np.ndarray:
    spectrum = np.abs(np.fft.rfft(mono))
    freqs = np.fft.rfftfreq(len(mono), d=1.0 / sample_rate)
    bands = [100, 200, 400, 800, 1600, 3200, 6400]
    psds = []
    for lo, hi in zip(bands[:-1], bands[1:]):
        mask = (freqs >= lo) & (freqs < hi)
        psds.append(np.mean(spectrum[mask] ** 2))
    psds = np.array(psds)
    return 10 * np.log10(psds / psds[0])


def test_white_noise_has_flat_spectrum():
    bed = generate_noise_bed(duration_s=10.0, seed=1, color="white", level=1.0)
    db = _octave_band_db(bed[:, 0], SAMPLE_RATE)
    # Flat PSD: every octave band within a couple dB of the first.
    assert np.all(np.abs(db) < 3.0)


def test_pink_noise_rolls_off_about_3db_per_octave():
    bed = generate_noise_bed(duration_s=10.0, seed=1, color="pink", level=1.0)
    db = _octave_band_db(bed[:, 0], SAMPLE_RATE)
    # 5 octaves out from the first band -> ~ -15dB at -3dB/octave.
    assert -18.0 < db[-1] < -12.0


def test_brown_noise_rolls_off_about_6db_per_octave():
    bed = generate_noise_bed(duration_s=10.0, seed=1, color="brown", level=1.0)
    db = _octave_band_db(bed[:, 0], SAMPLE_RATE)
    # 5 octaves out -> ~ -30dB at -6dB/octave.
    assert -36.0 < db[-1] < -24.0


def test_brown_noise_rolls_off_faster_than_pink_which_rolls_off_faster_than_white():
    white = _octave_band_db(generate_noise_bed(duration_s=10.0, seed=2, color="white", level=1.0)[:, 0], SAMPLE_RATE)
    pink = _octave_band_db(generate_noise_bed(duration_s=10.0, seed=2, color="pink", level=1.0)[:, 0], SAMPLE_RATE)
    brown = _octave_band_db(generate_noise_bed(duration_s=10.0, seed=2, color="brown", level=1.0)[:, 0], SAMPLE_RATE)
    assert brown[-1] < pink[-1] < white[-1]


def test_write_wav_round_trips_duration_and_channels(tmp_path):
    bed = generate_noise_bed(duration_s=1.5, seed=3, color="brown")
    path = tmp_path / "noise.wav"

    write_wav(bed, path)

    with wave.open(str(path), "rb") as wav_file:
        assert wav_file.getnchannels() == 2
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == SAMPLE_RATE
        assert wav_file.getnframes() == bed.shape[0]
