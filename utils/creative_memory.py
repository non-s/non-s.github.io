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


def creation_record(metadata: dict[str, Any]) -> dict[str, Any]:
    """Project full render metadata into the durable learning schema."""
    return {
        "content_id": metadata["content_id"],
        "generated_at": metadata.get("generated_at"),
        "kind": metadata.get("kind"),
        "genome_id": metadata.get("genome_id"),
        "genome": metadata.get("genome"),
        "visual_dna_id": metadata.get("visual_dna_id"),
        "visual_dna": metadata.get("visual_dna"),
        "audio_dna_id": metadata.get("audio_dna_id"),
        "audio_dna": metadata.get("audio_dna"),
        "audio_composition_id": metadata.get("audio_composition_id"),
        "audio_intent_vector": metadata.get("audio_intent_vector"),
        "audio_novelty": metadata.get("audio_novelty"),
        "semantic_signature": metadata.get("semantic_signature"),
        "semantic_novelty": metadata.get("semantic_novelty"),
        "quality": metadata.get("quality_report"),
        "puzzle": metadata.get("genome", {}).get("puzzle", {}),
        "performance_windows": {},
        "fitness": None,
        "experiment_id": metadata.get("experiment_id"),
        "hypothesis_id": metadata.get("hypothesis_id"),
        "experiment_variant": metadata.get("experiment_variant"),
        "experiment": metadata.get("experiment"),
        "candidate_selection": metadata.get("generator_profile", {}).get("candidate_selection", {}),
        "publication_readiness": metadata.get("publication_readiness"),
        "strategy_version": metadata.get("strategy_version"),
    }


def record_creation(metadata: dict[str, Any]) -> None:
    """Persist only durable learning fields, not bulky editorial metadata."""
    path = _path()
    with state_lock(path):
        catalog = load_catalog()
        catalog.append(creation_record(metadata))
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
        raw_signature = record.get("semantic_signature")
        signature: dict[str, Any] = raw_signature if isinstance(raw_signature, dict) else {}
        vector = signature.get("vector")
        if isinstance(vector, list) and all(isinstance(value, (int, float)) for value in vector):
            old_count = int(cell.get("semantic_samples", 0))
            old = cell.get("semantic_centroid", [0.0] * len(vector))
            if not isinstance(old, list) or len(old) != len(vector):
                old, old_count = [0.0] * len(vector), 0
            cell["semantic_centroid"] = [
                round((float(previous) * old_count + float(value)) / (old_count + 1), 6)
                for previous, value in zip(old, vector, strict=True)
            ]
            cell["semantic_samples"] = old_count + 1
            concepts = signature.get("concepts", [])
            counts = cell.get("semantic_concepts", {})
            if not isinstance(counts, dict):
                counts = {}
            for concept in concepts if isinstance(concepts, list) else []:
                key_concept = str(concept)[:160]
                counts[key_concept] = int(counts.get(key_concept, 0)) + 1
            cell["semantic_concepts"] = dict(
                sorted(counts.items(), key=lambda item: (-int(item[1]), item[0]))[:64]
            )
    save_versioned(path, archive, ARCHIVE_SCHEMA_VERSION)
