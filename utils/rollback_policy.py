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


# A replay/re-render of the same genome legitimately shares a ``content_id``
# across different ``video_id``s. Treating that as a "duplicate publication"
# created a self-reinforcing kill switch: every rebuild of the append-only
# ledger re-detected the same pair and kept ``publication_allowed`` false
# forever. A real duplicate is the *same* content (content_id + visual_dna_id)
# re-published inside a short window. Re-renders, legacy receipt recovery and
# cross-artifact idempotent rebuilds must not trigger the guard.
DUPLICATE_WINDOW = timedelta(hours=6)


def _detect_duplicate_publication(tags: Any, now: datetime) -> tuple[bool, str]:
    """Return ``(is_duplicate, reason)`` for genuine re-publication of content.

    ``tags`` maps ``video_id`` -> tag record. A record is suspicious only when
    another record shares both ``content_id`` and ``visual_dna_id`` *and* was
    uploaded within ``DUPLICATE_WINDOW``. The legacy receipt recovery path
    (``publication_ledger._legacy_receipts``) intentionally leaves
    ``visual_dna_id`` blank when evidence is ambiguous, so those never match
    here and cannot poison the guard.
    """
    if not isinstance(tags, dict):
        return False, ""
    by_content: dict[tuple[str, str], list[tuple[datetime, str]]] = {}
    for video_id, record in tags.items():
        if not isinstance(record, dict):
            continue
        content_id = str(record.get("content_id", "") or "")
        visual_dna_id = str(record.get("visual_dna_id", "") or "")
        if not content_id or not visual_dna_id:
            continue
        raw = record.get("uploaded_at")
        try:
            observed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=UTC)
        by_content.setdefault((content_id, visual_dna_id), []).append((observed, str(video_id)))
    for (content_id, visual_dna_id), entries in by_content.items():
        if len(entries) < 2:
            continue
        entries.sort(key=lambda item: item[0])
        for older, newer in zip(entries, entries[1:], strict=False):
            if newer[0] - older[0] <= DUPLICATE_WINDOW and newer[1] != older[1]:
                return True, (
                    f"duplicate content publication detected: content_id={content_id} "
                    f"visual_dna_id={visual_dna_id} "
                    f"video_ids={older[1]},{newer[1]} "
                    f"within_{int(DUPLICATE_WINDOW.total_seconds())}s"
                )
    return False, ""


def assess_rollback(data_root: Path, *, now: datetime | None = None) -> RollbackDecision:
    current = now or datetime.now(UTC)
    reasons: list[str] = []
    block_publication = False
    metrics = _json(data_root / "pipeline_metrics.json", [])
    recent_metrics = _recent(metrics if isinstance(metrics, list) else [], current)
    # Count only failures after a candidate passed the local production
    # contract. Historically, policy rejections were recorded as upload
    # failures too, creating a self-reinforcing publication kill switch.
    uploads = [
        row
        for row in recent_metrics
        if str(row.get("stage", "")).startswith("upload")
        and isinstance(row.get("details"), dict)
        and row["details"].get("remote_attempted") is True
    ][-5:]
    renders = [row for row in recent_metrics if str(row.get("stage", "")).startswith("generate")][-5:]
    if len(uploads) >= 3 and sum(not bool(row.get("success")) for row in uploads) >= 3:
        reasons.append("upload failure spike")
        block_publication = True
    if len(renders) >= 3 and sum(not bool(row.get("success")) for row in renders) >= 3:
        reasons.append("render failure spike")
    tags = _json(data_root / "video_tags.json", {})
    is_duplicate, duplicate_reason = _detect_duplicate_publication(tags, current)
    if is_duplicate:
        reasons.append(duplicate_reason)
        block_publication = True
    for name in ("catalog_memory.json", "research_ledger.json", "canon_state.json"):
        path = data_root / name
        if path.exists() and _json(path, None) is None:
            reasons.append(f"corrupted metadata state: {name}")
            block_publication = True
    return RollbackDecision(bool(reasons), block_publication, tuple(reasons))
