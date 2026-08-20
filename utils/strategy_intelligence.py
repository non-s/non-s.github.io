"""Explainable long-horizon strategy primitives for the autonomous loop."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

STRATEGY_VERSION = 1
MIN_CREATIVE_MAP_SAMPLES = 8


def _number(item: dict[str, Any], path: str) -> float | None:
    value: Any = item
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def pareto_frontier(catalog: list[dict[str, Any]]) -> list[str]:
    """Return non-dominated content IDs across fitness, novelty and confidence."""
    points: list[tuple[str, tuple[float, float, float]]] = []
    for item in catalog:
        content_id = item.get("content_id") if isinstance(item, dict) else None
        values = (
            _number(item, "fitness.score"),
            _number(item, "visual_dna.novelty.recent_distance"),
            _number(item, "fitness.confidence"),
        )
        if content_id and all(value is not None for value in values):
            points.append((str(content_id), tuple(float(value) for value in values)))  # type: ignore[arg-type]
    frontier: list[str] = []
    for content_id, point in points:
        dominated = any(
            all(other_value >= value for other_value, value in zip(other, point, strict=True))
            and any(other_value > value for other_value, value in zip(other, point, strict=True))
            for other_id, other in points
            if other_id != content_id
        )
        if not dominated:
            frontier.append(content_id)
    return sorted(frontier)


def creative_map(catalog: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a small interpretable map only when enough final-render DNA exists."""
    rows: list[tuple[float, float, float]] = []
    for item in catalog:
        values = (
            _number(item, "visual_dna.composition.screen_fill"),
            _number(item, "visual_dna.motion.optical_flow_mean"),
            _number(item, "visual_dna.composition.entropy"),
        )
        if all(value is not None for value in values):
            rows.append(tuple(float(value) for value in values))  # type: ignore[arg-type]
    if len(rows) < MIN_CREATIVE_MAP_SAMPLES:
        return {"status": "insufficient_data", "samples": len(rows), "cells": {}, "empty_cells": []}
    matrix = np.asarray(rows, dtype=float)
    medians = np.median(matrix, axis=0)
    counts: dict[str, int] = defaultdict(int)
    labels = (
        ("sparse", "dense"),
        ("calm", "chaotic"),
        ("simple", "complex"),
    )
    all_cells: set[str] = set()
    for a in labels[0]:
        for b in labels[1]:
            for c in labels[2]:
                all_cells.add(f"{a}/{b}/{c}")
    for row in matrix:
        cell = "/".join(labels[index][int(value >= medians[index])] for index, value in enumerate(row))
        counts[cell] += 1
    return {
        "status": "ready",
        "samples": len(rows),
        "axes": ["density", "motion", "complexity"],
        "medians": [round(float(value), 6) for value in medians],
        "cells": dict(sorted(counts.items())),
        "empty_cells": sorted(all_cells - set(counts)),
    }


def value_of_information(*, uncertainty: float, novelty: float, expected_performance: float) -> float:
    """Bounded exploration value; it can inform, never bypass publication gates."""
    values = [float(np.clip(value, 0.0, 1.0)) for value in (uncertainty, novelty, expected_performance)]
    return round(0.45 * values[0] + 0.40 * values[1] + 0.15 * values[2], 6)


def lineage_graph(catalog: list[dict[str, Any]]) -> dict[str, Any]:
    """Represent genealogy without adding a graph dependency."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    known = {str(item.get("content_id")) for item in catalog if isinstance(item, dict) and item.get("content_id")}
    for item in catalog:
        if not isinstance(item, dict) or not item.get("content_id"):
            continue
        content_id = str(item["content_id"])
        raw_genome = item.get("genome")
        genome: dict[str, Any] = raw_genome if isinstance(raw_genome, dict) else {}
        nodes.append(
            {
                "content_id": content_id,
                "generation": int(genome.get("generation", 0)),
                "family": str(genome.get("family", "unknown")),
            }
        )
        for parent in genome.get("parents", []):
            parent_id = str(parent)
            edges.append({"from": parent_id, "to": content_id, "resolved": str(parent_id in known).lower()})
    return {"strategy_version": STRATEGY_VERSION, "nodes": nodes, "edges": edges}
