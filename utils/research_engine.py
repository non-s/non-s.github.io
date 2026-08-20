"""Deterministic research records and explainable YouTube fitness.

Gemini may propose hypotheses elsewhere; this module owns validation and
decisions.  Missing metrics remain missing instead of being fabricated.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Literal

HypothesisStatus = Literal["insufficient_data", "inconclusive", "supported", "contradicted"]


@dataclass(frozen=True)
class FitnessResult:
    score: float
    confidence: float
    components: dict[str, float]
    weights: dict[str, float]
    missing: tuple[str, ...]
    model: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ratio(value: Any, scale: float = 1.0) -> float | None:
    try:
        number = float(value) / scale
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return min(1.0, max(0.0, number))


def compute_fitness(metrics: dict[str, Any], kind: str, *, novelty: float | None = None) -> FitnessResult:
    """Return a transparent multi-objective score for a comparable age window."""
    if kind == "short":
        model = "short_v1"
        candidates = {
            "retention": _ratio(metrics.get("average_percentage_viewed"), 100.0),
            "choice": _ratio(metrics.get("viewed_percentage"), 100.0),
            "engagement": _ratio(metrics.get("engagement_rate"), 0.10),
            "conversion": _ratio(metrics.get("subscriber_conversion"), 0.03),
            "novelty": _ratio(novelty),
        }
        weights = {"retention": 0.35, "choice": 0.25, "engagement": 0.15, "conversion": 0.10, "novelty": 0.15}
    else:
        model = "long_v1"
        candidates = {
            "consumption": _ratio(metrics.get("average_percentage_viewed"), 100.0),
            "watch_time": _ratio(
                metrics.get("average_view_duration_seconds"),
                max(1.0, float(metrics.get("duration_seconds", 1))),
            ),
            "choice": _ratio(metrics.get("impressions_ctr"), 0.15),
            "engagement": _ratio(metrics.get("engagement_rate"), 0.10),
            "conversion": _ratio(metrics.get("subscriber_conversion"), 0.03),
            "novelty": _ratio(novelty),
        }
        weights = {
            "consumption": 0.25,
            "watch_time": 0.25,
            "choice": 0.20,
            "engagement": 0.10,
            "conversion": 0.10,
            "novelty": 0.10,
        }
    available = {name: value for name, value in candidates.items() if value is not None}
    missing = tuple(name for name, value in candidates.items() if value is None)
    weight_total = sum(weights[name] for name in available)
    weighted_sum = sum(float(value) * weights[name] for name, value in available.items())
    score = weighted_sum / weight_total if weight_total else 0.0
    views = max(0, int(metrics.get("views") or 0))
    sample_confidence = 1.0 - math.exp(-views / 500.0)
    completeness = weight_total / sum(weights.values())
    confidence = sample_confidence * completeness
    return FitnessResult(
        score=round(score, 6),
        confidence=round(confidence, 6),
        components={name: round(float(value), 6) for name, value in available.items()},
        weights=weights,
        missing=missing,
        model=model,
    )


def hypothesis_status(effect: float | None, samples: int, confidence: float) -> HypothesisStatus:
    """Conservative evidence state; it deliberately does not claim causality."""
    if effect is None or samples < 5:
        return "insufficient_data"
    if confidence < 0.6 or abs(effect) < 0.03:
        return "inconclusive"
    return "supported" if effect > 0 else "contradicted"
