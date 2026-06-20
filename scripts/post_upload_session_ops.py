#!/usr/bin/env python3
"""Generate operator-assist recommendations for post-upload session growth."""

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
from utils.session_graph import build_session_graph  # noqa: E402
from utils.video_markers import sorted_done_markers  # noqa: E402


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _done_markers(root: Path) -> list[dict]:
    return [marker for _, marker in sorted_done_markers(root)]


def _score_related(source: dict, candidate: dict) -> float:
    score = 0.0
    if source.get("category") and source.get("category") == candidate.get("category"):
        score += 35
    if source.get("series") and source.get("series") == candidate.get("series"):
        score += 30
    if source.get("story_format") and source.get("story_format") == candidate.get("story_format"):
        score += 20
    score += min(15, float(candidate.get("views") or 0) / 200)
    return round(score, 2)


def _recommendable_title(title: str) -> bool:
    title = str(title or "").strip()
    if not title:
        return False
    return not editorial_issues({"title": title, "seo_title": title}, include_script=False)


def _has_recommendable_or_empty_title(item: dict) -> bool:
    title = str(item.get("title") or "").strip()
    return not title or _recommendable_title(title)


def build_session_ops(root: Path = ROOT) -> dict:
    data_dir = root / "_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    markers = _done_markers(root)
    graph = build_session_graph(markers)
    recommendable_markers = [item for item in markers if _has_recommendable_or_empty_title(item)]
    latest = recommendable_markers[-5:]
    related = []
    for source in latest:
        if source.get("title") and not _recommendable_title(str(source.get("title") or "")):
            continue
        candidates = [
            {
                "video_id": item.get("video_id"),
                "title": item.get("title"),
                "url": item.get("url") or f"https://www.youtube.com/shorts/{item.get('video_id')}",
                "score": _score_related(source, item),
                "reason": "same series/category/format session bridge",
            }
            for item in recommendable_markers
            if item.get("video_id") and item.get("video_id") != source.get("video_id")
        ]
        candidates.sort(key=lambda row: row["score"], reverse=True)
        if candidates:
            related.append(
                {
                    "source_video_id": source.get("video_id"),
                    "source_title": source.get("title"),
                    "recommendation": candidates[0],
                }
            )
    comments = _read_json(root / "_data" / "analytics" / "comments.json", {})
    comment_candidates = []
    for item in comments.get("top_comments") or comments.get("comments") or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("comment") or "")
        if "?" in text or len(text.split()) >= 6:
            comment_candidates.append(
                {
                    "comment": text[:240],
                    "video_id": item.get("video_id", ""),
                    "short_prompt": f"Answer this viewer question with one visible nature example: {text[:120]}",
                }
            )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "related_video_recommendations": related[:20],
        "playlist_sequence_notes": [
            "Place each new Short after the closest same-series winner.",
            "Use related video manually in Studio when official automation is unavailable.",
        ],
        "comment_reply_short_candidates": comment_candidates[:20],
        "sequel_opportunities": [
            {
                "video_id": item.get("video_id"),
                "title": item.get("title"),
                "prompt": f"Make a sequel with a new subject but the same payoff shape: {item.get('title')}",
            }
            for item in latest
            if _recommendable_title(str(item.get("title") or ""))
        ],
        "session_graph": {
            "nodes": len(graph.get("nodes") or []),
            "edges": len(graph.get("edges") or []),
            "coverage": graph.get("coverage", 0),
            "action_score_threshold": graph.get("action_score_threshold", 0),
            "target_reuse_limit": graph.get("target_reuse_limit", 0),
        },
    }
    (data_dir / "post_upload_session_ops.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (data_dir / "related_video_recommendations.json").write_text(
        json.dumps(
            {"generated_at": payload["generated_at"], "items": related[:20]},
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (data_dir / "comment_reply_short_candidates.json").write_text(
        json.dumps(
            {"generated_at": payload["generated_at"], "items": comment_candidates[:20]},
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (data_dir / "session_graph.json").write_text(
        json.dumps(
            {
                "generated_at": payload["generated_at"],
                "nodes": graph.get("nodes") or [],
                "edges": graph.get("edges") or [],
                "coverage": graph.get("coverage", 0),
                "action_score_threshold": graph.get("action_score_threshold", 0),
                "target_reuse_limit": graph.get("target_reuse_limit", 0),
            },
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (data_dir / "next_session_actions.json").write_text(
        json.dumps(
            {
                "generated_at": payload["generated_at"],
                "items": graph.get("next_session_actions") or [],
                "action_score_threshold": graph.get("action_score_threshold", 0),
                "target_reuse_limit": graph.get("target_reuse_limit", 0),
            },
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (data_dir / "sequel_candidates.json").write_text(
        json.dumps(
            {"generated_at": payload["generated_at"], "items": graph.get("sequel_candidates") or []},
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    payload = build_session_ops(Path(args.root).resolve())
    print(
        "post_upload_session_ops: "
        f"{len(payload['related_video_recommendations'])} related, "
        f"{len(payload['comment_reply_short_candidates'])} comment candidates"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
