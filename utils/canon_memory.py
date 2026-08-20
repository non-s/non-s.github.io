"""Versioned internal canon linking lore, puzzle episodes and lineage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.atomic_state import load_versioned, save_versioned
from utils.state_lock import state_lock

CANON_SCHEMA_VERSION = 1
CANON_LIMIT = 500


def record_canon_event(path: Path, metadata: dict[str, Any]) -> None:
    puzzle = metadata.get("genome", {}).get("puzzle", {})
    if not isinstance(puzzle, dict) or not puzzle.get("enabled"):
        return
    event = {
        "content_id": metadata["content_id"],
        "generated_at": metadata.get("generated_at"),
        "episode": puzzle.get("episode"),
        "message_id": puzzle.get("message_id"),
        "checksum": puzzle.get("checksum"),
        "difficulty": puzzle.get("difficulty"),
        "parents": metadata.get("genome", {}).get("parents", []),
        "canon_version": puzzle.get("canon_version"),
    }
    with state_lock(path):
        canon = load_versioned(path, CANON_SCHEMA_VERSION, {}, {"events": []})
        events = canon.setdefault("events", [])
        conflicts = [
            old
            for old in events
            if old.get("message_id") == event["message_id"] and old.get("checksum") != event["checksum"]
        ]
        if conflicts:
            raise ValueError("canon conflict: one message_id maps to multiple checksums")
        if not any(old.get("content_id") == event["content_id"] for old in events):
            events.append(event)
        canon["events"] = events[-CANON_LIMIT:]
        save_versioned(path, canon, CANON_SCHEMA_VERSION)
