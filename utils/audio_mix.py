"""Mixing engine: buses, EQ, compression, panning, reverb sends, sidechain.

The :class:`Mixer` collects rendered mono signals into named buses (drums,
bass, keys, guitar, pads, lead, percussion, fx), applies a 3-band EQ, per-bus
compression, constant-power panning, reverb sends to a shared
:class:`~utils.dsp.reverb.Freeverb`, optional sidechain ducking, and finally
sums everything through a master bus with a master compressor and brick-wall
limiter. Output is a stereo float64 numpy array of shape ``(2, N)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from utils.dsp.dynamics import Compressor, Limiter, SideChainDuck
from utils.dsp.filters import BiquadFilter
from utils.dsp.reverb import Freeverb

SR = 44100

# Canonical bus names recognised by the mixer.
BUS_NAMES: tuple[str, ...] = ("drums", "bass", "keys", "guitar", "pads", "lead", "percussion", "fx")

# EQ centre/crossover frequencies (Hz).
_LOW_FREQ = 200.0
_MID_FREQ = 1000.0
_HIGH_FREQ = 5000.0


@dataclass
class Bus:
    """A single mixer bus with gain, pan, EQ, dynamics and send controls."""

    gain: float = 1.0
    pan: float = 0.0  # -1 (left) to 1 (right)
    eq_low: float = 0.0  # dB cut/boost at 200 Hz (low shelf)
    eq_mid: float = 0.0  # dB cut/boost at 1 kHz (mid peak)
    eq_high: float = 0.0  # dB cut/boost at 5 kHz (high shelf)
    compressor: Compressor | None = None
    reverb_send: float = 0.0  # 0.0-1.0
    sidechain: SideChainDuck | None = None
    # Filled in by the mixer during render.
    _buffer: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float64), repr=False)


def _db_to_gain(db: float) -> float:
    return 10.0 ** (float(db) / 20.0)


def _pad_or_trim(signal: np.ndarray, n: int) -> np.ndarray:
    """Return a mono float64 array of length ``n`` (zero-padded or trimmed)."""
    x = np.asarray(signal, dtype=np.float64).ravel()
    if x.size == n:
        return x
    if x.size < n:
        out = np.zeros(n, dtype=np.float64)
        out[: x.size] = x
        return out
    return x[:n]


def _apply_eq(signal: np.ndarray, low_db: float, mid_db: float, high_db: float, sr: int) -> np.ndarray:
    """Apply a 3-band EQ (low shelf, mid peak, high shelf) to a mono signal."""
    x = np.asarray(signal, dtype=np.float64).ravel()
    # Low shelf at 200 Hz (approximated with a lowpass+gain blend).
    if abs(low_db) > 1e-6:
        low = BiquadFilter("lowpass", _LOW_FREQ, 0.707, sr).process(x)
        x = x + (_db_to_gain(low_db) - 1.0) * low
    # Mid peak at 1 kHz (bandpass blend).
    if abs(mid_db) > 1e-6:
        mid = BiquadFilter("bandpass", _MID_FREQ, 1.0, sr).process(x)
        x = x + (_db_to_gain(mid_db) - 1.0) * mid
    # High shelf at 5 kHz (highpass blend).
    if abs(high_db) > 1e-6:
        high = BiquadFilter("highpass", _HIGH_FREQ, 0.707, sr).process(x)
        x = x + (_db_to_gain(high_db) - 1.0) * high
    return x


def _constant_power_pan(pan: float) -> tuple[float, float]:
    """Return (left_gain, right_gain) for constant-power panning in [-1, 1]."""
    p = float(np.clip(pan, -1.0, 1.0))
    # Map [-1, 1] -> [0, pi/2].
    angle = (p + 1.0) * 0.25 * np.pi
    return float(np.cos(angle)), float(np.sin(angle))


class Mixer:
    """Multi-bus mixer with EQ, compression, panning, reverb and sidechain.

    Buses are created lazily for any name in :data:`BUS_NAMES`; a master bus is
    always present. Use :meth:`add_track` to accumulate rendered signals onto a
    bus, then :meth:`render` to produce the final stereo mix.
    """

    def __init__(self, sample_rate: int = SR) -> None:
        self.sample_rate = int(sample_rate)
        self.buses: dict[str, Bus] = {name: Bus() for name in BUS_NAMES}
        self.master = Bus(gain=1.0)
        self._tracks: list[tuple[str, np.ndarray]] = []
        self._reverb = Freeverb(room_size=0.7, damping=0.5, wet=0.3, dry=0.0, width=0.5, sample_rate=sample_rate)
        self._master_compressor = Compressor(-6.0, 2.0, 10.0, 100.0, makeup_gain=1.2, sample_rate=sample_rate)
        self._limiter = Limiter(ceiling=0.98, attack_ms=1.0, release_ms=50.0, sample_rate=sample_rate)

    def configure_bus(self, name: str, **kwargs: object) -> None:
        """Update parameters on bus ``name`` (gain, pan, eq_*, reverb_send, ...)."""
        if name not in self.buses:
            raise ValueError(f"unknown bus {name!r}; valid: {BUS_NAMES}")
        bus = self.buses[name]
        for key, value in kwargs.items():
            if key == "compressor":
                bus.compressor = value  # type: ignore[assignment]
            elif key == "sidechain":
                bus.sidechain = value  # type: ignore[assignment]
            else:
                setattr(bus, key, value)

    def configure_reverb(self, **kwargs: object) -> None:
        """Rebuild the shared Freeverb with the given parameters."""
        params: dict[str, object] = {
            "room_size": self._reverb.room_size,
            "damping": self._reverb.damping,
            "wet": self._reverb.wet,
            "dry": self._reverb.dry,
            "width": self._reverb.width,
            "sample_rate": self.sample_rate,
        }
        params.update(kwargs)
        self._reverb = Freeverb(**params)  # type: ignore[arg-type]

    def configure_master(
        self,
        *,
        compressor: Compressor | None = None,
        limiter: Limiter | None = None,
        gain: float | None = None,
    ) -> None:
        if compressor is not None:
            self._master_compressor = compressor
        if limiter is not None:
            self._limiter = limiter
        if gain is not None:
            self.master.gain = float(gain)

    def add_track(self, name: str, signal: np.ndarray, bus_name: str) -> None:
        """Add a rendered ``signal`` to bus ``bus_name``."""
        if bus_name not in self.buses:
            raise ValueError(f"unknown bus {bus_name!r}; valid: {BUS_NAMES}")
        self._tracks.append((bus_name, np.asarray(signal, dtype=np.float64).ravel()))

    def _sum_buses(self, n: int) -> dict[str, np.ndarray]:
        """Sum all tracks into per-bus mono buffers of length ``n``."""
        buffers: dict[str, np.ndarray] = {name: np.zeros(n, dtype=np.float64) for name in self.buses}
        for bus_name, signal in self._tracks:
            padded = _pad_or_trim(signal, n)
            buffers[bus_name] += padded
        return buffers

    def render(self, sample_rate: int = SR) -> np.ndarray:
        """Render the full mix to a stereo float64 array of shape ``(2, N)``."""
        sr = int(sample_rate)
        if not self._tracks:
            return np.zeros((2, 1), dtype=np.float64)
        n = max(signal.size for _, signal in self._tracks)
        if n <= 0:
            return np.zeros((2, 1), dtype=np.float64)
        bus_buffers = self._sum_buses(n)

        # Detect sidechain sources (e.g. drums bus) before processing.
        sidechain_spec: list[tuple[str, str, SideChainDuck]] = []
        for bus_name, bus in self.buses.items():
            if bus.sidechain is not None:
                sidechain_spec.append((bus_name, bus_name, bus.sidechain))

        # Apply sidechain ducking: duck a bus based on another bus's signal.
        for target_bus, _source_bus, duck in sidechain_spec:
            # Use the drums bus as the sidechain source by convention.
            source_sig = bus_buffers.get("drums", np.zeros(n, dtype=np.float64))
            target_sig = bus_buffers.get(target_bus, np.zeros(n, dtype=np.float64))
            ducked = SideChainDuck(
                source=source_sig,
                target=target_sig,
                threshold=duck.threshold,
                ratio=duck.ratio,
                attack_ms=duck.attack_ms,
                release_ms=duck.release_ms,
                sample_rate=sr,
            ).process()
            bus_buffers[target_bus] = _pad_or_trim(ducked, n)

        # Build the reverb send bus (sum of all sends pre-fader).
        reverb_input = np.zeros(n, dtype=np.float64)
        for bus_name, bus in self.buses.items():
            send = float(np.clip(bus.reverb_send, 0.0, 1.0))
            if send > 1e-6:
                reverb_input += send * bus_buffers[bus_name]

        # Process each bus: EQ -> compressor -> gain -> pan -> accumulate.
        left = np.zeros(n, dtype=np.float64)
        right = np.zeros(n, dtype=np.float64)
        for bus_name, bus in self.buses.items():
            buf = bus_buffers[bus_name]
            if np.max(np.abs(buf)) < 1e-12:
                continue
            buf = _apply_eq(buf, bus.eq_low, bus.eq_mid, bus.eq_high, sr)
            if bus.compressor is not None:
                buf = bus.compressor.process(buf)
            buf = buf * float(np.clip(bus.gain, 0.0, 4.0))
            l_gain, r_gain = _constant_power_pan(bus.pan)
            left += l_gain * buf
            right += r_gain * buf

        # Reverb return (stereo): process the send sum through Freeverb.
        if np.max(np.abs(reverb_input)) > 1e-12:
            wet_stereo = self._reverb.process(np.stack([reverb_input, reverb_input], axis=1))
            wet = np.asarray(wet_stereo, dtype=np.float64)
            if wet.ndim == 1:
                wet = np.stack([wet, wet], axis=1)
            left += wet[:, 0]
            right += wet[:, 1]

        # Sum to master and apply master compressor + limiter (per channel).
        left = left * float(np.clip(self.master.gain, 0.0, 4.0))
        right = right * float(np.clip(self.master.gain, 0.0, 4.0))
        left = self._master_compressor.process(left)
        right = self._master_compressor.process(right)
        left = self._limiter.process(left)
        right = self._limiter.process(right)

        return np.stack([left, right], axis=0).astype(np.float64)
