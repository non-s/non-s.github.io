"""Deterministic scene genomes for Liquid Wire's multi-organism engine.

Families are only the alphabet.  A scene is an unbounded composition made from
continuous transforms, motion, topology morphs and relationships.  The schema
is JSON-native so it can be persisted, compared and safely proposed by Gemini.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from typing import Any

import numpy as np

SCENE_VERSION = 1
RELATIONS = ("orbit", "resonance", "braid", "mirror", "attraction", "emergence", "fusion")
ROLES = ("anchor", "satellite", "counterpoint", "echo", "catalyst", "wanderer")


@dataclass(frozen=True)
class Organism:
    id: str
    family: str
    morph_family: str
    role: str
    seed: int
    x: float
    y: float
    scale: float
    depth: float
    phase: float
    orbit_rate: float
    pulse_rate: float
    hue_offset: float
    topology_mix: float


@dataclass(frozen=True)
class Relation:
    source: str
    target: str
    kind: str
    strength: float
    phase: float


def _hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def identify_scene(scene: dict[str, Any]) -> dict[str, Any]:
    """Refresh identities after a bounded evolutionary or candidate mutation."""
    result = {key: value for key, value in scene.items() if key not in {"scene_id", "architecture_id"}}
    organisms = result.get("organisms", [])
    relations = result.get("relations", [])
    result["scene_id"] = _hash(result)[:24]
    result["architecture_id"] = _hash({
        "families": sorted(x.get("family") for x in organisms),
        "roles": sorted(x.get("role") for x in organisms),
        "relations": sorted(x.get("kind") for x in relations),
        "count": len(organisms),
    })[:24]
    return result


def build_scene(seed: int, preset: str, families: Sequence[str], primary: str) -> dict[str, Any]:
    """Create a bounded render scene from a practically unbounded parameter space."""
    rng = np.random.default_rng(seed ^ 0x4C4956494E47)
    limits = {"short": (2, 4), "long": (3, 7), "live": (3, 6), "live-test": (3, 5)}
    low, high = limits.get(preset, (2, 5))
    count = int(rng.integers(low, high + 1))
    pool = list(dict.fromkeys(str(x) for x in families))
    chosen = [primary]
    while len(chosen) < count:
        chosen.append(str(rng.choice(pool)))

    organisms: list[Organism] = []
    golden = np.pi * (3.0 - np.sqrt(5.0))
    for index, family in enumerate(chosen):
        angle = float((index * golden + rng.uniform(-0.45, 0.45)) % (2 * np.pi))
        radius = 0.0 if index == 0 else float(rng.uniform(0.13, 0.31))
        organisms.append(Organism(
            id=f"o{index}", family=family, morph_family=str(rng.choice(pool)),
            role="anchor" if index == 0 else str(rng.choice(ROLES[1:])),
            seed=int(rng.integers(1, 2**63 - 1)),
            x=round(radius * float(np.cos(angle)), 6), y=round(radius * float(np.sin(angle)), 6),
            scale=round(float(rng.uniform(0.34, 0.64) if index else rng.uniform(0.48, 0.72)), 6),
            depth=round(float(rng.uniform(-1, 1)), 6), phase=round(float(rng.uniform(0, 2*np.pi)), 6),
            orbit_rate=round(float(rng.uniform(-0.24, 0.24)), 6),
            pulse_rate=round(float(rng.uniform(0.18, 1.25)), 6),
            hue_offset=round(float(rng.uniform(0, 1)), 6),
            topology_mix=round(float(rng.uniform(0.08, 0.92)), 6),
        ))
    relations = [Relation(
        source=organisms[index].id,
        target=organisms[int(rng.integers(0, index))].id,
        kind=str(rng.choice(RELATIONS)), strength=round(float(rng.uniform(0.2, 1.0)), 6),
        phase=round(float(rng.uniform(0, 2*np.pi)), 6),
    ) for index in range(1, count)]
    body = {"version": SCENE_VERSION, "organisms": [asdict(x) for x in organisms],
            "relations": [asdict(x) for x in relations]}
    return identify_scene(body)


def scene_music(profile: dict[str, Any]) -> dict[str, Any]:
    """Derive polyphonic intent from the entire scene, not only its anchor."""
    scene = profile.get("scene", {})
    organisms = scene.get("organisms", []) if isinstance(scene, dict) else []
    relations = scene.get("relations", []) if isinstance(scene, dict) else []
    intervals = [int(round((float(o.get("hue_offset", 0)) - .5) * 14)) for o in organisms]
    return {
        "version": 1,
        "voices": len(organisms),
        "intervals": intervals,
        "polyrhythm": [2 + (int(o.get("seed", 0)) % 7) for o in organisms],
        "relation_accents": [str(r.get("kind")) for r in relations],
        "scene_id": scene.get("scene_id"),
    }


def orchestrate_scene(composition: Any, scene_map: dict[str, Any], duration: float) -> Any:
    """Turn organisms into bounded counterpoint while preserving the base score."""
    intervals = [int(x) for x in scene_map.get("intervals", [])][1:]
    rhythms = [max(2, int(x)) for x in scene_map.get("polyrhythm", [])][1:]
    if not intervals or not getattr(composition, "notes", None):
        return composition
    original = tuple(composition.notes)
    additions = []
    # A sparse selection prevents clipping while making each organism audible.
    for voice_index, (interval, rhythm) in enumerate(zip(intervals, rhythms, strict=False), start=1):
        for note_index, note in enumerate(original):
            if note_index % rhythm:
                continue
            delay = (voice_index * composition.beat_seconds / rhythm) % max(.1, duration)
            start = float(note.start) + delay
            if start >= duration:
                continue
            additions.append(replace(
                note,
                note=int(np.clip(int(note.note) + interval, 24, 108)),
                start=round(start, 6),
                duration=round(min(float(note.duration) * (.55 + .07 * rhythm), duration - start), 6),
                velocity=round(float(note.velocity) / np.sqrt(1 + len(intervals)), 6),
                voice=f"{note.voice}:organism-{voice_index}",
            ))
    return replace(composition, notes=tuple(sorted((*original, *additions), key=lambda n: (n.start, n.voice))))


def scene_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    """Structural novelty in [0, 1], including continuous scene properties."""
    ao, bo = a.get("organisms", []), b.get("organisms", [])
    if not ao or not bo:
        return 1.0
    family_a, family_b = {x.get("family") for x in ao}, {x.get("family") for x in bo}
    union = family_a | family_b
    jaccard = 1.0 - len(family_a & family_b) / max(1, len(union))
    count = abs(len(ao) - len(bo)) / max(len(ao), len(bo))
    rel_a = {x.get("kind") for x in a.get("relations", [])}
    rel_b = {x.get("kind") for x in b.get("relations", [])}
    relation = 1.0 - len(rel_a & rel_b) / max(1, len(rel_a | rel_b))
    av = np.mean([[x.get("x", 0), x.get("y", 0), x.get("scale", .5), x.get("orbit_rate", 0)] for x in ao], axis=0)
    bv = np.mean([[x.get("x", 0), x.get("y", 0), x.get("scale", .5), x.get("orbit_rate", 0)] for x in bo], axis=0)
    continuous = min(1.0, float(np.linalg.norm(av - bv)))
    return round(float(.35*jaccard + .2*count + .2*relation + .25*continuous), 6)
