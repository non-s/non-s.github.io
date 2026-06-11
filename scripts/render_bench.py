#!/usr/bin/env python3
"""Lightweight render benchmark over produced metadata files."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def bench(root: Path = ROOT) -> dict:
    start = time.perf_counter()
    metas = []
    for directory in (root / "_videos", root / "_videos_pt-BR"):
        if directory.exists():
            metas.extend(directory.glob("*.json"))
            metas.extend(directory.glob("*.done"))
    sizes = []
    for path in metas:
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(meta, dict):
            continue
        video = root / str(meta.get("video") or "")
        if video.exists():
            sizes.append(video.stat().st_size)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata_files": len(metas),
        "video_files": len(sizes),
        "avg_video_mb": round(sum(sizes) / max(len(sizes), 1) / 1_000_000, 3),
        "scan_seconds": round(time.perf_counter() - start, 4),
    }
    out = root / "_data" / "render_bench.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = bench(Path(args.root).resolve())
    print(json.dumps(report, sort_keys=True, ensure_ascii=False) if args.json else "render_bench: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
