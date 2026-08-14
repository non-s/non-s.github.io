"""Tests for the procedural instrument library."""

from __future__ import annotations

import numpy as np

from utils.instruments import drums as drum_mod
from utils.instruments import keys, strings, synth, winds
from utils.instruments.base import NoteEvent

SR = 44100


def _make_note(note: int = 60, duration: float = 0.4, velocity: float = 0.8) -> NoteEvent:
    return NoteEvent(note=note, start=0.0, duration=duration, velocity=velocity)


def _assert_valid(signal: np.ndarray, expected_len: int | None = None) -> None:
    assert signal.dtype == np.float64
    assert signal.ndim == 1
    if expected_len is not None:
        assert abs(signal.shape[0] - expected_len) <= 1
    assert np.all(np.abs(signal) <= 1.0 + 1e-6), f"peak {float(np.max(np.abs(signal)))}"


def test_acoustic_piano_render() -> None:
    inst = keys.AcousticPiano(seed=42)
    note = _make_note(60, 0.4, 0.8)
    y = inst.render(note, SR)
    _assert_valid(y, int(0.4 * SR))


def test_acoustic_piano_determinism() -> None:
    inst = keys.AcousticPiano(seed=42)
    note = _make_note(60, 0.3, 0.7)
    a = inst.render(note, SR)
    b = inst.render(note, SR)
    assert np.array_equal(a, b)


def test_electric_piano_render() -> None:
    inst = keys.ElectricPiano(seed=1)
    y = inst.render(_make_note(64, 0.5), SR)
    _assert_valid(y, int(0.5 * SR))


def test_organ_render() -> None:
    inst = keys.Organ(leslie=True, seed=2)
    y = inst.render(_make_note(67, 0.6), SR)
    _assert_valid(y, int(0.6 * SR))


def test_organ_determinism() -> None:
    inst = keys.Organ(leslie=False, seed=2)
    a = inst.render(_make_note(67, 0.4), SR)
    b = inst.render(_make_note(67, 0.4), SR)
    assert np.array_equal(a, b)


def test_clavinet_render() -> None:
    inst = keys.Clavinet(seed=3)
    y = inst.render(_make_note(72, 0.3), SR)
    _assert_valid(y, int(0.3 * SR))


def test_harpsichord_render() -> None:
    inst = keys.Harpsichord(seed=4)
    y = inst.render(_make_note(55, 0.5), SR)
    _assert_valid(y, int(0.5 * SR))


def test_string_ensemble_render() -> None:
    inst = strings.StringEnsemble(seed=5)
    y = inst.render(_make_note(60, 0.8), SR)
    _assert_valid(y, int(0.8 * SR))


def test_brass_section_render() -> None:
    inst = strings.BrassSection(seed=6)
    y = inst.render(_make_note(62, 0.6), SR)
    _assert_valid(y, int(0.6 * SR))


def test_acoustic_guitar_render() -> None:
    inst = strings.AcousticGuitar(seed=7)
    y = inst.render(_make_note(57, 0.5), SR)
    _assert_valid(y, int(0.5 * SR))


def test_distorted_guitar_render() -> None:
    inst = strings.DistortedGuitar(seed=8, palm_mute=False)
    y = inst.render(_make_note(52, 0.4), SR)
    _assert_valid(y, int(0.4 * SR))


def test_distorted_guitar_palm_mute_shorter() -> None:
    open_inst = strings.DistortedGuitar(seed=8, palm_mute=False)
    mute_inst = strings.DistortedGuitar(seed=8, palm_mute=True)
    note = _make_note(52, 0.4, 0.8)
    y_open = open_inst.render(note, SR)
    y_mute = mute_inst.render(note, SR)
    # The palm-muted note should decay faster: less energy in the second half.
    half = y_open.size // 2
    energy_open = float(np.sum(y_open[half:] ** 2))
    energy_mute = float(np.sum(y_mute[half:] ** 2))
    assert energy_mute < energy_open


def test_bass_guitar_render() -> None:
    inst = strings.BassGuitar(seed=9)
    y = inst.render(_make_note(40, 0.4), SR)
    _assert_valid(y, int(0.4 * SR))


def test_sitar_render() -> None:
    inst = strings.Sitar(seed=10)
    y = inst.render(_make_note(60, 0.6), SR)
    _assert_valid(y, int(0.6 * SR))


def test_pad_render() -> None:
    inst = synth.Pad(seed=11)
    y = inst.render(_make_note(60, 1.0), SR)
    _assert_valid(y, int(1.0 * SR))


def test_lead_render() -> None:
    inst = synth.Lead(seed=12, waveform="saw")
    y = inst.render(_make_note(72, 0.5), SR)
    _assert_valid(y, int(0.5 * SR))


def test_sub_bass_render() -> None:
    inst = synth.SubBass(seed=13)
    y = inst.render(_make_note(28, 0.5), SR)
    _assert_valid(y, int(0.5 * SR))


