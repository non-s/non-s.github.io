"""Explainable Quality Gate 2.0 and private-validation publication policy."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PublicationDecision:
    passed: bool
    required_privacy: str
    blocking_issues: tuple[str, ...]
    review_prompts: tuple[str, ...]
    dimensions: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_publication(
    quality: dict[str, Any],
    visual_dna: dict[str, Any],
    audio_dna: dict[str, Any],
    *,
    puzzle: dict[str, Any] | None = None,
) -> PublicationDecision:
    """Block objective failures; subjective characteristics become prompts."""
    blocking: list[str] = []
    prompts: list[str] = []
    dimensions: dict[str, str] = {}
    if not quality.get("passed"):
        blocking.append("existing technical/perceptual quality gate failed")
        dimensions["technical"] = "fail"
    else:
        dimensions["technical"] = "pass"
    samples = int(visual_dna.get("sample_count") or 0)
    if samples < 3:
        blocking.append("visual DNA has fewer than three decoded samples")
        dimensions["visual"] = "fail"
    else:
        dimensions["visual"] = "pass"
    fill = visual_dna.get("composition", {}).get("screen_fill")
    if isinstance(fill, (int, float)) and fill < 0.02:
        prompts.append("very low screen occupancy; review mobile legibility")
    novelty = visual_dna.get("novelty", {}).get("recent_distance")
    if isinstance(novelty, (int, float)) and novelty < 0.015:
        blocking.append("final render is a perceptual near-duplicate")
        dimensions["novelty"] = "fail"
    else:
        dimensions["novelty"] = "pass" if novelty is not None else "unmeasured"
    rms = audio_dna.get("loudness", {}).get("rms_db")
    peak = audio_dna.get("loudness", {}).get("peak")
    if isinstance(rms, (int, float)) and rms <= -60:
        blocking.append("final audio is effectively silent")
    if isinstance(peak, (int, float)) and peak > 1.001:
        blocking.append("final audio exceeds digital full scale")
    dimensions["audio"] = "fail" if any("audio" in issue for issue in blocking) else "pass"
    puzzle_state = puzzle or {"enabled": False}
    if puzzle_state.get("enabled") and not puzzle_state.get("validated"):
        blocking.append("enabled puzzle has not passed validation")
        dimensions["puzzle"] = "fail"
    else:
        dimensions["puzzle"] = "pass" if puzzle_state.get("enabled") else "not_applicable"
    force_private = os.environ.get("LIQUID_WIRE_PRIVATE_VALIDATION", "1") != "0"
    return PublicationDecision(
        passed=not blocking,
        required_privacy="private" if force_private else "configured",
        blocking_issues=tuple(blocking),
        review_prompts=tuple(prompts),
        dimensions=dimensions,
    )
