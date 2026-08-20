"""Governed autonomy: kill switches, safe mode and failure-rate guardrails."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from utils.rollback_policy import assess_rollback


@dataclass(frozen=True)
class AutonomyState:
    generation_allowed: bool
    publication_allowed: bool
    safe_mode: bool
    reasons: tuple[str, ...]
    evolution_mode: Literal["off", "shadow", "canary", "active"]
    puzzles_allowed: bool
    gemini_allowed: bool
    schedules_allowed: bool
    force_private: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _recent_failures(data_root: Path) -> int:
    path = data_root / "dead_letter_queue.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    count = 0
    for item in value[-20:] if isinstance(value, list) else []:
        try:
            timestamp = datetime.fromisoformat(str(item.get("timestamp", "")).replace("Z", "+00:00"))
        except (AttributeError, TypeError, ValueError):
            continue
        count += int(timestamp >= cutoff)
    return count


def assess_autonomy(data_root: Path) -> AutonomyState:
    reasons: list[str] = []
    killed = os.environ.get("LIQUID_WIRE_KILL_SWITCH", "0") == "1"
    publication_killed = os.environ.get("LIQUID_WIRE_PUBLICATION_KILL_SWITCH", "0") == "1"
    upload_killed = os.environ.get("LIQUID_WIRE_DISABLE_UPLOAD", "0") == "1"
    gemini_killed = os.environ.get("LIQUID_WIRE_DISABLE_GEMINI", "0") == "1"
    evolution_killed = os.environ.get("LIQUID_WIRE_DISABLE_EVOLUTION", "0") == "1"
    puzzle_killed = os.environ.get("LIQUID_WIRE_DISABLE_PUZZLE", "0") == "1"
    schedules_killed = os.environ.get("LIQUID_WIRE_PAUSE_SCHEDULES", "0") == "1"
    force_private = os.environ.get("LIQUID_WIRE_FORCE_PRIVATE", "0") == "1"
    forced_safe = os.environ.get("LIQUID_WIRE_SAFE_MODE", "0") == "1"
    failures = _recent_failures(data_root)
    rollback = assess_rollback(data_root)
    if killed:
        reasons.append("global kill switch enabled")
    if publication_killed:
        reasons.append("publication kill switch enabled")
    if upload_killed:
        reasons.append("upload kill switch enabled")
    if forced_safe:
        reasons.append("safe mode explicitly enabled")
    if failures >= 3:
        reasons.append(f"failure-rate guardrail: {failures} recent dead letters")
    reasons.extend(reason for reason in rollback.reasons if reason not in reasons)
    safe = forced_safe or failures >= 3 or rollback.required
    configured = os.environ.get("LIQUID_WIRE_EVOLUTION_MODE", "shadow")
    configured_evolution: Literal["off", "shadow", "canary", "active"] = (
        configured if configured in {"off", "shadow", "canary", "active"} else "shadow"  # type: ignore[assignment]
    )
    if evolution_killed:
        reasons.append("evolution kill switch enabled")
    if puzzle_killed:
        reasons.append("puzzle kill switch enabled")
    if gemini_killed:
        reasons.append("Gemini kill switch enabled")
    if schedules_killed:
        reasons.append("schedule pause enabled")
    return AutonomyState(
        generation_allowed=not killed,
        publication_allowed=(
            not killed and not publication_killed and not upload_killed and not rollback.block_publication
        ),
        safe_mode=safe,
        reasons=tuple(reasons),
        evolution_mode="off" if safe or evolution_killed else configured_evolution,
        puzzles_allowed=not safe and not puzzle_killed,
        gemini_allowed=not gemini_killed,
        schedules_allowed=not schedules_killed and not killed,
        force_private=force_private or safe,
    )
