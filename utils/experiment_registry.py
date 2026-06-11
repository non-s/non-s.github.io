"""Governed experiment registry derived from the live axis list."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from utils.experiments import AXES

REGISTRY_FILE = Path("_data/experiment_registry.json")

CREATIVE_AXES = {
    "hook_style",
    "script_tone",
    "opening_visual_pattern",
    "subtitle_density",
    "loop_style",
    "cta_pattern",
    "end_card_style",
    "title_shape",
    "music_bed",
}


def _axis_kind(axis: str) -> str:
    if axis in CREATIVE_AXES:
        return "creative"
    if axis in {"narrator_voice", "thumbnail_style"}:
        return "packaging"
    return "operational"


def build_registry() -> dict:
    axes = {}
    for axis in AXES:
        default = axis.variants[0] if axis.variants else ""
        axes[axis.name] = {
            "variants": list(axis.variants),
            "default_variant": default,
            "hypothesis": f"{axis.description} Default {default} remains the control until enough engaged views accumulate.",
            "primary_metric": "continued_watch_rate",
            "guardrail_metric": "swipe_rate",
            "window_days": 14,
            "owner": "wild_brief_operator",
            "kind": _axis_kind(axis.name),
            "promotion_rule": "promote only with explicit hypothesis, >=8 samples per variant and no guardrail regression",
        }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registry_version": "experiment-governance-v2",
        "axes": axes,
    }


def validate_registry(registry: dict | None = None) -> dict:
    registry = registry or build_registry()
    axes = registry.get("axes") or {}
    registered = set(axes)
    live = {axis.name for axis in AXES}
    orphan_live_axes = sorted(live - registered)
    stale_registry_axes = sorted(registered - live)
    missing_hypothesis = sorted(axis for axis, row in axes.items() if not (row or {}).get("hypothesis"))
    return {
        "ok": not (orphan_live_axes or stale_registry_axes or missing_hypothesis),
        "orphan_live_axes": orphan_live_axes,
        "stale_registry_axes": stale_registry_axes,
        "missing_hypothesis": missing_hypothesis,
        "axis_count": len(axes),
    }


def write_registry(path: Path = REGISTRY_FILE) -> dict:
    registry = build_registry()
    registry["validation"] = validate_registry(registry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return registry
