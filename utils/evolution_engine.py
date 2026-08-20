"""Deterministic multi-objective selection, lineage and semantic mutation."""

from __future__ import annotations

import copy
import os
from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np

EvolutionMode = Literal["off", "shadow", "canary", "active"]


@dataclass(frozen=True)
class Mutation:
    category: str
    field: str
    before: Any
    after: Any


@dataclass(frozen=True)
class EvolutionDecision:
    mode: EvolutionMode
    strategy: str
    applied: bool
    parent_content_id: str | None
    parent_genome_id: str | None
    generation: int
    exploration_rate: float
    mutation: Mutation | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def archive_of_elites(catalog: list[dict[str, Any]], per_cell: int = 3) -> list[dict[str, Any]]:
    """Keep the best confident and diverse creations in family/format cells."""
    cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in catalog:
        if not isinstance(item, dict):
            continue
        raw_fitness = item.get("fitness")
        fitness: dict[str, Any] = raw_fitness if isinstance(raw_fitness, dict) else {}
        confidence = float(fitness.get("confidence") or 0.0)
        if confidence < 0.2:
            continue
        raw_genome = item.get("genome")
        genome: dict[str, Any] = raw_genome if isinstance(raw_genome, dict) else {}
        scene = genome.get("scene", {})
        family = str(scene.get("architecture_id") or genome.get("family", "unknown"))
        kind = str(item.get("kind", "unknown"))
        raw_visual_dna = item.get("visual_dna")
        visual_dna: dict[str, Any] = raw_visual_dna if isinstance(raw_visual_dna, dict) else {}
        raw_novelty = visual_dna.get("novelty")
        novelty_block: dict[str, Any] = raw_novelty if isinstance(raw_novelty, dict) else {}
        novelty = novelty_block.get("recent_distance")
        score = float(fitness.get("score") or 0.0)
        item = {**item, "_elite_score": score * confidence + 0.15 * float(novelty or 0.0)}
        cells.setdefault((family, kind), []).append(item)
    result: list[dict[str, Any]] = []
    for values in cells.values():
        result.extend(sorted(values, key=lambda row: row["_elite_score"], reverse=True)[:per_cell])
    return result


def adaptive_exploration_rate(catalog: list[dict[str, Any]]) -> float:
    """Explore aggressively during cold start and when recent diversity collapses."""
    samples = len(catalog)
    if samples < 12:
        return 0.8
    recent = catalog[-24:]
    families = {str(item.get("genome", {}).get("family", "")) for item in recent if isinstance(item, dict)}
    family_ratio = len(families) / max(1, min(8, len(recent)))
    rate = 0.25 + (0.35 if family_ratio < 0.35 else 0.0)
    return round(min(0.8, max(0.2, rate)), 3)


def _select_parent(elites: list[dict[str, Any]], preset: str, rng: np.random.Generator, strategy: str):
    candidates = [item for item in elites if item.get("kind") == preset] or elites
    if not candidates:
        return None
    if strategy == "exploration":
        return max(
            candidates,
            key=lambda item: float(item.get("visual_dna", {}).get("novelty", {}).get("recent_distance") or 0.0),
        )
    scores = np.asarray([max(0.001, float(item.get("_elite_score", 0.001))) for item in candidates], dtype=float)
    probabilities = scores / scores.sum()
    return candidates[int(rng.choice(len(candidates), p=probabilities))]


