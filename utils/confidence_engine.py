"""Evidence gates for Wild Brief learning systems.

The goal is to keep recommendations useful while the channel is still
collecting data. Strong strategy changes require enough samples and enough
observed metrics; small or estimated signals stay in observation mode.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

MINIMUM_SAMPLE_RULES = {
    "category": 5,
    "format": 5,
    "series": 3,
    "video": 1,
    "pattern": 5,
    "distribution": 8,
}

QUALITY_WEIGHTS = {
    "observed": 1.0,
    "inferred": 0.65,
    "estimated": 0.35,
    "missing": 0.0,
}


@dataclass(frozen=True)
class Confidence:
    confidence_score: float
    sample_size: int
    minimum_sample_size: int
    data_quality: str
    data_quality_score: float
    recommendation_strength: str
    can_adjust_strategy: bool
    bootstrap_multiplier: float
    reasoning: str

    def to_dict(self) -> dict:
        return asdict(self)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def data_quality_from_counts(*, observed: int = 0, inferred: int = 0, estimated: int = 0, missing: int = 0) -> dict:
    counts = {
        "observed": int(observed or 0),
        "inferred": int(inferred or 0),
        "estimated": int(estimated or 0),
        "missing": int(missing or 0),
    }
    total = sum(counts.values())
    if total <= 0:
        return {"data_quality": "missing", "data_quality_score": 0.0, "counts": counts}
    score = sum(counts[key] * QUALITY_WEIGHTS[key] for key in counts) / total
    dominant = max(counts.items(), key=lambda item: (item[1], QUALITY_WEIGHTS[item[0]]))[0]
    if counts["observed"] and counts["observed"] >= counts["estimated"] + counts["inferred"]:
        dominant = "observed"
    return {
        "data_quality": dominant,
        "data_quality_score": round(_clamp(score), 3),
        "counts": counts,
    }


def assess_confidence(
    axis: str,
    sample_size: int,
    *,
    observed: int = 0,
    inferred: int = 0,
    estimated: int = 0,
    missing: int = 0,
    minimum_sample_size: int | None = None,
) -> dict:
    minimum = int(minimum_sample_size or MINIMUM_SAMPLE_RULES.get(axis, 5))
    sample_size = int(sample_size or 0)
    quality = data_quality_from_counts(
        observed=observed,
        inferred=inferred,
        estimated=estimated,
        missing=missing,
    )
    sample_factor = _clamp(sample_size / max(minimum, 1))
    confidence = _clamp(sample_factor * quality["data_quality_score"])
    can_adjust = sample_size >= minimum and confidence >= 0.55 and quality["data_quality"] != "missing"
    if can_adjust and confidence >= 0.82:
        strength = "act"
    elif can_adjust:
        strength = "test"
    else:
        strength = "observe"
    multiplier = 0.25 + confidence * 0.75
    if quality["data_quality"] == "estimated":
        multiplier = min(multiplier, 0.45)
    if sample_size < minimum:
        multiplier = min(multiplier, 0.55)
    if quality["data_quality"] == "missing":
        multiplier = 0.0
    reason = (
        f"{axis} has {sample_size}/{minimum} samples, "
        f"{quality['data_quality']} data, confidence {confidence:.2f}; "
        f"{'strategy changes allowed' if can_adjust else 'observation only'}."
    )
    return Confidence(
        confidence_score=round(confidence, 3),
        sample_size=sample_size,
        minimum_sample_size=minimum,
        data_quality=quality["data_quality"],
        data_quality_score=quality["data_quality_score"],
        recommendation_strength=strength,
        can_adjust_strategy=can_adjust,
        bootstrap_multiplier=round(_clamp(multiplier), 3),
        reasoning=reason,
    ).to_dict()


def blend_weight(raw_weight: float, confidence: dict, neutral: float = 1.0) -> float:
    """Pull any strategy weight back toward neutral while confidence is low."""
    multiplier = float((confidence or {}).get("bootstrap_multiplier") or 0.0)
    if not (confidence or {}).get("can_adjust_strategy"):
        return neutral
    return round(neutral + (float(raw_weight) - neutral) * multiplier, 3)


def combined_confidence(signals: list[dict]) -> dict:
    usable = [s for s in signals if isinstance(s, dict)]
    if not usable:
        return assess_confidence("decision", 0, missing=1, minimum_sample_size=1)
    score = sum(float(s.get("confidence_score") or 0) for s in usable) / len(usable)
    sample_size = sum(int(s.get("sample_size") or 0) for s in usable)
    observed = sum(1 for s in usable if s.get("data_quality") == "observed")
    inferred = sum(1 for s in usable if s.get("data_quality") == "inferred")
    estimated = sum(1 for s in usable if s.get("data_quality") == "estimated")
    missing = sum(1 for s in usable if s.get("data_quality") == "missing")
    quality = data_quality_from_counts(observed=observed, inferred=inferred, estimated=estimated, missing=missing)
    return {
        "confidence_score": round(_clamp(score), 3),
        "sample_size": sample_size,
        "minimum_sample_size": sum(int(s.get("minimum_sample_size") or 0) for s in usable),
        "data_quality": quality["data_quality"],
        "data_quality_score": quality["data_quality_score"],
        "recommendation_strength": "act" if score >= 0.82 else ("test" if score >= 0.55 else "observe"),
        "can_adjust_strategy": score >= 0.55,
        "bootstrap_multiplier": round(0.25 + _clamp(score) * 0.75, 3),
        "reasoning": f"Combined {len(usable)} evidence source(s) with average confidence {score:.2f}.",
    }
