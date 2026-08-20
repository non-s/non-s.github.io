from utils.semantic_memory import (
    SEMANTIC_VECTOR_SIZE,
    build_semantic_signature,
    load_archive_signatures,
    nearest_semantic_signature,
    semantic_distance,
)


def _profile(family: str = "orb", relation: str = "fusion") -> dict:
    return {
        "genre": "ambient",
        "duration": 30,
        "scene": {
            "organisms": [
                {"family": family, "role": "anchor", "scale": .6, "orbit_rate": .1, "pulse_rate": .5, "hue_offset": .2},
                {
                    "family": "ribbon", "role": "echo", "scale": .4,
                    "orbit_rate": -.2, "pulse_rate": .8, "hue_offset": .8,
                },
            ],
            "relations": [{"kind": relation}],
            "matter": {"cohesion": .7, "viscosity": .9, "elasticity": .8},
        },
        "timeline": [
            {"kind": "emergence", "start": 0, "duration": 8},
            {"kind": "fusion", "start": 8, "duration": 22},
        ],
        "scene_music": {"agents": [{"transform": "rotate"}, {"transform": "invert"}]},
        "composition": {
            "mode": "dorian", "progression": [0, 3, 4],
            "notes": [{"voice": "motif", "note": 60, "start": 0, "duration": 1}],
        },
    }


def test_semantic_signature_is_interpretable_fixed_and_deterministic():
    first = build_semantic_signature(_profile(), "short")
    assert first == build_semantic_signature(_profile(), "short")
    assert len(first["vector"]) == SEMANTIC_VECTOR_SIZE
    assert "narrative:emergence>fusion" in first["concepts"]
    assert semantic_distance(first, first) == 0
    assert semantic_distance(first, build_semantic_signature(_profile("gyroid", "braid"), "short")) > 0


def test_cross_format_memory_recognizes_same_idea_without_using_format_as_meaning():
    short = build_semantic_signature(_profile(), "short")
    long = build_semantic_signature(_profile(), "long")
    result = nearest_semantic_signature(long, [{
        "content_id": "lw_short", "kind": "short", "semantic_signature": short,
    }])
    assert semantic_distance(short, long) == 0
    assert result["cross_format_nearest"]["content_id"] == "lw_short"
    assert result["cross_format_nearest"]["distance"] == 0


def test_evicted_archive_prototype_remains_searchable(tmp_path):
    from utils.atomic_state import save_versioned

    signature = build_semantic_signature(_profile(), "short")
    save_versioned(tmp_path / "catalog_archive.json", {"cells": {
        "orb|short": {
            "semantic_centroid": signature["vector"],
            "semantic_concepts": {concept: 1 for concept in signature["concepts"]},
        }
    }}, 1)
    archive = load_archive_signatures(tmp_path)
    result = nearest_semantic_signature(signature, [], archive)
    assert result["nearest"]["content_id"] == "archive:orb|short"
    assert result["nearest"]["distance"] == 0
