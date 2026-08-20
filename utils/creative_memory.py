"""Bounded, machine-readable catalog memory for generated work."""

from __future__ import annotations

from typing import Any

from utils.atomic_state import load_versioned, save_versioned
from utils.paths import data_dir
from utils.state_lock import state_lock

CATALOG_SCHEMA_VERSION = 1
CATALOG_LIMIT = 1000


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
                "quality": metadata.get("quality_report"),
                "performance_windows": {},
                "fitness": None,
                "experiment_id": metadata.get("experiment_id"),
                "hypothesis_id": metadata.get("hypothesis_id"),
            }
        )
        save_versioned(path, catalog[-CATALOG_LIMIT:], CATALOG_SCHEMA_VERSION)
