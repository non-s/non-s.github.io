#!/usr/bin/env python3
"""Build and optionally queue Shorts ideas from viewer comments."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.comment_to_short import build_candidates, merge_into_queue  # noqa: E402


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _markers(root: Path) -> list[dict]:
    rows = []
    for path in sorted((root / "_videos").glob("*.done")) if (root / "_videos").exists() else []:
        item = _read_json(path, {})
        if isinstance(item, dict):
            rows.append(item)
    return rows


def run(root: Path = ROOT) -> dict:
    data_dir = root / "_data"
    comments = _read_json(data_dir / "analytics" / "comments.json", {})
    candidates = build_candidates(comments if isinstance(comments, dict) else {}, _markers(root))
    min_score = float(os.environ.get("COMMENT_TO_SHORT_MIN_SCORE", "64") or 64)
    max_items = int(os.environ.get("COMMENT_TO_SHORT_MAX_ITEMS", "6") or 6)
    enabled = os.environ.get("COMMENT_TO_SHORT_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
    queued = 0
    updated = 0
    removed = 0
    if enabled and candidates:
        queue_path = data_dir / "stories_queue.json"
        queue = _read_json(queue_path, {"stories": []})
        merged = merge_into_queue(
            queue if isinstance(queue, dict) else {"stories": []}, candidates, min_score=min_score, max_items=max_items
        )
        queued = int(merged.get("comment_to_short_added", 0) or 0)
        updated = int(merged.get("comment_to_short_updated", 0) or 0)
        removed = int(merged.get("comment_to_short_removed", 0) or 0)
        if queued or updated or removed:
            queue_path.parent.mkdir(parents=True, exist_ok=True)
            queue_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "enabled": enabled,
        "min_score": min_score,
        "candidates": candidates[:50],
        "queued": queued,
        "updated": updated,
        "removed": removed,
    }
    out = data_dir / "comment_to_short_candidates.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    payload = run(Path(args.root).resolve())
    print(
        f"comment_to_short: {len(payload['candidates'])} candidate(s), "
        f"{payload['queued']} queued, {payload['updated']} updated, {payload['removed']} removed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
