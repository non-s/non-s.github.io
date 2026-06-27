#!/usr/bin/env python3
"""Write the Wild Brief level-up operating system."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.analytics_schema import read_jsonl
from utils.level_system import build_level_system

OUT = ROOT / "_data" / "level_system.json"


def _safe(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def main() -> int:
    payload = build_level_system(
        health=_safe(ROOT / "_data" / "automation_health.json"),
        dry_run=_safe(ROOT / "_data" / "dry_run_publish.json"),
        next_shorts=_safe(ROOT / "_data" / "next_shorts.json"),
        queue_audit=_safe(ROOT / "_data" / "queue_audit.json"),
        scale_blueprint=_safe(ROOT / "_data" / "scale_blueprint.json"),
        comments=_safe(ROOT / "_data" / "analytics" / "comments.json"),
        crosspost_pack=_safe(ROOT / "_data" / "crosspost_pack.json"),
        upload_intents=read_jsonl(ROOT / "_data" / "upload_intents.jsonl"),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    level = payload.get("current_level") or {}
    boss = payload.get("boss") or {}
    print(
        "level system: "
        f"level={level.get('number')} {level.get('name')} "
        f"boss={boss.get('id')} progress={payload.get('overall_progress_pct')}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
