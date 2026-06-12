#!/usr/bin/env python3
"""Classify old uploaded markers that predate current metadata fields."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.humanity_engine import score_story
from utils.retention_surgeon import diagnose
from utils.story_intelligence import audit_hook, audit_title, classify_format

VIDEOS = ROOT / "_videos"
OUT = ROOT / "_data" / "analytics" / "legacy_backfill.json"


def _markers() -> list[dict]:
    rows = []
    for path in sorted(VIDEOS.glob("*.done")) if VIDEOS.exists() else []:
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(item, dict):
            item["_marker"] = path.name
            rows.append(item)
    return rows


def build_backfill() -> dict:
    rows = []
    derived_keys = ("humanity", "studio_state", "story_format", "retention_surgery")
    source_keys = ("hook",)
    for item in _markers():
        title = str(item.get("title") or "")
        hook = str(item.get("hook") or "")
        script = str(item.get("script") or item.get("description") or "")
        story = {**item, "title": title, "hook": hook, "script": script}
        missing_derived = [key for key in derived_keys if not item.get(key)]
        missing_source = [key for key in source_keys if not item.get(key)]
        needs = missing_source + missing_derived
        if not needs:
            continue
        rows.append({
            "video_id": item.get("video_id", ""),
            "marker": item.get("_marker", ""),
            "title": title,
            "missing": needs,
            "missing_source_fields": missing_source,
            "missing_derived_fields": missing_derived,
            "derived": {
                "story_format": item.get("story_format") or classify_format(f"{title} {hook} {script}"),
                "hook_audit": audit_hook(hook).to_dict(),
                "title_audit": audit_title(title).to_dict(),
                "humanity": (item.get("humanity") or score_story(story).to_dict()),
                "retention_surgery": diagnose(story),
            },
        })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "derived_missing_count": sum(1 for row in rows if row.get("missing_derived_fields")),
        "source_missing_count": sum(1 for row in rows if row.get("missing_source_fields")),
        "markers": rows,
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = build_backfill()
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        "legacy backfill: "
        f"{payload['derived_missing_count']} marker(s) need derived metadata; "
        f"{payload['source_missing_count']} marker(s) miss source fields"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
