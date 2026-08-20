"""Cheap, bounded candidate generation before expensive rendering."""

from __future__ import annotations

import copy
import os
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class CandidateScore:
    index: int
    mutation: dict[str, Any]
    intent_novelty: float
    family_saturation: float
    score: float


def candidate_budget(preset: str) -> int:
    default = 4 if preset == "short" else 2
    try:
        configured = int(os.environ.get("LIQUID_WIRE_CHEAP_CANDIDATES", default))
    except ValueError:
        configured = default
    return min(8, max(1, configured))


def _intent_vector(profile: dict[str, Any]) -> np.ndarray:
    raw_palette = profile.get("palette")
    palette: dict[str, Any] = raw_palette if isinstance(raw_palette, dict) else {}
    return np.asarray(
        [
            float(profile.get("folds_theta", 0)) / 12.0,
            float(profile.get("folds_phi", 0)) / 12.0,
            min(1.0, float(profile.get("melt_rate", 0)) / 2.5),
            float(palette.get("base_hue", 0)) % 1.0,
        ],
        dtype=float,
    )


def _catalog_vectors(catalog: list[dict[str, Any]]) -> list[np.ndarray]:
    vectors: list[np.ndarray] = []
    for item in catalog[-96:]:
        genome = item.get("genome") if isinstance(item, dict) else None
        if not isinstance(genome, dict):
            continue
        geometry = genome.get("geometry", {})
        motion = genome.get("motion", {})
        appearance = genome.get("appearance", {})
        vectors.append(
            _intent_vector(
                {
                    **geometry,
                    **motion,
                    "palette": appearance.get("palette", {}),
                }
            )
        )
    return vectors


def _variant(base: dict[str, Any], index: int, rng: np.random.Generator) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = copy.deepcopy(base)
    if index == 0:
        return candidate, {"field": None, "before": None, "after": None}
    choice = (index - 1) % 3
    if choice == 0:
        field = "palette.base_hue"
        palette = candidate.setdefault("palette", {})
        before = float(palette.get("base_hue", 0.0))
        after = round((before + float(rng.uniform(0.08, 0.22))) % 1.0, 6)
        palette["base_hue"] = after
    elif choice == 1:
        field = "folds_theta"
        before = int(candidate.get(field, 3))
        after = int(np.clip(before + int(rng.choice([-1, 1])), 1, 12))
        candidate[field] = after
    else:
        field = "melt_rate"
        before = float(candidate.get(field, 0.2))
        after = round(float(np.clip(before * rng.uniform(0.75, 1.25), 0.02, 2.5)), 6)
        candidate[field] = after
    return candidate, {"field": field, "before": before, "after": after}


def select_candidate(
    profile: dict[str, Any], preset: str, catalog: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Select one single-variable intent; the final render gate remains authoritative."""
    budget = candidate_budget(preset)
    rng = np.random.default_rng(int(profile["seed"]) ^ 0xC0FFEE)
    old_vectors = _catalog_vectors(catalog)
    recent_families = [item.get("genome", {}).get("family") for item in catalog[-24:] if isinstance(item, dict)]
    family = profile.get("family")
    saturation = recent_families.count(family) / max(1, len(recent_families))
    scored: list[tuple[dict[str, Any], CandidateScore]] = []
    for index in range(budget):
        candidate, mutation = _variant(profile, index, rng)
        vector = _intent_vector(candidate)
        novelty = min((float(np.linalg.norm(vector - old)) / 2.0 for old in old_vectors), default=1.0)
        score = 0.75 * novelty + 0.25 * (1.0 - saturation)
        scored.append((candidate, CandidateScore(index, mutation, novelty, saturation, score)))
    selected, selected_score = max(scored, key=lambda pair: pair[1].score)
    report = {
        "stage": "cheap_genome",
        "budget": budget,
        "selected_index": selected_score.index,
        "selected": asdict(selected_score),
        "candidates": [asdict(score) for _, score in scored],
        "limitations": "Intent novelty is a cheap prefilter; final visual DNA and quality gate govern publication.",
    }
    return selected, report
