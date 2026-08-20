"""Cheap deterministic resource benchmarks for the autonomous control plane."""

from __future__ import annotations

import json
import time
import tracemalloc
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from utils.atomic_state import atomic_write_json, save_versioned
from utils.candidate_selector import select_candidate
from utils.liquid_wire_quality import _audio_metrics
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
    frame = np.zeros((360, 640), dtype=np.uint8)
    cv2.circle(frame, (320, 180), 100, 255, 2)
    opencv_started = time.perf_counter()
    for _ in range(iterations):
        cv2.Canny(frame, 80, 160)
    opencv_seconds = time.perf_counter() - opencv_started
    seconds = np.linspace(0, 1, 48_000, endpoint=False)
    mono = (0.2 * np.sin(2 * np.pi * 220 * seconds)).astype(np.float32)
    audio = np.column_stack((mono, mono * 0.9))
    audio_started = time.perf_counter()
    audio_result = _audio_metrics(audio)
    audio_seconds = time.perf_counter() - audio_started
    catalog = []
    for index in range(100):
        value = index / 100
        catalog.append(
            {
                "content_id": f"lw_{index}",
                "kind": "short",
                "fitness_window": "72h",
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
        "opencv_mean_ms": 20.0,
        "audio_analysis_ms": 250.0,
        "research_seconds": 2.0,
        "peak_memory_mb": 64.0,
    }
    measurements = {
        "candidate_mean_ms": candidate_seconds / iterations * 1000,
        "opencv_mean_ms": opencv_seconds / iterations * 1000,
        "audio_analysis_ms": audio_seconds * 1000,
        "research_seconds": research_seconds,
        "peak_memory_mb": peak_bytes / 1024 / 1024,
    }
    passed = all(measurements[name] <= limit for name, limit in limits.items())
    render_budget = _observed_render_budget(output.parent)
    passed = passed and render_budget.get("status") != "fail"
    report = {
        "schema_version": 1,
        "iterations": iterations,
        "catalog_size": len(catalog),
        "measurements": {name: round(value, 6) for name, value in measurements.items()},
        "limits": limits,
        "passed": passed,
        "audio_probe": audio_result,
        "render_budget": render_budget,
        "scope": "control plane plus representative OpenCV/audio analysis; render uses observed pipeline metrics",
    }
    atomic_write_json(output, report)
    return report


def _observed_render_budget(data_root: Path) -> dict[str, Any]:
    path = data_root / "pipeline_metrics.json"
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        rows = []
    durations = [
        float(row.get("duration_seconds", 0))
        for row in rows if isinstance(rows, list) and isinstance(row, dict)
        if str(row.get("stage", "")).startswith("generate") and row.get("success")
    ]
    if not durations:
        return {"status": "unmeasured", "limit_seconds": 5400.0}
    latest = durations[-20:]
    maximum = max(latest)
    return {
        "status": "pass" if maximum <= 5400 else "fail",
        "samples": len(latest),
        "max_seconds": round(maximum, 3),
        "limit_seconds": 5400.0,
    }
