"""Bounded, versioned memory for candidate and render rejections."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from utils.atomic_state import load_versioned, save_versioned
from utils.state_lock import state_lock

REJECTION_SCHEMA_VERSION = 1
REJECTION_LIMIT = 500
REJECTION_REASONS = frozenset(
    {
        "too_similar",
        "low_motion",
        "bad_composition",
        "puzzle_lost",
        "audio_failure",
        "render_failure",
        "quality_failure",
        "publication_policy_failure",
    }
)


def record_rejection(
    path: Path,
    reason: str,
    *,
    seed: int | None = None,
    family: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Record a normalized failure without persisting secrets or bulky media."""
    normalized = reason if reason in REJECTION_REASONS else "render_failure"
    with state_lock(path):
        records = load_versioned(path, REJECTION_SCHEMA_VERSION, {}, [])
        if not isinstance(records, list):
            records = []
        records.append(
            {
                "at": datetime.now(UTC).isoformat(),
                "reason": normalized,
                "seed": seed,
                "family": family,
                "details": details or {},
            }
        )
        save_versioned(path, records[-REJECTION_LIMIT:], REJECTION_SCHEMA_VERSION)


def recent_rejection_counts(path: Path, limit: int = 100) -> dict[str, int]:
    records = load_versioned(path, REJECTION_SCHEMA_VERSION, {}, []) if path.exists() else []
    counts: dict[str, int] = {}
    for record in records[-max(1, limit):] if isinstance(records, list) else []:
        if isinstance(record, dict):
            reason = str(record.get("reason", "render_failure"))
            counts[reason] = counts.get(reason, 0) + 1
    return counts
