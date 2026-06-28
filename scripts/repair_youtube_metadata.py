#!/usr/bin/env python3
"""Repair already-published YouTube metadata when local markers prove a bad title."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upload_youtube import (  # noqa: E402
    _apply_unique_upload_title,
    _detail_conflicts_with_category,
    _existing_upload_titles,
    _normalise_tags,
    _title_key,
    _youtube_description,
    _youtube_title,
    get_youtube_service,
)


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def marker_paths(videos_dir: Path) -> list[Path]:
    return sorted(Path(videos_dir).glob("*.done"))


def needs_semantic_title_repair(marker: dict) -> bool:
    dedupe = marker.get("upload_title_dedupe") or {}
    if not isinstance(dedupe, dict) or not dedupe.get("applied"):
        return False
    title = str(dedupe.get("after") or marker.get("title") or "")
    category = str(marker.get("category") or "")
    return bool(title and category and _detail_conflicts_with_category(title, category))


def repair_plan(marker: dict, marker_path: Path, existing_titles: set[str]) -> dict:
    if not needs_semantic_title_repair(marker):
        return {}
    video_id = str(marker.get("video_id") or "").strip()
    dedupe = marker.get("upload_title_dedupe") or {}
    original_title = str(dedupe.get("before") or "").strip()
    current_title = str(marker.get("title") or dedupe.get("after") or "").strip()
    if not video_id or not original_title or not current_title:
        return {}

    meta = dict(marker)
    meta["title"] = original_title
    description = str(marker.get("description") or "")
    if description and description.startswith(current_title):
        meta["description"] = original_title + description[len(current_title) :]

    safe_existing = set(existing_titles)
    safe_existing.discard(_title_key(current_title))
    _apply_unique_upload_title(meta, safe_existing)

    repaired_title = _youtube_title(meta)
    if not repaired_title or _title_key(repaired_title) == _title_key(current_title):
        return {}
    if _detail_conflicts_with_category(repaired_title, str(marker.get("category") or "")):
        return {}

    return {
        "marker": str(marker_path),
        "video_id": video_id,
        "before_title": current_title,
        "after_title": repaired_title,
        "before_description": description,
        "after_description": _youtube_description(meta),
        "tags": _normalise_tags(marker.get("tags") or meta.get("tags") or []),
        "category_id": str(marker.get("youtube_category_id") or "15"),
        "reason": "semantic_title_conflict_after_dedupe",
    }


def collect_repair_plans(videos_dir: Path, *, video_ids: set[str] | None = None) -> list[dict]:
    existing_titles = _existing_upload_titles(videos_dir)
    plans: list[dict] = []
    for path in marker_paths(videos_dir):
        marker = _read_json(path)
        if video_ids and str(marker.get("video_id") or "") not in video_ids:
            continue
        plan = repair_plan(marker, path, existing_titles)
        if plan:
            plans.append(plan)
    return plans


def update_youtube_metadata(youtube, plan: dict) -> dict:
    snippet = {
        "title": plan["after_title"],
        "description": plan["after_description"],
        "tags": plan.get("tags") or [],
        "categoryId": plan.get("category_id") or "15",
    }
    request = youtube.videos().update(
        part="snippet",
        body={"id": plan["video_id"], "snippet": snippet},
    )
    response = request.execute()
    return response if isinstance(response, dict) else {}


def write_marker_repair(plan: dict, *, applied: bool, response: dict | None = None) -> None:
    path = Path(plan["marker"])
    marker = _read_json(path)
    if not marker:
        return
    marker["title"] = plan["after_title"]
    marker["description"] = plan["after_description"]
    marker["metadata_repair"] = {
        "applied": applied,
        "reason": plan["reason"],
        "before_title": plan["before_title"],
        "after_title": plan["after_title"],
        "video_id": plan["video_id"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "youtube_response_id": str((response or {}).get("id") or ""),
    }
    path.write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--videos-dir", default="_videos")
    parser.add_argument("--video-id", action="append", default=[])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    videos_dir = Path(args.videos_dir)
    plans = collect_repair_plans(videos_dir, video_ids=set(args.video_id or []) or None)
    applied: list[dict] = []
    if args.apply and plans:
        youtube = get_youtube_service()
        for plan in plans:
            response = update_youtube_metadata(youtube, plan)
            write_marker_repair(plan, applied=True, response=response)
            applied.append(
                {
                    "video_id": plan["video_id"],
                    "before_title": plan["before_title"],
                    "after_title": plan["after_title"],
                    "marker": plan["marker"],
                }
            )

    payload = {
        "apply": bool(args.apply),
        "planned": len(plans),
        "applied": applied,
        "plans": plans,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(f"metadata repair plans: {len(plans)}")
        for plan in plans:
            action = "updated" if args.apply else "would update"
            print(f"- {action} {plan['video_id']}: {plan['before_title']} -> {plan['after_title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
