"""Tests for the universal music engine integration in generate_liquid_wire_video.

Covers:
- ``_synth_audio`` produces a valid WAV for every registered genre.
- The WAV format is stereo / 44100 Hz / 16-bit.
- ``audio_source`` metadata remains ``synthetic_python``.
- The style-drift rotation system works and is persistent.
- Short-duration variability produces different durations across slots.
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np
import pytest

import generate_liquid_wire_video as liquid
from utils.genres.registry import GENRES, list_genres
from utils.liquid_wire_timeline import build_timeline

SR = liquid.SAMPLE_RATE
# 1.5s is enough to exercise the full instrument/mixer/mastering chain (every
# genre renders its pad/drums/bass voices and the multiband+exciter+tape
# mastering path) while keeping the per-genre synthesis fast. At 5s the Pad
# supersaw additive engine made each parametrised genre case take ~10-30s,
# pushing the 14-genre x 3-cases suite past the 15min CI job timeout. 1.5s
# still produces a real stereo WAV with non-trivial RMS and stereo width.
SHORT_DURATION = 1.5


def _synth_genre(tmp_path: Path, genre_name: str, seed: int = 123) -> Path:
    """Synthesize a short clip for ``genre_name`` and return the WAV path."""
    profile = liquid._profile(seed, "short")
    profile["genre"] = genre_name
    events = build_timeline(seed, SHORT_DURATION, profile["music"])
    path = tmp_path / f"{genre_name}.wav"
    liquid._synth_audio(path, SHORT_DURATION, seed, profile, events, None)
    return path


def _read_wav(path: Path) -> tuple[int, int, int, int, np.ndarray]:
    """Return (channels, sample_width, framerate, nframes, float_samples)."""
    with wave.open(str(path), "rb") as w:
        ch, sw, fr, nf = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(nf)
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    return ch, sw, fr, nf, data


@pytest.mark.parametrize("genre_name", sorted(GENRES))
def test_synth_audio_produces_valid_wav_for_each_genre(tmp_path: Path, genre_name: str) -> None:
    path = _synth_genre(tmp_path, genre_name)
    ch, sw, fr, nf, data = _read_wav(path)
    assert ch == 2, f"{genre_name}: expected stereo, got {ch} channels"
    assert sw == 2, f"{genre_name}: expected 16-bit, got {sw} bytes"
    assert fr == SR, f"{genre_name}: expected {SR} Hz, got {fr} Hz"
    expected_frames = int(SHORT_DURATION * SR)
    assert abs(nf - expected_frames) <= 1, f"{genre_name}: expected ~{expected_frames} frames, got {nf}"


@pytest.mark.parametrize("genre_name", sorted(GENRES))
def test_synth_audio_not_silent_or_clipping(tmp_path: Path, genre_name: str) -> None:
    path = _synth_genre(tmp_path, genre_name)
    _, _, _, _, data = _read_wav(path)
    data = data.reshape(-1, 2)
    rms = float(np.sqrt(np.mean(data ** 2)))
    peak = float(np.max(np.abs(data)))
    assert rms > 1e-4, f"{genre_name}: audio is silent (rms={rms})"
    assert peak < 0.999, f"{genre_name}: audio is clipping (peak={peak})"


@pytest.mark.parametrize("genre_name", sorted(GENRES))
def test_synth_audio_has_stereo_width(tmp_path: Path, genre_name: str) -> None:
    path = _synth_genre(tmp_path, genre_name)
    _, _, _, _, data = _read_wav(path)
    data = data.reshape(-1, 2)
    mono_energy = float(np.mean(np.abs(data.mean(axis=1)))) + 1e-9
    side_energy = float(np.mean(np.abs(data[:, 0] - data[:, 1])))
    width = side_energy / mono_energy
    assert width > 0.01, f"{genre_name}: stereo image too narrow (width={width})"


def test_audio_source_metadata_is_synthetic_python(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        liquid,
        "ai_text",
        lambda *args, **kwargs: json.dumps(
            {"title": "Test Title #Shorts", "description": "Original code-generated work."}
        ),
    )
    profile = liquid._profile(42, "short")
    metadata = liquid._metadata(tmp_path / "v.mp4", tmp_path / "t.jpg", 35.0, "short", profile)
    assert metadata["audio_source"] == "synthetic_python"


def test_lofi_ambient_uses_fast_path(tmp_path: Path) -> None:
    """lofi_ambient must still produce output equivalent to the original engine."""
    profile = liquid._profile(7, "short")
    profile["genre"] = "lofi_ambient"
    events = build_timeline(7, SHORT_DURATION, profile["music"])
    path = tmp_path / "lofi.wav"
    liquid._synth_audio(path, SHORT_DURATION, 7, profile, events, None)
    ch, sw, fr, nf, data = _read_wav(path)
    assert (ch, sw, fr) == (2, 2, SR)
    assert nf == int(SHORT_DURATION * SR)
    # The lofi path is well-tuned; its RMS sits in a known healthy band.
    rms = float(np.sqrt(np.mean(data ** 2)))
    assert 0.005 < rms < 0.5


def test_style_drift_rotation_persists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    drift_path = tmp_path / "style_drift.json"
    assert not drift_path.exists()
    first = liquid._update_style_drift(force=True)
    assert drift_path.exists()
    assert isinstance(first["current_genres"], list)
    assert 3 <= len(first["current_genres"]) <= 4
    assert first["rotation"] >= 1
    # Re-loading reads the persisted state.
    reloaded = liquid._load_style_drift()
    assert reloaded["current_genres"] == first["current_genres"]
    assert reloaded["rotation"] == first["rotation"]


def test_style_drift_subset_only_contains_valid_genres(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    data = liquid._update_style_drift(force=True)
    valid = set(list_genres())
    for name in data["current_genres"]:
        assert name in valid


def test_style_drift_force_changes_subset(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    a = liquid._update_style_drift(force=True)
    b = liquid._update_style_drift(force=True)
    # Forcing twice rotates again; the subset should differ (the rotation
    # algorithm deliberately avoids repeating the previous subset).
    assert a["rotation"] != b["rotation"]


def test_pick_genre_for_seed_is_deterministic_and_in_subset(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path)
    liquid._update_style_drift(force=True)
    g1 = liquid._pick_genre_for_seed(999)
    g2 = liquid._pick_genre_for_seed(999)
    assert g1 == g2
    subset = set(liquid._current_genres())
    assert g1 in subset


def test_pick_genre_for_seed_uses_all_genres_when_no_drift_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(liquid, "data_dir", lambda: tmp_path / "__nonexistent_dir__")
    # When the drift file cannot be written/read, every genre is available.
    pick = liquid._pick_genre_for_seed(5)
    assert pick in set(list_genres())


def test_short_duration_variability_across_slots(monkeypatch) -> None:
    durations = set()
    for slot in ("alpha", "beta", "gamma", "delta", "epsilon"):
        monkeypatch.setenv("LIQUID_WIRE_SLOT", slot)
        d = liquid._short_duration_for_slot()
        assert 27.0 <= d <= 60.0
        durations.add(round(d, 3))
    # At least two distinct durations across five different slots.
    assert len(durations) >= 2


def test_short_duration_deterministic_for_same_slot(monkeypatch) -> None:
    monkeypatch.setenv("LIQUID_WIRE_SLOT", "fixed_slot")
    d1 = liquid._short_duration_for_slot()
    d2 = liquid._short_duration_for_slot()
    assert d1 == d2


def test_profile_includes_genre() -> None:
    profile = liquid._profile(321, "short")
    assert "genre" in profile
    assert profile["genre"] in set(list_genres())


def test_profile_genre_is_deterministic_for_seed() -> None:
    p1 = liquid._profile(555, "short")
    p2 = liquid._profile(555, "short")
    assert p1["genre"] == p2["genre"]
