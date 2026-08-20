"""Cheap deterministic resource benchmarks for the autonomous control plane."""

from __future__ import annotations

import json
import time
import tracemalloc
from pathlib import Path
from typing import Any

from utils.atomic_state import save_versioned
from utils.candidate_selector import select_candidate
from utils.research_cycle import run_research_cycle


def run_benchmarks(output: Path, *, iterations: int = 200) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "seed": 42,
        "family": "orb",
        "folds_theta": 3,
        "folds_phi": 5,
        "melt_rate": 0.2,
        "palette": {"base_hue": 0.4},
    }
    tracemalloc.start()
    started = time.perf_counter()
    for _ in range(iterations):
        select_candidate(profile, "short", [])
    candidate_seconds = time.perf_counter() - started
    catalog = []
    for index in range(100):
        value = index / 100
        catalog.append(
            {
                "content_id": f"lw_{index}",
                "kind": "short",
                "genome": {"family": "orb" if index % 2 else "ribbon"},
                "fitness": {"score": value, "confidence": 0.8},
                "visual_dna": {
                    "composition": {"screen_fill": value, "symmetry": value, "entropy": value},
                    "motion": {"optical_flow_mean": value},
                    "appearance": {"brightness": value, "saturation": value},
                    "temporal": {"opening_activity": value},
                },
            }
        )
    data_root = output.parent / ".benchmark_state"
    save_versioned(data_root / "catalog_memory.json", catalog, 1, backup=False)
    research_started = time.perf_counter()
    run_research_cycle(data_root)
    research_seconds = time.perf_counter() - research_started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    limits = {
        "candidate_mean_ms": 10.0,
        "research_seconds": 2.0,
        "peak_memory_mb": 64.0,
    }
    measurements = {
        "candidate_mean_ms": candidate_seconds / iterations * 1000,
        "research_seconds": research_seconds,
        "peak_memory_mb": peak_bytes / 1024 / 1024,
    }
    passed = all(measurements[name] <= limit for name, limit in limits.items())
    report = {
        "schema_version": 1,
        "iterations": iterations,
        "catalog_size": len(catalog),
        "measurements": {name: round(value, 6) for name, value in measurements.items()},
        "limits": limits,
        "passed": passed,
        "scope": "control-plane only; render/FFmpeg budgets come from pipeline_metrics.json",
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
