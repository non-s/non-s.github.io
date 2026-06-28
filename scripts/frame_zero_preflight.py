#!/usr/bin/env python3
"""Build the pre-render frame-zero opening contract for pending Shorts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.frame_zero_packaging import OPENING_RETENTION_FLOOR, score_frame_zero  # noqa: E402
from utils.opening_retention import score_retention_opening  # noqa: E402
from utils.packaging import package_story  # noqa: E402

QUEUE = Path("_data/stories_queue.json")
OUT = Path("_data/frame_zero_preflight.json")


def _safe_json(path: Path, default: dict) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else default
    except Exception:
        return default


def _story_id(story: dict) -> str:
    return str(story.get("id") or story.get("slug") or story.get("source_clip_id") or story.get("title") or "")


def _opening_line(story: dict) -> str:
    hook = str(story.get("hook") or "").strip()
    if hook:
        return hook
    script = str(story.get("script") or "").strip()
    return script.split(".", 1)[0].strip() + ("." if script else "")


def _render_gate(opening: dict, frame_zero: dict) -> str:
    opening_ready = float(opening.get("score") or 0) >= OPENING_RETENTION_FLOOR and opening.get("approved") is True
    frame_ready = frame_zero.get("approved") is True
    return "approved" if opening_ready and frame_ready else "hold"


def build_report(root: Path = Path("."), *, limit: int = 50) -> dict:
    queue = _safe_json(root / QUEUE, {"stories": []})
    rows: list[dict] = []
    counts: Counter[str] = Counter()
    for story in queue.get("stories") or []:
        if not isinstance(story, dict) or story.get("consumed"):
            continue
        packaged = package_story(story)
        packaging = packaged.get("packaging") or {}
        opening = packaging.get("opening_retention") or score_retention_opening(packaged)
        frame_zero = packaging.get("frame_zero") or score_frame_zero(packaged)
        repair = packaged.get("frame_zero_repair") or {}
        gate = _render_gate(opening, frame_zero)
        counts[gate] += 1
        if repair:
            counts["rewritten"] += 1
        before = repair.get("before") or {}
        after = repair.get("after") or opening
        rows.append(
            {
                "id": _story_id(packaged),
                "title": packaged.get("seo_title") or packaged.get("title") or "",
                "category": packaged.get("category", ""),
                "render_gate": gate,
                "opening_score": float(opening.get("score") or 0),
                "frame_zero_score": float(frame_zero.get("score") or 0),
                "opening_state": opening.get("state", ""),
                "opening_line": _opening_line(packaged),
                "first_frame_text": packaged.get("thumbnail_text", ""),
                "visible_cue": (repair.get("cue") or (packaged.get("curiosity_angle") or {}).get("cue") or ""),
                "rewrite_applied": bool(repair),
                "rewrite_reason": repair.get("reason", ""),
                "before_score": before.get("score"),
                "after_score": after.get("score"),
                "risks": opening.get("risks") or [],
                "action": (
                    "Use the frame-zero rewrite before rendering."
                    if repair
                    else (
                        "Ready to render with current first frame."
                        if gate == "approved"
                        else "Hold until opening is rewritten."
                    )
                ),
            }
        )

    rows.sort(
        key=lambda row: (
            row["render_gate"] == "approved",
            not row["rewrite_applied"],
            float(row["opening_score"]),
            str(row["title"]),
        )
    )
    pending = len(rows)
    ready = counts.get("approved", 0)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "floor": OPENING_RETENTION_FLOOR,
        "pending": pending,
        "ready": ready,
        "held": counts.get("hold", 0),
        "rewritten": counts.get("rewritten", 0),
        "average_opening_score": round(
            sum(float(row["opening_score"]) for row in rows) / max(len(rows), 1),
            2,
        ),
        "render_gate": "approved" if pending and ready == pending else ("empty" if not pending else "hold"),
        "counts": dict(counts),
        "items": rows[:limit],
    }
    out_path = root / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    report = build_report(Path(args.root).resolve(), limit=args.limit)
    print(
        "frame_zero_preflight: "
        f"{report['ready']}/{report['pending']} render-ready, "
        f"{report['rewritten']} rewrite(s), gate={report['render_gate']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
