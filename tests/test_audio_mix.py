"""Tests for the mixing engine (buses, pan, reverb, sidechain, limiter)."""

from __future__ import annotations

import numpy as np

from utils.audio_mix import BUS_NAMES, Bus, Mixer
from utils.dsp.dynamics import Compressor, SideChainDuck
from utils.dsp.oscillators import noise_white, sine

SR = 44100


def _sine(freq: float, dur: float = 0.5, amp: float = 0.5) -> np.ndarray:
    return sine(freq, dur, SR) * amp


def test_mixer_with_simple_signals() -> None:
    mixer = Mixer(sample_rate=SR)
    mixer.add_track("kick", _sine(60.0), "drums")
    mixer.add_track("bass", _sine(80.0), "bass")
    out = mixer.render(SR)
    assert out.shape[0] == 2
    assert out.dtype == np.float64
    assert out.shape[1] > 0
    assert float(np.max(np.abs(out))) > 0.0


def test_stereo_output_shape() -> None:
    mixer = Mixer(sample_rate=SR)
    mixer.add_track("sig", _sine(440.0, 1.0), "lead")
    out = mixer.render(SR)
    assert out.shape == (2, SR)


def test_empty_mixer_returns_silence() -> None:
    mixer = Mixer(sample_rate=SR)
    out = mixer.render(SR)
    assert out.shape[0] == 2
    assert float(np.max(np.abs(out))) == 0.0


def test_constant_power_pan_centre_is_equal() -> None:
    from utils.audio_mix import _constant_power_pan

    left, right = _constant_power_pan(0.0)
    assert abs(left - right) < 1e-9
    assert abs(left - (2 ** 0.5 / 2.0)) < 1e-6


def test_constant_power_pan_left_attenuates_right() -> None:
    from utils.audio_mix import _constant_power_pan

    left, right = _constant_power_pan(-1.0)
    assert left > right
    assert abs(right) < 1e-6
    assert abs(left - 1.0) < 1e-6


def test_constant_power_pan_right_attenuates_left() -> None:
    from utils.audio_mix import _constant_power_pan

    left, right = _constant_power_pan(1.0)
    assert right > left
    assert abs(left) < 1e-6
    assert abs(right - 1.0) < 1e-6


def test_pan_affects_stereo_balance() -> None:
    mixer_left = Mixer(sample_rate=SR)
    mixer_left.configure_bus("lead", pan=-1.0, reverb_send=0.0)
    mixer_left.add_track("sig", _sine(440.0, 0.5), "lead")
    out_left = mixer_left.render(SR)

    mixer_right = Mixer(sample_rate=SR)
    mixer_right.configure_bus("lead", pan=1.0, reverb_send=0.0)
    mixer_right.add_track("sig", _sine(440.0, 0.5), "lead")
    out_right = mixer_right.render(SR)

    left_energy = float(np.sum(out_left[0] ** 2))
    right_energy = float(np.sum(out_right[1] ** 2))
    # Panned-left mix should have more energy on the left channel than right.
    assert float(np.sum(out_left[0] ** 2)) > float(np.sum(out_left[1] ** 2))
    assert float(np.sum(out_right[1] ** 2)) > float(np.sum(out_right[0] ** 2))
    assert left_energy > 0.0
    assert right_energy > 0.0


def test_reverb_send_adds_wet_signal() -> None:
    mixer_dry = Mixer(sample_rate=SR)
    mixer_dry.configure_bus("pads", reverb_send=0.0)
    mixer_dry.add_track("pad", _sine(440.0, 0.5), "pads")
    out_dry = mixer_dry.render(SR)

    mixer_wet = Mixer(sample_rate=SR)
    mixer_wet.configure_reverb(room_size=0.9, damping=0.3, wet=0.8, width=0.5)
    mixer_wet.configure_bus("pads", reverb_send=1.0)
    mixer_wet.add_track("pad", _sine(440.0, 0.5), "pads")
    out_wet = mixer_wet.render(SR)

    # The wet mix should have more total energy (dry + reverb tail) than dry.
    dry_energy = float(np.sum(out_dry ** 2))
    wet_energy = float(np.sum(out_wet ** 2))
    assert wet_energy > dry_energy


