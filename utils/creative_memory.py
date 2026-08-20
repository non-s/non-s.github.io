"""Bounded, machine-readable catalog memory for generated work."""

from __future__ import annotations

from typing import Any

from utils.atomic_state import load_versioned, save_versioned
from utils.canon_memory import record_canon_event
from utils.paths import data_dir
from utils.state_lock import state_lock

CATALOG_SCHEMA_VERSION = 1
CATALOG_LIMIT = 1000
ARCHIVE_SCHEMA_VERSION = 1


def _path():
    return data_dir() / "catalog_memory.json"


def load_catalog() -> list[dict[str, Any]]:
    value = load_versioned(_path(), CATALOG_SCHEMA_VERSION, {}, [])
    if not isinstance(value, list):
        raise ValueError("catalog memory data must be a list")
    return [item for item in value if isinstance(item, dict)]


def record_creation(metadata: dict[str, Any]) -> None:
    """Persist only durable learning fields, not bulky editorial metadata."""
    path = _path()
    with state_lock(path):
        catalog = load_catalog()
        catalog.append(
            {
                "content_id": metadata["content_id"],
                "generated_at": metadata.get("generated_at"),
                "kind": metadata.get("kind"),
                "genome_id": metadata.get("genome_id"),
                "genome": metadata.get("genome"),
                "visual_dna_id": metadata.get("visual_dna_id"),
                "visual_dna": metadata.get("visual_dna"),
                "audio_dna_id": metadata.get("audio_dna_id"),
                "audio_dna": metadata.get("audio_dna"),
                "quality": metadata.get("quality_report"),
                "puzzle": metadata.get("genome", {}).get("puzzle", {}),
                "performance_windows": {},
                "fitness": None,
                "experiment_id": metadata.get("experiment_id"),
                "hypothesis_id": metadata.get("hypothesis_id"),
            }
        )
        dropped = catalog[:-CATALOG_LIMIT]
        if dropped:
            _aggregate_archive(path.parent / "catalog_archive.json", dropped)
        save_versioned(path, catalog[-CATALOG_LIMIT:], CATALOG_SCHEMA_VERSION)
    record_canon_event(path.parent / "canon_state.json", metadata)


def _aggregate_archive(path, records: list[dict[str, Any]]) -> None:
    """Compact evicted raw records into durable family/format/generation counts."""
    archive = load_versioned(path, ARCHIVE_SCHEMA_VERSION, {}, {"cells": {}})
    if not isinstance(archive, dict) or not isinstance(archive.get("cells"), dict):
        archive = {"cells": {}}
    cells = archive["cells"]
    for record in records:
        raw_genome = record.get("genome")
        genome: dict[str, Any] = raw_genome if isinstance(raw_genome, dict) else {}
        family = str(genome.get("family", "unknown"))
        kind = str(record.get("kind", "unknown"))
        generation = max(0, int(genome.get("generation", 0)))
        key = f"{family}|{kind}"
        cell = cells.setdefault(key, {"count": 0, "max_generation": 0, "fitness_sum": 0.0, "fitness_samples": 0})
        cell["count"] += 1
        cell["max_generation"] = max(int(cell["max_generation"]), generation)
        raw_fitness = record.get("fitness")
        fitness: dict[str, Any] = raw_fitness if isinstance(raw_fitness, dict) else {}
        score = fitness.get("score")
        if isinstance(score, (int, float)):
            cell["fitness_sum"] += float(score)
            cell["fitness_samples"] += 1
    save_versioned(path, archive, ARCHIVE_SCHEMA_VERSION)
