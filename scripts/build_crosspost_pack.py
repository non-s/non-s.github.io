#!/usr/bin/env python3
"""Build operator-ready crosspost copy packs from uploaded Short markers."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.editorial_guard import editorial_issues  # noqa: E402
from utils.video_markers import sorted_done_markers  # noqa: E402


def _recommendable_title(title: str) -> bool:
    title = str(title or "").strip()
    if not title:
        return False
    return not editorial_issues({"title": title, "seo_title": title}, include_script=False)


def build_pack(root: Path = ROOT, limit: int = 10) -> dict:
    items = []
    for _, marker in sorted_done_markers(root, ("_videos", "_videos_pt-BR"), newest_first=True):
        title = str(marker.get("title") or "Wild Brief")
        if not _recommendable_title(title):
            continue
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
