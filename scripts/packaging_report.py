#!/usr/bin/env python3
"""Audit pending Shorts packaging: title, thumbnail and community hook."""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.packaging import package_story

QUEUE = ROOT / "_data" / "stories_queue.json"
OUT = ROOT / "_data" / "packaging_report.json"


def _safe(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def main() -> int:
    queue = _safe(QUEUE)
    rows = []
    states = Counter()
    risks = Counter()
    for story in queue.get("stories") or []:
        if not isinstance(story, dict) or story.get("consumed"):
            continue
        packaged = package_story(story)
        pkg = packaged.get("packaging") or {}
        states[str(pkg.get("state") or "unknown")] += 1
        risks.update(pkg.get("risks") or [])
        rows.append(
            {
                "id": story.get("id", ""),
                "title": packaged.get("seo_title") or packaged.get("title") or "",
                "thumbnail_text": packaged.get("thumbnail_text", ""),
                "category": packaged.get("category", ""),
                "packaging": pkg,
            }
        )
    rows.sort(key=lambda item: (item["packaging"].get("score", 0), item["title"]), reverse=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pending": len(rows),
        "states": dict(states),
        "top_risks": dict(risks.most_common(8)),
        "top": rows[:30],
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"packaging report: {len(rows)} pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
