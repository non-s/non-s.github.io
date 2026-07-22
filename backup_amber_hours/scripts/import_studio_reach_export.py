#!/usr/bin/env python3
"""Import optional YouTube Studio Shorts Reach CSV exports."""

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

from utils.studio_reach_schema import read_reach_csv, summarize_reach  # noqa: E402


def _enabled(env: dict | None = None) -> bool:
    value = (env or os.environ).get("STUDIO_REACH_IMPORT_ENABLED", "1")
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _source_paths(root: Path, source: str | None) -> list[Path]:
    if source:
        path = Path(source)
        if not path.is_absolute():
            path = root / path
        return [path] if path.is_file() else sorted(path.glob("*.csv")) if path.exists() else []
    export_dir = root / "_data" / "studio_reach_exports"
    return sorted(export_dir.glob("*.csv")) if export_dir.exists() else []


def import_reach(root: Path = ROOT, source: str | None = None, *, env: dict | None = None) -> dict:
    analytics = root / "_data" / "analytics"
    analytics.mkdir(parents=True, exist_ok=True)
    out = analytics / "studio_reach_daily.jsonl"
    latest = analytics / "studio_reach_latest.json"
    imported_at = datetime.now(timezone.utc).isoformat()
    if not _enabled(env):
        report = {
            "generated_at": imported_at,
            "enabled": False,
            "source_files": [],
            "rows": 0,
            "summary": summarize_reach([]),
        }
        latest.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        return report
    rows: list[dict] = []
    source_files = _source_paths(root, source)
    for path in source_files:
        try:
            rows.extend(read_reach_csv(path, imported_at=imported_at))
        except Exception as exc:
            rows.append(
                {
                    "row_type": "studio_reach_import_error",
                    "imported_at": imported_at,
                    "source_file": str(path),
                    "error": str(exc)[:240],
                }
            )
    out.write_text("", encoding="utf-8")
    with out.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            if row.get("row_type") == "studio_reach_daily":
                handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    summary = summarize_reach([row for row in rows if row.get("row_type") == "studio_reach_daily"])
    report = {
        "generated_at": imported_at,
        "enabled": True,
        "source_files": [str(path) for path in source_files],
        "rows": summary["rows"],
        "summary": summary,
        "output": str(out.relative_to(root)),
    }
    latest.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--source", help="CSV file or folder. Defaults to _data/studio_reach_exports/*.csv.")
    args = parser.parse_args()
    report = import_reach(Path(args.root).resolve(), args.source)
    print(f"studio reach import: {report['rows']} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
