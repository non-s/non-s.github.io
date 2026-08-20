"""Governed autonomy: kill switches, safe mode and failure-rate guardrails."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True)
class AutonomyState:
    generation_allowed: bool
    publication_allowed: bool
    safe_mode: bool
    reasons: tuple[str, ...]
    evolution_mode: Literal["off", "shadow", "canary", "active"]
    puzzles_allowed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _recent_failures(data_root: Path) -> int:
    path = data_root / "dead_letter_queue.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    return len(value[-6:]) if isinstance(value, list) else 0


def assess_autonomy(data_root: Path) -> AutonomyState:
    reasons: list[str] = []
    killed = os.environ.get("LIQUID_WIRE_KILL_SWITCH", "0") == "1"
    publication_killed = os.environ.get("LIQUID_WIRE_PUBLICATION_KILL_SWITCH", "0") == "1"
    forced_safe = os.environ.get("LIQUID_WIRE_SAFE_MODE", "0") == "1"
    failures = _recent_failures(data_root)
    if killed:
        reasons.append("global kill switch enabled")
    if publication_killed:
        reasons.append("publication kill switch enabled")
    if forced_safe:
        reasons.append("safe mode explicitly enabled")
    if failures >= 3:
        reasons.append(f"failure-rate guardrail: {failures} recent dead letters")
    safe = forced_safe or failures >= 3
    configured = os.environ.get("LIQUID_WIRE_EVOLUTION_MODE", "shadow")
    configured_evolution: Literal["off", "shadow", "canary", "active"] = (
        configured if configured in {"off", "shadow", "canary", "active"} else "shadow"  # type: ignore[assignment]
    )
    return AutonomyState(
        generation_allowed=not killed,
        publication_allowed=not killed and not publication_killed,
        safe_mode=safe,
        reasons=tuple(reasons),
        evolution_mode="off" if safe else configured_evolution,
        puzzles_allowed=not safe,
    )
