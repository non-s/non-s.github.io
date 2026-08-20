"""Interpretable, cross-format semantic memory for creative intent.

The vector is local and deterministic: it describes meaning and structure rather
than pixels, filenames or duration.  This lets shorts, long videos and live
sessions recognize when they are retelling the same creative idea.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from utils.atomic_state import load_versioned

SEMANTIC_MEMORY_VERSION = 1
SEMANTIC_VECTOR_SIZE = 48
SEMANTIC_MIN_DISTANCE = 0.045


def _items(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, (list, tuple)) else []


def _number(value: Any, default: float = 0.0) -> float:
    return float(value) if isinstance(value, (int, float)) else default


def _token_vector(tokens: list[str]) -> list[float]:
    values = np.zeros(32, dtype=np.float64)
    for token in sorted(set(tokens)):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        values[int.from_bytes(digest[:2], "big") % values.size] += 1.0
    norm = float(np.linalg.norm(values))
    return (values / norm if norm else values).round(6).tolist()


def build_semantic_signature(profile: dict[str, Any], kind: str) -> dict[str, Any]:
    """Describe a work's concepts, narrative grammar and audiovisual intent."""
    raw_scene = profile.get("scene")
    scene: dict[str, Any] = raw_scene if isinstance(raw_scene, dict) else {}
    organisms = _items(scene.get("organisms"))
    relations = _items(scene.get("relations"))
    raw_matter = scene.get("matter")
    matter: dict[str, Any] = raw_matter if isinstance(raw_matter, dict) else {}
    events = _items(profile.get("timeline"))
    raw_composition = profile.get("composition")
    composition: dict[str, Any] = raw_composition if isinstance(raw_composition, dict) else {}
    notes = _items(composition.get("notes"))
    raw_scene_music = profile.get("scene_music")
    scene_music: dict[str, Any] = raw_scene_music if isinstance(raw_scene_music, dict) else {}
    agents = _items(scene_music.get("agents"))

    families = [str(item.get("family", "unknown")) for item in organisms]
    roles = [str(item.get("role", "unknown")) for item in organisms]
    relation_kinds = [str(item.get("kind", "unknown")) for item in relations]
    event_kinds = [str(item.get("kind", "unknown")) for item in events]
    transformations = [str(item.get("transform", "unknown")) for item in agents]
    genre = str(profile.get("genre", "lofi_ambient"))
    mode = str(composition.get("mode", "unknown"))
    progression = composition.get("progression", [])
    concepts = sorted(set([
        f"family:{value}" for value in families
    ] + [
        f"role:{value}" for value in roles
    ] + [
        f"relation:{value}" for value in relation_kinds
    ] + [
        f"event:{value}" for value in event_kinds
    ] + [
        f"agent:{value}" for value in transformations
    ] + [
        f"genre:{genre}", f"mode:{mode}",
        f"family-ensemble:{'+'.join(sorted(families))}",
        f"narrative:{'>'.join(event_kinds)}",
        f"relations:{'>'.join(relation_kinds)}",
        f"progression:{','.join(str(value) for value in progression)}",
    ]))

    orbit = [_number(item.get("orbit_rate")) for item in organisms]
    pulse = [_number(item.get("pulse_rate")) for item in organisms]
    scale = [_number(item.get("scale")) for item in organisms]
    hue = [_number(item.get("hue_offset")) % 1.0 for item in organisms]
    inferred_duration = max(
        (_number(event.get("start")) + _number(event.get("duration")) for event in events),
        default=1.0,
    )
    duration = max(.001, _number(profile.get("duration"), inferred_duration))
    voices = {str(note.get("voice", "unknown")).split(":", 1)[0] for note in notes}
    continuous = [
        min(1.0, len(organisms) / 7), min(1.0, len(relations) / 6),
        min(1.0, len(set(families)) / 7), min(1.0, len(set(relation_kinds)) / 7),
        min(1.0, float(np.mean(np.abs(orbit))) * 4) if orbit else 0.0,
        min(1.0, float(np.std(orbit)) * 4) if orbit else 0.0,
        min(1.0, float(np.mean(pulse)) / 1.25) if pulse else 0.0,
        float(np.mean(scale)) if scale else 0.0,
        float(np.std(scale)) if scale else 0.0,
        float(np.mean(hue)) if hue else 0.0,
        min(1.0, _number(matter.get("cohesion"))),
        min(1.0, _number(matter.get("viscosity"))),
        min(1.0, _number(matter.get("elasticity"))),
        min(1.0, len(events) / 12), min(1.0, len(voices) / 8),
        min(1.0, len(notes) / max(1.0, duration * 12)),
    ]
    vector = [*_token_vector(concepts), *[round(float(np.clip(value, 0, 1)), 6) for value in continuous]]
    body = {
        "version": SEMANTIC_MEMORY_VERSION,
        "kind": kind,
        "concepts": concepts,
        "narrative_grammar": event_kinds,
        "ensemble": {"families": families, "roles": roles, "relations": relation_kinds},
        "musical_theme": {"genre": genre, "mode": mode, "agent_transformations": transformations},
        "vector": vector,
    }
    body["signature_id"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:24]
    return body


def semantic_distance(first: dict[str, Any], second: dict[str, Any]) -> float:
    """Mixed symbolic/continuous semantic distance normalized to [0, 1]."""
    a, b = set(first.get("concepts", [])), set(second.get("concepts", []))
    symbolic = 1.0 - len(a & b) / max(1, len(a | b))
    av, bv = first.get("vector"), second.get("vector")
    if not isinstance(av, list) or not isinstance(bv, list) or len(av) != len(bv):
        numeric = 1.0
    else:
        numeric = min(1.0, float(np.mean(np.abs(np.asarray(av, dtype=float) - np.asarray(bv, dtype=float))) * 4))
    return round(.72 * symbolic + .28 * numeric, 6)


def load_archive_signatures(data_root: Path) -> list[dict[str, Any]]:
    """Restore bounded semantic prototypes retained beyond the raw catalog."""
    path = data_root / "catalog_archive.json"
    if not path.exists():
        return []
    archive = load_versioned(path, 1, {}, {"cells": {}})
    cells = archive.get("cells", {}) if isinstance(archive, dict) else {}
    result = []
    for key, cell in cells.items() if isinstance(cells, dict) else []:
        if not isinstance(cell, dict) or not isinstance(cell.get("semantic_centroid"), list):
            continue
        concepts = cell.get("semantic_concepts", {})
        result.append({
            "content_id": f"archive:{key}",
            "kind": str(key).rsplit("|", 1)[-1],
            "semantic_signature": {
                "vector": cell["semantic_centroid"],
                "concepts": list(concepts) if isinstance(concepts, dict) else [],
            },
        })
    return result


def nearest_semantic_signature(
    signature: dict[str, Any],
    catalog: list[dict[str, Any]],
    archive: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return overall and cross-format nearest neighbors from durable memory."""
    nearest: dict[str, Any] = {"distance": 1.0, "content_id": None, "kind": None}
    cross: dict[str, Any] = {"distance": 1.0, "content_id": None, "kind": None}
    for item in [*catalog[-1000:], *(archive or [])]:
        candidate = item.get("semantic_signature") if isinstance(item, dict) else None
        if not isinstance(candidate, dict):
            continue
        distance = semantic_distance(signature, candidate)
        current = {"distance": distance, "content_id": item.get("content_id"), "kind": item.get("kind")}
        if distance < nearest["distance"]:
            nearest = current
        if item.get("kind") != signature.get("kind") and distance < cross["distance"]:
            cross = current
    return {"nearest": nearest, "cross_format_nearest": cross}
