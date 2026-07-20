#!/usr/bin/env python3
"""Search Pixabay for b-roll candidates and print them, unfiltered by
looks_anime_styled() -- a human decision aid for picking/auditing a clip,
not a step in the publish pipeline. Prints tags/dims/duration/download URL
for each hit so a candidate can be eyeballed (via its download_url, a
public CDN link needing no API key) before it's ever added to
LOFI_QUERIES or pinned as a fixed clip.

One-off/manual admin tool, same category as scripts/check_live_broadcast_status.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.broll import fetch_pixabay, looks_anime_styled  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "queries",
        help='One or more Pixabay search queries, "|"-delimited (e.g. "anime rain window|anime cozy room")',
    )
    parser.add_argument("--per-query", type=int, default=8)
    args = parser.parse_args()

    results = {}
    for query in (q.strip() for q in args.queries.split("|")):
        if not query:
            continue
        clips = fetch_pixabay(query, per_page=args.per_query)
        results[query] = [
            {
                "id": clip.source_metadata.get("id"),
                "download_url": clip.download_url,
                "width": clip.width,
                "height": clip.height,
                "duration_s": clip.duration_s,
                "tags": clip.source_metadata.get("tags"),
                "page_url": clip.url,
                "anime_style_tag_match": looks_anime_styled(str(clip.source_metadata.get("tags") or "")),
            }
            for clip in clips
        ]
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
