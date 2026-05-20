#!/usr/bin/env python3
"""One-shot: delete YouTube-era `_videos/*.done` markers.

Why this exists
---------------
Before the May-2026 platform switch (#145), the YouTube uploader wrote
`.done` sidecars with `url: https://youtube.com/...`. After the switch
those markers became misleading: dashboards / analytics / the daily
digest read them and report YouTube URLs for a TikTok channel that
hasn't actually posted those videos.

What it does
------------
Walks `_videos/*.done`, opens each JSON, and deletes any whose `url`
field points at YouTube. TikTok-era markers (whose `url` starts with
`https://www.tiktok.com/...`) are left alone.

Usage
-----
    python scripts/purge_legacy_done.py            # dry-run
    python scripts/purge_legacy_done.py --apply    # actually delete
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


VIDEOS_DIR = Path("_videos")


def _is_youtube_done(path: Path) -> bool:
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    url = (meta.get("url") or "").lower()
    return "youtube.com" in url or "youtu.be" in url


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--apply", action="store_true",
                   help="Actually delete files (default: dry-run).")
    args = p.parse_args()

    if not VIDEOS_DIR.exists():
        print(f"No {VIDEOS_DIR}/ directory — nothing to do.")
        return 0

    legacy = [d for d in sorted(VIDEOS_DIR.glob("*.done"))
              if _is_youtube_done(d)]
    if not legacy:
        print("✅ No YouTube-era .done markers found.")
        return 0

    print(f"{'Would delete' if not args.apply else 'Deleting'} "
          f"{len(legacy)} legacy .done marker(s):")
    for d in legacy:
        print(f"  - {d.name}")
        if args.apply:
            d.unlink()

    if not args.apply:
        print("\n(dry-run) re-run with --apply to delete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
