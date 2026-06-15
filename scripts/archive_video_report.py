#!/usr/bin/env python3
"""Report safe Internet Archive video candidates for Wild Brief."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.internet_archive import discover_public_domain_videos  # noqa: E402


DEFAULT_QUERIES = [
    "birds wildlife",
    "ocean animals",
    "insects nature",
    "farm animals",
    "reptiles wildlife",
    "arctic animals",
    "forest wildlife",
]


def build_report(queries: list[str], *, rows: int = 12, limit: int = 24) -> dict:
    seen: set[str] = set()
    candidates: list[dict] = []
    for query in queries:
        for asset in discover_public_domain_videos(query, rows=rows):
            key = f"{asset.identifier}:{asset.file_name}"
            if key in seen:
                continue
            seen.add(key)
            row = asset.to_manifest_row()
            row["query"] = query
            candidates.append(row)
            if len(candidates) >= limit:
                break
        if len(candidates) >= limit:
            break
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Internet Archive",
        "rights_policy": "explicit_public_domain_cc0_or_usgov_only",
        "query_count": len(queries),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", action="append", dest="queries", help="Archive search query. Repeatable.")
    parser.add_argument("--rows", type=int, default=12)
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument("--out", default="_data/archive_video_candidates.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    queries = args.queries or DEFAULT_QUERIES
    report = build_report(queries, rows=max(1, args.rows), limit=max(1, args.limit))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(f"archive video candidates: {report['candidate_count']} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
