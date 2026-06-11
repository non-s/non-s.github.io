#!/usr/bin/env python3
"""Annotate the queue with zero-cost topic freshness metadata."""
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

from utils.topic_freshness import annotate_queue, freshness_report  # noqa: E402


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, type(default)) else default
    except Exception:
        return default


def apply_freshness(root: Path = ROOT) -> dict:
    enabled = os.environ.get("TOPIC_FRESHNESS_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}
    queue_path = root / "_data" / "stories_queue.json"
    candidates_path = root / "_data" / "trends" / "topic_candidates.json"
    report_path = root / "_data" / "trends" / "freshness_report.json"
    queue = _read_json(queue_path, {"stories": []})
    candidates = (_read_json(candidates_path, {}).get("candidates") or []) if enabled else []
    annotated = annotate_queue(queue, candidates) if enabled else queue
    report = freshness_report(annotated)
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["enabled"] = enabled
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    if enabled and queue_path.exists():
        annotated["updated_at"] = datetime.now(timezone.utc).isoformat()
        queue_path.write_text(
            json.dumps(annotated, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    report = apply_freshness(Path(args.root).resolve())
    print(f"topic freshness: {report['scored']}/{report['pending']} scored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
