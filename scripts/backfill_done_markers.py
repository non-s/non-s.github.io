#!/usr/bin/env python3
"""Backfill modern quality fields into historical .done markers."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.packaging import package_story
from utils.publish_score import score_metadata
from utils.subscriber_conversion import score_subscriber_conversion
from utils.humanity_engine import score_story as score_humanity
from utils.retention_surgeon import diagnose
from utils.story_intelligence import classify_format
from utils.youtube_brain import publish_brain


def backfill_marker(marker: dict) -> tuple[dict, bool]:
    out = dict(marker)
    changed = False
    story_text = " ".join(str(out.get(key) or "") for key in ("title", "hook", "script", "description"))
    story = {
        **out,
        "title": out.get("seo_title") or out.get("title") or "",
        "hook": out.get("hook") or "",
        "script": out.get("script") or out.get("description") or "",
    }
    if not out.get("story_format"):
        out["story_format"] = classify_format(story_text)
        changed = True
    if not out.get("humanity"):
        out["humanity"] = score_humanity(story).to_dict()
        changed = True
    if not out.get("retention_surgery"):
        out["retention_surgery"] = diagnose(story)
        changed = True
    if not out.get("studio_state"):
        out["studio_state"] = "legacy_backfilled"
        changed = True
    packaged = package_story(out)
    if not out.get("packaging"):
        out["packaging"] = packaged.get("packaging") or {}
        out["pinned_comment"] = out.get("pinned_comment") or out["packaging"].get("pinned_comment", "")
        changed = True
    if not out.get("publish_score"):
        out["publish_score"] = score_metadata(out)
        changed = True
    if not out.get("subscriber_conversion"):
        out["subscriber_conversion"] = (out.get("packaging") or {}).get(
            "subscriber_conversion"
        ) or score_subscriber_conversion(out)
        changed = True
    if not out.get("youtube_brain"):
        out["youtube_brain"] = publish_brain(out)
        changed = True
    return out, changed


def main() -> int:
    changed = 0
    scanned = 0
    for path in sorted(Path("_videos").glob("*.done")):
        scanned += 1
        marker = json.loads(path.read_text(encoding="utf-8"))
        updated, did_change = backfill_marker(marker)
        if did_change:
            path.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
            changed += 1
    print(f"backfill_done_markers: {changed}/{scanned} updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
