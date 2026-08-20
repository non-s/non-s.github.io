"""Objective rollback criteria for autonomous production changes."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RollbackDecision:
    required: bool
    block_publication: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _recent(entries: list[Any], now: datetime) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    cutoff = now - timedelta(hours=24)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        raw = entry.get("at") or entry.get("timestamp")
        try:
            observed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if observed >= cutoff:
            result.append(entry)
    return result


def assess_rollback(data_root: Path, *, now: datetime | None = None) -> RollbackDecision:
    current = now or datetime.now(UTC)
    reasons: list[str] = []
    block_publication = False
    metrics = _json(data_root / "pipeline_metrics.json", [])
    recent_metrics = _recent(metrics if isinstance(metrics, list) else [], current)
    uploads = [row for row in recent_metrics if str(row.get("stage", "")).startswith("upload")][-5:]
    renders = [row for row in recent_metrics if str(row.get("stage", "")).startswith("generate")][-5:]
    if len(uploads) >= 3 and sum(not bool(row.get("success")) for row in uploads) >= 3:
        reasons.append("upload failure spike")
        block_publication = True
    if len(renders) >= 3 and sum(not bool(row.get("success")) for row in renders) >= 3:
        reasons.append("render failure spike")
    tags = _json(data_root / "video_tags.json", {})
    seen: dict[str, str] = {}
    if isinstance(tags, dict):
        for video_id, record in tags.items():
            content_id = record.get("content_id") if isinstance(record, dict) else None
            if content_id and content_id in seen and seen[content_id] != video_id:
                reasons.append("duplicate content publication detected")
                block_publication = True
                break
            if content_id:
                seen[str(content_id)] = str(video_id)
    for name in ("catalog_memory.json", "research_ledger.json", "canon_state.json"):
        path = data_root / name
        if path.exists() and _json(path, None) is None:
            reasons.append(f"corrupted metadata state: {name}")
            block_publication = True
    return RollbackDecision(bool(reasons), block_publication, tuple(reasons))
