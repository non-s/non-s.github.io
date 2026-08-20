"""Perceptual-intent novelty checks for composition plans before rendering."""

from __future__ import annotations

from typing import Any

import numpy as np

AUDIO_PLAN_VECTOR_VERSION = 1
AUDIO_PLAN_MIN_DISTANCE = 0.035


def _hist(values: list[int], size: int) -> list[float]:
    counts = np.zeros(size, dtype=np.float64)
    for value in values:
        counts[value % size] += 1
    total = float(counts.sum())
    return (counts / total if total else counts).round(6).tolist()


def audio_plan_vector(composition: Any) -> list[float]:
    """Return a duration-independent 44-dimensional musical fingerprint."""
    notes = sorted(getattr(composition, "notes", ()), key=lambda n: (float(n.start), str(n.voice)))
    pitches = [int(note.note) for note in notes]
    intervals = [pitches[index] - pitches[index - 1] for index in range(1, len(pitches))]
    beat = max(.001, float(getattr(composition, "beat_seconds", 1.0)))
    starts = [int(round(float(note.start) / beat * 4)) for note in notes]
    durations = [min(3, int(float(note.duration) / beat * 2)) for note in notes]
    voice_counts: dict[str, int] = {}
    for note in notes:
        voice = str(note.voice).split(":", 1)[0]
        voice_counts[voice] = voice_counts.get(voice, 0) + 1
    voice_hist = sorted(voice_counts.values(), reverse=True)[:4]
    voice_hist += [0] * (4 - len(voice_hist))
    voice_total = max(1, sum(voice_hist))
    globals_ = [
        min(1.0, len(notes) / 512),
        min(1.0, len(voice_counts) / 8),
        (int(getattr(composition, "tonic", 0)) % 12) / 11,
        min(1.0, int(getattr(composition, "meter", 4)) / 12),
    ]
    return [
        *_hist(pitches, 12),
        *_hist([value + 6 for value in intervals], 12),
        *_hist(starts, 8),
        *_hist(durations, 4),
        *[round(value / voice_total, 6) for value in voice_hist],
        *[round(value, 6) for value in globals_],
    ]


def audio_plan_distance(first: list[float], second: list[float]) -> float:
    """Normalized L1 distance in [0, 1]; incompatible schemas are novel."""
    if not first or len(first) != len(second):
        return 1.0
    return round(float(np.mean(np.abs(np.asarray(first) - np.asarray(second)))), 6)


def nearest_audio_plan(vector: list[float], catalog: list[dict[str, Any]], limit: int = 96) -> tuple[float, str | None]:
    """Find the closest valid recent audio-intent vector."""
    nearest, content_id = 1.0, None
    for item in catalog[-limit:]:
        candidate = item.get("audio_intent_vector") if isinstance(item, dict) else None
        if not isinstance(candidate, list) or not all(isinstance(value, (int, float)) for value in candidate):
            continue
        distance = audio_plan_distance(vector, [float(value) for value in candidate])
        if distance < nearest:
            nearest, content_id = distance, str(item.get("content_id") or "") or None
    return nearest, content_id
