#!/usr/bin/env python3
"""Repair stale copy in consumed queue records without changing upload state."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.editorial_guard import editorial_issues
from utils.local_rewriter import rescue_story
from utils.packaging import package_story
from utils.youtube_brain import creator_premortem

QUEUE = ROOT / "_data" / "stories_queue.json"
OUT = ROOT / "_data" / "queue_history_repair.json"

PRESERVE_KEYS = {
    "consumed",
    "consumed_at",
    "consumed_reason",
    "uploaded_at",
    "uploaded_record",
    "uploaded_url",
    "uploaded_video_id",
    "youtube_video_id",
}
STALE_PATTERNS = (
    re.compile(r"\bone leaves\b", re.I),
    re.compile(r"\bthis forests changes\b", re.I),
    re.compile(r"\bforests use it\b", re.I),
    re.compile(r"\bnow the forests at the start makes sense\b", re.I),
    re.compile(r"\bcute behavior matters\b", re.I),
)


def _has_stale_text(story: dict[str, Any]) -> bool:
    return any(pattern.search(json.dumps(story, ensure_ascii=False)) for pattern in STALE_PATTERNS)


def _refresh_derived_fields(story: dict[str, Any]) -> dict[str, Any]:
    base = dict(story)
    for key in ("packaging", "youtube_brain"):
        base.pop(key, None)
    packaged = package_story(base)
    packaged["youtube_brain"] = creator_premortem(packaged)
    return packaged


def repair_story(story: dict[str, Any]) -> tuple[dict[str, Any], list[str], bool]:
    """Return a repaired consumed story while preserving upload bookkeeping."""
    if not story.get("consumed"):
        return story, [], False
    issues = editorial_issues(story)
    stale = _has_stale_text(story)
    if not issues and not stale:
        return story, [], False
    if issues:
        repaired, applied = rescue_story(story, issues)
    else:
        repaired, applied = dict(story), True
    if not applied:
        return story, issues, False
    repaired = _refresh_derived_fields(dict(repaired))
    for key in PRESERVE_KEYS:
        if key in story:
            repaired[key] = story[key]
    repaired["history_repair"] = {
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "issues": issues,
        "refreshed_stale_derived_fields": stale,
        "previous_title_had_issues": bool(issues),
    }
    return repaired, issues, True


def repair_queue(queue: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    changed = 0
    held: list[dict[str, Any]] = []
    stories = []
    for story in queue.get("stories") or []:
        if not isinstance(story, dict):
            stories.append(story)
            continue
        repaired, issues, applied = repair_story(story)
        if applied:
            changed += 1
        elif issues:
            held.append(
                {
                    "id": story.get("id"),
                    "title": story.get("title") or story.get("seo_title"),
                    "issues": issues,
                }
            )
        stories.append(repaired)
    out = dict(queue)
    out["stories"] = stories
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "changed": changed,
        "held": held,
    }
    return out, summary


def main() -> int:
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    repaired, summary = repair_queue(queue)
    QUEUE.write_text(json.dumps(repaired, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"queue_history_repair: {summary['changed']} repaired, {len(summary['held'])} held")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