def test_synth_bass_render() -> None:
    inst = synth.SynthBass(seed=14)
    y = inst.render(_make_note(36, 0.4), SR)
    _assert_valid(y, int(0.4 * SR))


def test_bell_render() -> None:
    inst = synth.Bell(seed=15)
    y = inst.render(_make_note(72, 0.8), SR)
    _assert_valid(y, int(0.8 * SR))


def test_mallet_render() -> None:
    inst = synth.Mallet(seed=16)
    y = inst.render(_make_note(69, 0.5), SR)
    _assert_valid(y, int(0.5 * SR))


def test_choir_render() -> None:
    inst = synth.Choir(seed=17, vowel="a")
    y = inst.render(_make_note(60, 1.0), SR)
    _assert_valid(y, int(1.0 * SR))


def test_flute_render() -> None:
    inst = winds.Flute(seed=18)
    y = inst.render(_make_note(74, 0.5), SR)
    _assert_valid(y, int(0.5 * SR))


def test_kalimba_render() -> None:
    inst = winds.Kalimba(seed=19)
    y = inst.render(_make_note(64, 0.4), SR)
    _assert_valid(y, int(0.4 * SR))


def test_kick_808_render_hit() -> None:
    drum = drum_mod.Kick808()
    y = drum.render_hit(velocity=1.0, duration=0.5, sample_rate=SR)
    _assert_valid(y, int(0.5 * SR))


def test_snare_render_hit() -> None:
    drum = drum_mod.Snare()
    y = drum.render_hit(velocity=1.0, duration=0.2, sample_rate=SR)
    _assert_valid(y, int(0.2 * SR))


def test_clap_render_hit() -> None:
    drum = drum_mod.Clap()
    y = drum.render_hit(velocity=1.0, duration=0.2, sample_rate=SR)
    _assert_valid(y, int(0.2 * SR))


def test_hihat_closed_vs_open() -> None:
    closed = drum_mod.HiHat(open_hat=False, seed=0)
    open_hat = drum_mod.HiHat(open_hat=True, seed=0)
    y_closed = closed.render_hit(velocity=1.0, sample_rate=SR)
    y_open = open_hat.render_hit(velocity=1.0, sample_rate=SR)
    # Open hat should be longer (default 0.4s) than closed (default 0.08s).
    assert y_open.size > y_closed.size


def test_crash_render_hit() -> None:
    drum = drum_mod.Crash()
    y = drum.render_hit(velocity=1.0, duration=1.0, sample_rate=SR)
    _assert_valid(y, int(1.0 * SR))


def test_ride_render_hit() -> None:
    drum = drum_mod.Ride()
    y = drum.render_hit(velocity=1.0, duration=1.0, sample_rate=SR)
    _assert_valid(y, int(1.0 * SR))


def test_tom_render_hit() -> None:
    drum = drum_mod.Tom()
    y = drum.render_hit(velocity=1.0, duration=0.4, sample_rate=SR)
    _assert_valid(y, int(0.4 * SR))


def test_tabla_render_hit() -> None:
    drum = drum_mod.Tabla()
    y = drum.render_hit(velocity=1.0, duration=0.4, sample_rate=SR)
    _assert_valid(y, int(0.4 * SR))


def test_timpani_render_hit() -> None:
    drum = drum_mod.Timpani()
    y = drum.render_hit(velocity=1.0, duration=1.0, sample_rate=SR)
    _assert_valid(y, int(1.0 * SR))


def test_drum_render_via_note_event() -> None:
    drum = drum_mod.Tom()
    note = NoteEvent(note=60, start=0.0, duration=0.4, velocity=0.9)
    y = drum.render(note, SR)
    _assert_valid(y)


def test_drum_pitch_factor_changes_length() -> None:
    drum = drum_mod.Tom()
    low = drum.render(NoteEvent(note=48, start=0.0, duration=0.4, velocity=0.9), SR)
    high = drum.render(NoteEvent(note=72, start=0.0, duration=0.4, velocity=0.9), SR)
    # Higher note => pitch factor > 1 => resampled to fewer samples.
    assert high.size <= low.size


def test_render_chord_mixes_notes() -> None:
    inst = keys.AcousticPiano(seed=0)
    notes = [
        NoteEvent(note=60, start=0.0, duration=0.3, velocity=0.7),
        NoteEvent(note=64, start=0.0, duration=0.3, velocity=0.7),
        NoteEvent(note=67, start=0.0, duration=0.3, velocity=0.7),
    ]
    y = inst.render_chord(notes, SR)
    assert y.dtype == np.float64
    assert y.ndim == 1
    # Chord should have more energy than a single note.
    single = inst.render(notes[0], SR)
    assert float(np.sum(y ** 2)) > float(np.sum(single ** 2))


def test_drum_determinism() -> None:
    drum = drum_mod.Kick808()
    a = drum.render_hit(velocity=1.0, duration=0.5, sample_rate=SR)
    b = drum.render_hit(velocity=1.0, duration=0.5, sample_rate=SR)
    assert np.array_equal(a, b)
