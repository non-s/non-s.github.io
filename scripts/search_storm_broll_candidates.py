#!/usr/bin/env python3
"""Search Pixabay for *real* storm/rain b-roll candidates (growth pass,
2026-07-21) -- a human decision aid for picking a real-footage clip to
pin, same category as scripts/search_broll_candidates.py.

Deliberately NOT wired into the runtime pipeline: ADR 0004 (see
docs/adr/0004-pinned-broll-per-format.md) already settled this for the
lofi pillar -- one hand-picked clip beats N auto-selected ones, because
per-video auto-selection let off-brand clips slip through with nothing
checking their actual look. Real-world footage has an even wider range of
what counts as "on brand" than illustrated b-roll did, so the storm
pillar keeps the same discipline: this script surfaces candidates
(tags/dims/duration/download URL) for a human to eyeball via the public
download_url (no API key needed to view it) before one is ever downloaded
and pinned as `_assets/video/pinned_storm_clip.mp4`, replacing the
illustrated scene scripts/generate_storm_scene.py draws by default.

Defaults to `video_type="film"` (real footage); pass `--video-type
animation` for illustrated/cartoon-style candidates instead (chat,
2026-07-22: reused for a one-off cartoon-clip search for a possible new
classical/piano pillar, not just storm/rain -- see
utils.broll.fetch_pixabay's docstring for the film/animation
distinction). The `storm_relevant_tag_match` hint below is storm-specific
regardless of video_type -- ignore it when searching for anything else,
it's advisory only, never a filter.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.broll import (  # noqa: E402
    STORM_RELEVANCE_SIGNALS,
    score_relevance,
    search_pixabay,
)

# Re-export the relevance helper for the JSON hint column. It is the same
# check used by scripts/sync_storm_broll.py and the runtime selection gates
# -- see utils/broll.py's is_on_brand_storm_clip docstring for why that
# second gate matters. In *this* script the hint is purely advisory; a human
# reviews every candidate before anything is pinned by hand.


DEFAULT_QUERIES = (
    "heavy rain window night",
    "thunderstorm lightning night sky",
    "rain city street night",
    "rain on window slow motion",
    "raindrops glass night",
    "dark storm clouds",
    "rain falling trees",
    "night rain balcony",
    "torrential rain street",
    "stormy sea rain",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "queries",
        nargs="?",
        default="|".join(DEFAULT_QUERIES),
        help='One or more Pixabay search queries, "|"-delimited.',
    )
    parser.add_argument("--per-query", type=int, default=8)
    parser.add_argument("--pages", type=int, default=2)
    parser.add_argument(
        "--video-type",
        default="film",
        choices=["film", "animation"],
        help='Pixabay video_type: "film" (real footage) or "animation" (illustrated/cartoon).',
    )
    args = parser.parse_args()

    results = {}
    for query in (q.strip() for q in args.queries.split("|")):
        if not query:
            continue
        clips = search_pixabay(
            [query],
            per_page=args.per_query,
            pages=args.pages,
            video_type=args.video_type,
            signals=STORM_RELEVANCE_SIGNALS,
            min_score=1,
        )
        results[query] = [
            {
                "id": clip.source_metadata.get("pixabay_video_id"),
                "download_url": clip.download_url,
                "width": clip.width,
                "height": clip.height,
                "duration_s": clip.duration_s,
                "tags": clip.source_metadata.get("tags"),
                "page_url": clip.url,
                "photographer": clip.source_metadata.get("photographer"),
                "photographer_url": clip.source_metadata.get("photographer_url"),
                "storm_relevant_tag_match": score_relevance(
                    str(clip.source_metadata.get("tags") or ""), STORM_RELEVANCE_SIGNALS
                ),
            }
            for clip in clips
        ]
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
