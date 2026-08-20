"""Require replicated Short evidence before scheduled long-form production."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from utils.atomic_state import load_versioned


def eligible_long_form_families(data_root: Path) -> dict[str, dict[str, float | int]]:
    path = data_root / "catalog_memory.json"
    if not path.exists():
        return {}
    catalog = load_versioned(path, 1, {}, [])
    grouped: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for item in catalog if isinstance(catalog, list) else []:
        if not isinstance(item, dict) or item.get("kind") != "short":
            continue
        raw_fitness = item.get("fitness")
        fitness = raw_fitness if isinstance(raw_fitness, dict) else {}
        score = float(fitness.get("score") or 0.0)
        confidence = float(fitness.get("confidence") or 0.0)
        raw_windows = item.get("performance_windows")
        windows = raw_windows if isinstance(raw_windows, dict) else {}
        if not ({"72h", "mature"} & set(windows)):
            continue
        raw_genome = item.get("genome")
        genome = raw_genome if isinstance(raw_genome, dict) else {}
        family = str(genome.get("family", "unknown"))
        if score >= 0.6 and confidence >= 0.4:
            grouped[family].append((score, confidence))
    return {
        family: {
            "replications": len(values),
            "mean_fitness": round(sum(score for score, _ in values) / len(values), 6),
            "mean_confidence": round(sum(confidence for _, confidence in values) / len(values), 6),
        }
        for family, values in grouped.items()
        if len(values) >= 2
    }


def long_form_eligible(data_root: Path) -> bool:
    return bool(eligible_long_form_families(data_root))
