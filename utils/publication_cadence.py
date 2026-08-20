"""Adaptive publication frequency guard based on actual recent channel state."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class CadenceDecision:
    generate: bool
    reason: str
    recent_publications: int
    daily_limit: int

    def to_dict(self):
        return asdict(self)


def decide_cadence(data_root: Path, *, now: datetime | None = None, manual: bool = False) -> CadenceDecision:
    if manual:
        return CadenceDecision(True, "manual dispatch", 0, 0)
    current = now or datetime.now(UTC)
    try:
        daily_limit = min(4, max(1, int(os.environ.get("LIQUID_WIRE_DAILY_PUBLICATION_LIMIT", "3"))))
    except ValueError:
        daily_limit = 3
    try:
        tags = json.loads((data_root / "video_tags.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        tags = {}
    uploaded: list[datetime] = []
    for item in tags.values() if isinstance(tags, dict) else []:
        if not isinstance(item, dict):
            continue
        try:
            uploaded.append(datetime.fromisoformat(str(item.get("uploaded_at", "")).replace("Z", "+00:00")))
        except ValueError:
            continue
    recent = [timestamp for timestamp in uploaded if timestamp >= current - timedelta(hours=24)]
    if len(recent) >= daily_limit:
        return CadenceDecision(False, "daily publication limit reached", len(recent), daily_limit)
    if recent and current - max(recent) < timedelta(hours=6):
        return CadenceDecision(False, "minimum six-hour learning interval not reached", len(recent), daily_limit)
    return CadenceDecision(True, "cadence budget available", len(recent), daily_limit)
