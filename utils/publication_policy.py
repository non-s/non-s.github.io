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
    experiment: dict[str, Any] | None = None,
    semantic_novelty: dict[str, Any] | None = None,
    force_private: bool = False,
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
    temporal = visual_dna.get("temporal")
    dimensions["temporal"] = "pass" if isinstance(temporal, dict) and temporal else "unmeasured"
    fill = visual_dna.get("composition", {}).get("screen_fill")
    if isinstance(fill, (int, float)) and fill < 0.02:
        prompts.append("very low screen occupancy; review mobile legibility")
    novelty = visual_dna.get("novelty", {}).get("recent_distance")
    if isinstance(novelty, (int, float)) and novelty < 0.015:
        blocking.append("final render is a perceptual near-duplicate")
        dimensions["novelty"] = "fail"
    else:
        dimensions["novelty"] = "pass" if novelty is not None else "unmeasured"
    semantic_state = semantic_novelty or {}
    semantic_nearest = semantic_state.get("nearest", {})
    semantic_distance = semantic_nearest.get("distance") if isinstance(semantic_nearest, dict) else None
    semantic_minimum = semantic_state.get("minimum_distance")
    if (
        isinstance(semantic_distance, (int, float))
        and isinstance(semantic_minimum, (int, float))
        and semantic_nearest.get("content_id") is not None
        and semantic_distance < semantic_minimum
    ):
        blocking.append("creative intent is a semantic near-duplicate")
        dimensions["semantic_novelty"] = "fail"
    else:
        dimensions["semantic_novelty"] = "pass" if semantic_distance is not None else "unmeasured"
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
    elif puzzle_state.get("enabled") and not puzzle_state.get("render_validation", {}).get("passed"):
        blocking.append("enabled puzzle carrier did not survive final-render validation")
        dimensions["puzzle"] = "fail"
    else:
        dimensions["puzzle"] = "pass" if puzzle_state.get("enabled") else "not_applicable"
    experiment_state = experiment or {}
    changed = experiment_state.get("changed_variables")
    if changed is not None and (not isinstance(changed, dict) or len(changed) != 1):
        blocking.append("experiment must change exactly one declared variable")
        dimensions["experiment"] = "fail"
    else:
        dimensions["experiment"] = "pass" if changed is not None else "not_applicable"
    private_required = (
        force_private
        or os.environ.get("LIQUID_WIRE_FORCE_PRIVATE", "0") == "1"
        or os.environ.get("LIQUID_WIRE_PRIVATE_VALIDATION", "1") != "0"
    )
    return PublicationDecision(
        passed=not blocking,
        required_privacy="private" if private_required else "configured",
        blocking_issues=tuple(blocking),
        review_prompts=tuple(prompts),
        dimensions=dimensions,
    )
