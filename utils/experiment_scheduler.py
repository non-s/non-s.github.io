"""Power-aware experiment scheduling for low-volume Shorts channels."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from utils.experiment_registry import build_registry

UNDERPOWERED_FILE = Path("_data/underpowered_tests.json")


def plan_experiment_schedule(
    registry: dict | None = None,
    *,
    engaged_views_per_day: float = 371,
    active_axes: list[str] | None = None,
) -> dict:
    registry = registry or build_registry()
    axes = registry.get("axes") or {}
    active_axes = active_axes or []
    creative_active = [axis for axis in active_axes if (axes.get(axis) or {}).get("kind") in {"creative", "packaging"}]
    operational_active = [axis for axis in active_axes if (axes.get(axis) or {}).get("kind") == "operational"]
    low_volume = engaged_views_per_day < 1000
    blocked: list[dict] = []
    if low_volume and len(creative_active) > 1:
        for axis in creative_active[1:]:
            blocked.append({"axis": axis, "reason": "low_volume_one_creative_axis_at_a_time"})
    if low_volume and len(operational_active) > 1:
        for axis in operational_active[1:]:
            blocked.append({"axis": axis, "reason": "low_volume_one_operational_axis_parallel"})
    recommended = []
    for axis, row in axes.items():
        if row.get("kind") in {"creative", "packaging"}:
            recommended.append(axis)
            break
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engaged_views_per_day": engaged_views_per_day,
        "low_volume": low_volume,
        "limits": {
            "creative_axes": 1 if low_volume else 2,
            "operational_axes": 1 if low_volume else 2,
            "multivariate_allowed": not low_volume,
        },
        "active_axes": active_axes,
        "recommended_next_axes": recommended,
        "underpowered_tests": blocked,
    }


def write_underpowered_tests(path: Path = UNDERPOWERED_FILE, **kwargs) -> dict:
    payload = plan_experiment_schedule(**kwargs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload
