#!/usr/bin/env python3
"""Lint pending and uploaded Shorts metadata for SEO/search hygiene."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.audience_expansion import merge_hashtags, merge_search_tags  # noqa: E402
from utils.seo_optimizer import lint_metadata  # noqa: E402


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _pending_metadata(story: dict) -> dict:
    category = str(story.get("category") or "nature")
    discovery = list(story.get("discovery_hashtags") or [])
    if not discovery:
        topic_tag = str(story.get("topic_hashtag") or category or "nature").lower()
        topic_tag = "".join(ch for ch in topic_tag if ch.isalnum())
        discovery = [category.lower(), topic_tag, "naturefacts", "earthscience", "science"]
    hashtag_block = " ".join(f"#{tag}" for tag in merge_hashtags(discovery))
    body = str(story.get("yt_description") or story.get("description") or story.get("script") or "").strip()
    tags = merge_search_tags([str(tag) for tag in (story.get("yt_tags") or [])], category)
    return {
        **story,
        "description": f"{body}\n\n{hashtag_block}".strip(),
        "tags": tags,
    }


def lint_repo(root: Path = ROOT) -> dict:
    paths = []
    for folder in ("_videos", "_videos_pt-BR"):
        base = root / folder
        if base.exists():
            paths.extend(sorted(base.glob("*.json")))
            paths.extend(sorted(base.glob("*.done")))
    recent_titles: list[str] = []
    items = []
    uploaded_checked = 0
    for path in paths:
        meta = _read_json(path)
        if not meta:
            continue
        lint = lint_metadata(meta, recent_titles=recent_titles)
        recent_titles.append(str(meta.get("title") or ""))
        uploaded_checked += 1
        items.append({"kind": "uploaded", "path": path.relative_to(root).as_posix(), **lint})
    queue = _read_json(root / "_data" / "stories_queue.json")
    pending_checked = 0
    for story in queue.get("stories") or []:
        if not isinstance(story, dict) or story.get("consumed"):
            continue
        meta = _pending_metadata(story)
        lint = lint_metadata(meta, recent_titles=recent_titles)
        recent_titles.append(str(meta.get("title") or ""))
        pending_checked += 1
        story_id = str(story.get("id") or pending_checked)
        items.append({"kind": "pending", "path": f"_data/stories_queue.json#{story_id}", **lint})
    errors = sum(len(item.get("errors") or []) for item in items)
    warnings = sum(len(item.get("warnings") or []) for item in items)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checked": len(items),
        "uploaded_checked": uploaded_checked,
        "pending_checked": pending_checked,
        "errors": errors,
        "warnings": warnings,
        "items": items[:100],
    }
    out = root / "_data" / "seo_metadata_lint.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    payload = lint_repo(Path(args.root).resolve())
    print(f"seo_metadata_lint: {payload['checked']} checked, {payload['errors']} error(s)")
    return 2 if args.strict and payload["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
