#!/usr/bin/env python3
"""Build operator-ready crosspost copy packs from uploaded Short markers."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def build_pack(root: Path = ROOT, limit: int = 10) -> dict:
    items = []
    for directory in (root / "_videos", root / "_videos_pt-BR"):
        if directory.exists():
            for path in sorted(directory.glob("*.done"), key=lambda p: p.stat().st_mtime, reverse=True):
                marker = _read_json(path)
                if not marker:
                    continue
                title = str(marker.get("title") or "Wild Brief")
                url = str(marker.get("url") or "")
                tags = " ".join("#" + str(tag).lstrip("#") for tag in (marker.get("tags") or [])[:5])
                items.append(
                    {
                        "video_id": marker.get("video_id", ""),
                        "title": title,
                        "url": url,
                        "shortform_caption": f"{title} {tags}".strip()[:2200],
                        "instagram_caption": f"{title}\n\n{url}\n\n{tags}".strip()[:2200],
                        "shorts_caption": marker.get("description", "")[:5000],
                    }
                )
                if len(items) >= limit:
                    break
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "items": items}
    out = root / "_data" / "crosspost_pack.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_pack(Path(args.root).resolve())
    print(
        json.dumps(report, sort_keys=True, ensure_ascii=True)
        if args.json
        else f"crosspost_pack: {len(report['items'])} items"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
