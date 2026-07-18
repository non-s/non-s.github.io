#!/usr/bin/env python3
"""One-time rebrand of the 20 already-published lofi titles to the "hook first,
channel name last" formula (e.g. "Rainy Night Anime Lofi -- Amber Hours").

The old titles ("Chill Beats to Unwind", "Study & Relax") were interchangeable
with every other lofi channel's SEO vocabulary, which is unwinnable head-term
territory for a small channel. This list was drafted and approved with the
channel owner in chat on 2026-07-18 as the first step of a rainy-night/cozy
anime sub-niche pivot -- it is not derivable from the code, hence the fixed
map instead of a generated rule.

Only the title changes; description/tags/category are read back from the
local .done marker and resent unmodified, because videos.update requires the
full snippet resource or it silently wipes the fields you don't include.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upload_youtube import _normalise_tags, get_youtube_service  # noqa: E402

VIDEOS_DIR = Path("_videos")

NEW_TITLES: dict[str, str] = {
    "ErjYI1RELFU": "Late Night Study Anime Lofi — Amber Hours 🕯️",
    "em26a-SM9xw": "Ocean Waves at Night — Calming Lofi — Amber Hours 🌊",
    "8h5OsCzD954": "Cozy Anime Lofi — Amber Hours 🌙",
    "on6UxqQyBj4": "Anime Lofi After Hours — Amber Hours 🌙",
    "QO-lcCEaWgM": "Cozy Bedroom Anime Lofi — Amber Hours 🌙",
    "znGCGdlCveY": "Midnight City Anime Lofi — Amber Hours 🌃",
    "Spr9pearb2E": "Quiet Anime Nights Lofi — Amber Hours 🌙",
    "OkVCQ9R66do": "Sleepy Cat Anime Lofi — Amber Hours 🐾",
    "Xi2cWR1DhYc": "Cat Nap Anime Lofi — Amber Hours 🐾",
    "Ck7hf9ELE6g": "Midnight Cat Lofi — Amber Hours 🐾",
    "aCoO3WXAurs": "Rainy Night Anime Lofi — Amber Hours 🌧️",
    "FX2p3eMfASM": "Snowy Night Anime Lofi — Amber Hours 🌨️",
    "oSREV1Tfouk": "Plant-Filled Room Anime Lofi — Amber Hours 🌙",
    "6FkdfO3XZsU": "Cozy Cat Corner Anime Lofi — Amber Hours 🐾",
    "RNgqhxTZAb4": "Late Night Library Lofi — Amber Hours 📚",
    "guDtN8g-xCA": "Purring Through the Night — Amber Hours 🐾",
    "IKvEOESS8i8": "City Lights at Night — Amber Hours 🌃",
    "3Y-rn3CraqY": "Snowfall Anime Lofi — Amber Hours 🌨️",
    "SkqC0A42z1I": "Rain on the Window Anime Lofi — Amber Hours 🌧️",
    "dhFjT3Qw8uw": "Sleepy Cat Anime Lofi (1 Hour) — Amber Hours 🐾",
}


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _marker_for_video_id(video_id: str, videos_dir: Path) -> Path | None:
    for path in sorted(videos_dir.glob("*.done")):
        if str(_read_json(path).get("video_id") or "") == video_id:
            return path
    return None


def build_plan(videos_dir: Path = VIDEOS_DIR) -> list[dict]:
    plans: list[dict] = []
    for video_id, new_title in NEW_TITLES.items():
        path = _marker_for_video_id(video_id, videos_dir)
        if not path:
            plans.append({"video_id": video_id, "after_title": new_title, "error": "marker_not_found"})
            continue
        marker = _read_json(path)
        before_title = str(marker.get("title") or "")
        if before_title == new_title:
            continue
        plans.append(
            {
                "marker": str(path),
                "video_id": video_id,
                "before_title": before_title,
                "after_title": new_title,
                "description": str(marker.get("description") or ""),
                "tags": _normalise_tags(marker.get("tags") or []),
                "category_id": str(marker.get("youtube_category_id") or "15"),
            }
        )
    return plans


def apply_plan(youtube, plan: dict) -> dict:
    snippet = {
        "title": plan["after_title"],
        "description": plan["description"],
        "tags": plan["tags"],
        "categoryId": plan["category_id"],
    }
    response = youtube.videos().update(part="snippet", body={"id": plan["video_id"], "snippet": snippet}).execute()
    return response if isinstance(response, dict) else {}


def write_marker_rebrand(plan: dict, response: dict) -> None:
    path = Path(plan["marker"])
    marker = _read_json(path)
    if not marker:
        return
    marker["title"] = plan["after_title"]
    marker["title_rebrand"] = {
        "before_title": plan["before_title"],
        "after_title": plan["after_title"],
        "video_id": plan["video_id"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "youtube_response_id": str(response.get("id") or ""),
        "reason": "subniche_rebrand_2026-07-18",
    }
    path.write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--videos-dir", default=str(VIDEOS_DIR))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    videos_dir = Path(args.videos_dir)
    plans = build_plan(videos_dir)
    runnable = [p for p in plans if not p.get("error")]
    applied: list[dict] = []

    if args.apply and runnable:
        youtube = get_youtube_service()
        for plan in runnable:
            response = apply_plan(youtube, plan)
            write_marker_rebrand(plan, response)
            applied.append({"video_id": plan["video_id"], "after_title": plan["after_title"]})

    payload = {"planned": len(runnable), "applied": len(applied), "plans": plans}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for plan in plans:
            if plan.get("error"):
                print(f"{plan['video_id']}: ERROR {plan['error']}")
            else:
                print(f"{plan['video_id']}: {plan['before_title']!r} -> {plan['after_title']!r}")
        print(f"planned={len(runnable)} applied={len(applied)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
