#!/usr/bin/env python3
"""Remove b-roll clips whose metadata shows no real anime-style evidence.

One-off/manual admin tool. Checked live: a "man with a stack of books"
generic 3D stock-animation clip (Pixabay id 115021) slipped into the
b-roll library despite matching an "anime library reading" query, and
played on the 24/7 live relay looking nothing like the intended
Lofi-Girl-style loop. Clips downloaded before scripts/sync_lofi_broll.py
grew its anime-style tag filter don't have full tag data saved (only a
single first tag as "title"), so the reliable retroactive signal is
Pixabay's own is_ai_generated flag: checked by hand against every clip
in the library during this incident, every AI-generated clip had a
plausible anime-style first tag ("anime", "ai generated"), every
non-AI-generated one had a generic single-word stock tag ("man", "girl",
"train", "window").
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BROLL_DIR = ROOT / "_assets" / "video" / "lofi_broll"


def find_offbrand_clips(broll_dir: Path) -> list[Path]:
    offbrand = []
    for meta_path in sorted(broll_dir.glob("pixabay_*.json")):
        try:
            meta = json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if not meta.get("is_ai_generated"):
            offbrand.append(meta_path)
    return offbrand


def main() -> int:
    removed = 0
    for meta_path in find_offbrand_clips(BROLL_DIR):
        title = "?"
        try:
            title = json.loads(meta_path.read_text()).get("title", "?")
        except (json.JSONDecodeError, OSError):
            pass
        print(f"Removing off-brand clip {meta_path.stem} (title={title!r})")
        meta_path.with_suffix(".mp4").unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        removed += 1
    print(f"Removed {removed} off-brand clip(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
