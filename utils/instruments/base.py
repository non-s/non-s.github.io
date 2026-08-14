"""Base classes for procedural instrument rendering.

An :class:`Instrument` turns a :class:`NoteEvent` (MIDI note number, start,
duration, velocity) into a mono float64 numpy array. Subclasses implement
:meth:`Instrument.render`; :meth:`Instrument.render_chord` mixes several
notes into a single buffer with sample-accurate placement.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class NoteEvent:
    """A single MIDI note event."""

    note: int  # MIDI note number
    start: float  # start time in seconds
    duration: float  # duration in seconds
    velocity: float  # 0.0-1.0


class Instrument:
    """Base class for all procedural instruments."""

    name: str = "base"

    def render(self, note: NoteEvent, sample_rate: int = 44100) -> np.ndarray:
        """Render ``note`` into a mono float64 array of length ``duration*sample_rate``."""
        raise NotImplementedError

    def render_chord(self, notes: list[NoteEvent], sample_rate: int = 44100) -> np.ndarray:
        """Render a list of notes and mix them into one buffer.

        The buffer length covers the latest note end (``start + duration``).
        """
        if not notes:
            return np.zeros(1, dtype=np.float64)
        result = np.zeros(int(max(n.start + n.duration for n in notes) * sample_rate) + 1, dtype=np.float64)
        for n in notes:
            rendered = self.render(n, sample_rate)
            start_i = int(n.start * sample_rate)
            end_i = min(len(result), start_i + len(rendered))
            if end_i <= start_i:
                continue
            result[start_i:end_i] += rendered[: end_i - start_i]
        return result


def midi_to_hz(note: float) -> float:
    """Convert a MIDI note number to frequency in Hz (A4 = 69 = 440 Hz)."""
    return 440.0 * 2.0 ** ((note - 69.0) / 12.0)


def normalise(signal: np.ndarray) -> np.ndarray:
    """Peak-normalise a signal to roughly [-1, 1] unless it is silent."""
    peak = float(np.max(np.abs(signal))) if signal.size else 1.0
    if peak > 1e-12:
        signal = signal / peak
    return signal.astype(np.float64, copy=False)


def clamp(signal: np.ndarray, ceiling: float = 1.0) -> np.ndarray:
    """Hard-clip a signal to ``[-ceiling, ceiling]``."""
    return np.clip(signal, -ceiling, ceiling).astype(np.float64, copy=False)
