#!/usr/bin/env python3
"""Build a local remake backlog from analytics candidates."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.editorial_guard import editorial_issues  # noqa: E402
from utils.retention_surgeon import remake_brief

LATEST = ROOT / "_data" / "analytics" / "latest.json"
OUT = ROOT / "_data" / "remake_backlog.json"


def _safe_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _recommendable_title(title: str) -> bool:
    title = str(title or "").strip()
    if not title:
        return False
    return not editorial_issues({"title": title, "seo_title": title}, include_script=False)


def _brief(item: dict) -> dict:
    title = str(item.get("title") or "")
    action = str(item.get("action") or "remake with a sharper hook")
    out = {
        "source_video_id": item.get("video_id", ""),
        "source_title": title,
        "views": int(item.get("views", 0) or 0),
        "retention": float(item.get("retention", item.get("view_pct", 0)) or 0),
        "growth_score": float(item.get("growth_score", 0) or 0),
        "action": action,
        "instructions": [
            "Keep the winning subject promise, but change the first sentence.",
            "Use a different animal or a visibly different angle when possible.",
            "Try another narrative template and narrator variant.",
            "Do not reuse the same source clip.",
        ],
        "candidate_titles": [
            f"{title} - the part viewers missed"[:90],
            f"{title} explained in one detail"[:90],
            f"Why {title[:48]} works"[:90],
        ],
    }
    out.update(
        remake_brief(
            {
                "title": title,
                "hook": item.get("hook", ""),
                "script": item.get("script", title),
                "category": item.get("category", ""),
            }
        )
    )
    return out


def build_backlog(root: Path = ROOT) -> dict:
    latest = _safe_json(root / "_data" / "analytics" / "latest.json")
    candidates = (
        latest.get("remake_candidates")
        or (latest.get("production_recommendations") or {}).get("remake_candidates")
        or []
    )
    if not candidates:
        candidates = []
        for item in latest.get("top_performers") or []:
            if not isinstance(item, dict):
                continue
            views = int(item.get("views", 0) or 0)
            growth = float(item.get("growth_score", 0) or 0)
            retention = float(item.get("view_pct", item.get("average_view_percentage", 0)) or 0)
            postmortem = item.get("postmortem") or {}
            likely = set(postmortem.get("likely_causes") or [])
            if not _recommendable_title(str(item.get("title") or "")):
                continue
            if views >= 250 and (growth >= 120 or retention < 60 or "hook_needs_work" in likely):
                remake = dict(item)
                remake["retention"] = retention
                remake["action"] = "remake the proven topic with a new first sentence and tighter visual promise"
                candidates.append(remake)
    briefs = [
        _brief(item)
        for item in candidates
        if isinstance(item, dict) and _recommendable_title(str(item.get("title") or ""))
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(briefs),
        "remakes": briefs[:20],
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = build_backlog(ROOT)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"remake backlog: {payload['count']} candidate(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