def _mutate_profile(profile: dict[str, Any], rng: np.random.Generator) -> Mutation:
    options = ["geometry", "motion", "appearance", "audio", "scene", "scene"]
    category = str(rng.choice(options))
    before: Any
    after: Any
    if category == "geometry":
        field = str(rng.choice(["folds_theta", "folds_phi"]))
        before = int(profile.get(field, 3))
        after = int(np.clip(before + int(rng.choice([-1, 1])), 1, 12))
    elif category == "motion":
        field = "melt_rate"
        before = float(profile.get(field, 0.2))
        after = round(float(np.clip(before * rng.uniform(0.8, 1.2), 0.02, 2.5)), 6)
    elif category == "appearance":
        field = "palette.base_hue"
        palette = profile.setdefault("palette", {})
        before = float(palette.get("base_hue", 0.0))
        after = round((before + float(rng.uniform(-0.12, 0.12))) % 1.0, 6)
        palette["base_hue"] = after
        return Mutation(category, field, before, after)
    elif category == "audio":
        field = "music.swing"
        music = profile.setdefault("music", {})
        before = float(music.get("swing", 0.1))
        after = round(float(np.clip(before + rng.uniform(-0.04, 0.04), 0.0, 0.35)), 6)
        music["swing"] = after
        return Mutation(category, field, before, after)
    else:
        organisms = profile.get("scene", {}).get("organisms", [])
        if not organisms:
            field = "folds_theta"
            before = int(profile.get(field, 3))
            after = int(np.clip(before + int(rng.choice([-1, 1])), 1, 12))
            profile[field] = after
            return Mutation("geometry", field, before, after)
        organism = organisms[int(rng.integers(0, len(organisms)))]
        field = f"scene.{organism.get('id')}.topology_mix"
        before = float(organism.get("topology_mix", .5))
        after = round(float(np.clip(before + rng.uniform(-.2, .2), 0, 1)), 6)
        organism["topology_mix"] = after
        return Mutation(category, field, before, after)
    profile[field] = after
    return Mutation(category, field, before, after)


def _inherit(profile: dict[str, Any], genome: dict[str, Any]) -> None:
    geometry = genome.get("geometry", {})
    motion = genome.get("motion", {})
    appearance = genome.get("appearance", {})
    audio = genome.get("audio", {})
    for field in ("folds_theta", "folds_phi", "wire_density", "strand_count"):
        if geometry.get(field) is not None:
            profile[field] = geometry[field]
    for field in ("melt_rate", "rotation_rate", "camera_speed"):
        if motion.get(field) is not None:
            profile[field] = motion[field]
    if isinstance(appearance.get("palette"), dict):
        profile["palette"] = copy.deepcopy(appearance["palette"])
    if audio.get("genre"):
        profile["genre"] = audio["genre"]
    scene = genome.get("scene")
    if isinstance(scene, dict) and scene.get("organisms"):
        profile["scene"] = copy.deepcopy(scene)


def evolve_profile(
    profile: dict[str, Any],
    preset: str,
    catalog: list[dict[str, Any]],
    *,
    mode: EvolutionMode | None = None,
) -> EvolutionDecision:
    """Plan or apply one bounded mutation, preserving an auditable lineage."""
    configured = str(mode or os.environ.get("LIQUID_WIRE_EVOLUTION_MODE", "shadow")).lower()
    if configured not in {"off", "shadow", "canary", "active"}:
        configured = "shadow"
    actual_mode: EvolutionMode = configured  # type: ignore[assignment]
    rng = np.random.default_rng(int(profile["seed"]))
    exploration_rate = adaptive_exploration_rate(catalog)
    strategy = "exploration" if rng.random() < exploration_rate else "exploitation"
    parent = _select_parent(archive_of_elites(catalog), preset, rng, strategy)
    if actual_mode == "off" or parent is None:
        return EvolutionDecision(
            actual_mode,
            strategy,
            False,
            None,
            None,
            0,
            exploration_rate,
            None,
            "disabled" if actual_mode == "off" else "no confident parent; cold-start generation",
        )
    should_apply = actual_mode == "active" or (actual_mode == "canary" and int(profile["seed"]) % 10 == 0)
    candidate = copy.deepcopy(profile)
    _inherit(candidate, parent.get("genome", {}))
    mutation = _mutate_profile(candidate, rng)
    generation = int(parent.get("genome", {}).get("generation", 0)) + 1
    if should_apply:
        profile.clear()
        profile.update(candidate)
        profile["generation"] = generation
        profile["parents"] = [parent.get("content_id")]
        profile["mutations"] = [asdict(mutation)]
    return EvolutionDecision(
        actual_mode,
        strategy,
        should_apply,
        str(parent.get("content_id")),
        str(parent.get("genome_id")),
        generation,
        exploration_rate,
        mutation,
        "single semantic mutation from archive of elites" if should_apply else "shadow decision only",
    )
