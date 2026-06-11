#!/usr/bin/env python3
"""Build a zero-cost fact/source guard report for queue and rendered metadata."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.claim_risk import evaluate_claim_risk  # noqa: E402

REPORT_FILE = ROOT / "_data" / "fact_guard_report.json"
SOURCES_FILE = ROOT / "_data" / "fact_sources.jsonl"


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _items(root: Path) -> list[dict]:
    queue = _read_json(root / "_data" / "stories_queue.json", {})
    stories = [item for item in (queue.get("stories") or []) if isinstance(item, dict)]
    metas = []
    for directory in (root / "_videos", root / "_videos_pt-BR"):
        if directory.exists():
            for path in sorted(directory.glob("*.json")) + sorted(directory.glob("*.done")):
                data = _read_json(path, {})
                if isinstance(data, dict):
                    data["_path"] = str(path.relative_to(root))
                    metas.append(data)
    return stories + metas


def _source_row(item: dict) -> dict:
    return {
        "story_id": str(item.get("id") or item.get("story_id") or item.get("story_slug") or ""),
        "title": str(item.get("title") or item.get("seo_title") or "")[:160],
        "source_url": str(item.get("source_url") or item.get("url") or item.get("commons_page_url") or ""),
        "source_license": str(item.get("source_license") or item.get("commons_license") or ""),
        "scientific_name": str(item.get("scientific_name") or (item.get("gbif") or {}).get("scientificName") or ""),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def _write_sources(rows: list[dict], path: Path) -> int:
    existing = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            existing.add((str(row.get("story_id") or ""), str(row.get("source_url") or "")))
    written = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            key = (row["story_id"], row["source_url"])
            if key in existing or not any(key):
                continue
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
            existing.add(key)
            written += 1
    return written


def build_fact_guard(root: Path = ROOT) -> dict:
    rows = []
    source_rows = []
    for item in _items(root):
        risk = evaluate_claim_risk(item)
        rows.append(
            {
                "story_id": str(item.get("id") or item.get("story_id") or item.get("story_slug") or ""),
                "title": str(item.get("title") or item.get("seo_title") or "")[:160],
                "level": risk["level"],
                "claim_count": risk["claim_count"],
                "has_source": risk["has_source"],
            }
        )
        source_rows.append(_source_row(item))
    written = _write_sources(source_rows, root / "_data" / "fact_sources.jsonl")
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["level"]] = counts.get(row["level"], 0) + 1
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": len(rows),
        "counts": counts,
        "sources_written": written,
        "blocked": [row for row in rows if row["level"] == "block"][:20],
    }
    out = root / "_data" / "fact_guard_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_fact_guard(Path(args.root).resolve())
    if args.json:
        print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    else:
        print(f"fact_guard: {report['items']} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
