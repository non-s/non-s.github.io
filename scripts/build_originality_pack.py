#!/usr/bin/env python3
"""Build originality/transformation JSONL packs for pending or done Shorts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.originality_pack import write_originality_pack  # noqa: E402


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def build_packs(root: Path = ROOT, path: Path | None = None) -> dict:
    out = path or (root / "_data" / "originality_pack.jsonl")
    scanned = written = incomplete = 0
    for directory in (root / "_videos", root / "_videos_pt-BR"):
        if not directory.exists():
            continue
        for meta_path in sorted(directory.glob("*.json")) + sorted(directory.glob("*.done")):
            meta = _read_json(meta_path)
            if not meta:
                continue
            scanned += 1
            result = write_originality_pack(meta, out)
            written += int(bool(result.get("written")))
            incomplete += 0 if result["pack"].get("complete") else 1
    return {"scanned": scanned, "written": written, "incomplete": incomplete, "path": str(out)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_packs(Path(args.root).resolve())
    print(
        json.dumps(report, sort_keys=True, ensure_ascii=False)
        if args.json
        else f"originality_pack: {report['written']} written"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