def test_sidechain_ducking_reduces_bass_when_kick_hits() -> None:
    mixer = Mixer(sample_rate=SR)
    # Loud continuous bass.
    bass = _sine(80.0, 0.5, amp=0.8)
    # Kick-like transient at the very start.
    kick = np.zeros(int(0.5 * SR), dtype=np.float64)
    kick[: int(0.05 * SR)] = _sine(60.0, 0.05, amp=1.0)
    mixer.add_track("kick", kick, "drums")
    mixer.add_track("bass", bass, "bass")

    # Render without sidechain first.
    mixer_no_sc = Mixer(sample_rate=SR)
    mixer_no_sc.add_track("kick", kick, "drums")
    mixer_no_sc.add_track("bass", bass, "bass")
    mixer_no_sc.configure_bus("bass", reverb_send=0.0)
    mixer_no_sc.configure_bus("drums", reverb_send=0.0)
    out_no_sc = mixer_no_sc.render(SR)

    # Render with sidechain ducking on bass driven by drums.
    duck = SideChainDuck(
        source=np.zeros(1, dtype=np.float64),
        target=np.zeros(1, dtype=np.float64),
        threshold=-40.0,
        ratio=8.0,
        attack_ms=2.0,
        release_ms=80.0,
        sample_rate=SR,
    )
    mixer_sc = Mixer(sample_rate=SR)
    mixer_sc.add_track("kick", kick, "drums")
    mixer_sc.add_track("bass", bass, "bass")
    mixer_sc.configure_bus("drums", reverb_send=0.0)
    mixer_sc.configure_bus("bass", reverb_send=0.0, sidechain=duck)
    out_sc = mixer_sc.render(SR)

    # Compare bass energy in the first 50 ms (where the kick transient is).
    window = int(0.05 * SR)
    bass_no_sc = float(np.sum(out_no_sc[:, :window] ** 2))
    bass_sc = float(np.sum(out_sc[:, :window] ** 2))
    assert bass_sc < bass_no_sc, "sidechain did not reduce bass during kick"


def test_master_limiter_prevents_clipping() -> None:
    mixer = Mixer(sample_rate=SR)
    # Stack many loud signals to force clipping pre-limiter.
    for _ in range(8):
        mixer.add_track("loud", noise_white(0.5, SR, seed=1) * 0.9, "drums")
    out = mixer.render(SR)
    peak = float(np.max(np.abs(out)))
    assert peak <= 0.98 + 1e-6, f"limiter failed to prevent clipping: peak={peak}"


def test_add_track_unknown_bus_raises() -> None:
    mixer = Mixer(sample_rate=SR)
    try:
        mixer.add_track("sig", _sine(440.0), "nonexistent_bus")
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown bus")


def test_configure_bus_updates_parameters() -> None:
    mixer = Mixer(sample_rate=SR)
    mixer.configure_bus("drums", gain=1.5, pan=0.3, eq_low=2.0, reverb_send=0.2)
    bus = mixer.buses["drums"]
    assert bus.gain == 1.5
    assert bus.pan == 0.3
    assert bus.eq_low == 2.0
    assert bus.reverb_send == 0.2


def test_configure_reverb_changes_room_size() -> None:
    mixer = Mixer(sample_rate=SR)
    mixer.configure_reverb(room_size=0.95, damping=0.1, wet=0.6, width=0.9)
    assert mixer._reverb.room_size == 0.95
    assert mixer._reverb.damping == 0.1
    assert mixer._reverb.wet == 0.6
    assert mixer._reverb.width == 0.9


def test_all_bus_names_present() -> None:
    mixer = Mixer(sample_rate=SR)
    for name in BUS_NAMES:
        assert name in mixer.buses


def test_bus_dataclass_defaults() -> None:
    bus = Bus()
    assert bus.gain == 1.0
    assert bus.pan == 0.0
    assert bus.eq_low == 0.0
    assert bus.eq_mid == 0.0
    assert bus.eq_high == 0.0
    assert bus.compressor is None
    assert bus.reverb_send == 0.0
    assert bus.sidechain is None


def test_bus_compressor_applied() -> None:
    mixer = Mixer(sample_rate=SR)
    comp = Compressor(-10.0, 4.0, 5.0, 50.0, makeup_gain=1.0, sample_rate=SR)
    mixer.configure_bus("lead", compressor=comp, reverb_send=0.0)
    mixer.add_track("sig", _sine(440.0, 0.5, amp=0.9), "lead")
    out = mixer.render(SR)
    # Compressor should reduce the peak relative to the raw signal.
    raw_peak = float(np.max(np.abs(_sine(440.0, 0.5, amp=0.9))))
    out_peak = float(np.max(np.abs(out)))
    assert out_peak <= raw_peak + 1e-6


def test_mixer_determinism() -> None:
    def build() -> np.ndarray:
        m = Mixer(sample_rate=SR)
        m.add_track("a", _sine(440.0, 0.3), "lead")
        m.add_track("b", _sine(80.0, 0.3), "bass")
        m.configure_bus("lead", reverb_send=0.0)
        m.configure_bus("bass", reverb_send=0.0)
        return m.render(SR)

    a = build()
    b = build()
    assert np.allclose(a, b)
