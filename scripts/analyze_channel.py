#!/usr/bin/env python3
"""Refresh free public performance metrics for uploaded Wild Brief Shorts."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from utils.experiments import compute_winners, write_winners

TOKEN_FILE = ROOT / "youtube_token.json"
VIDEOS_DIR = ROOT / "_videos"
ANALYTICS_DIR = ROOT / "_data" / "analytics"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _load_markers(videos_dir: Path = VIDEOS_DIR) -> list[dict]:
    rows: list[dict] = []
    if not videos_dir.exists():
        return rows
    for path in sorted(videos_dir.glob("*.done")):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(item, dict) and item.get("video_id"):
            item["_marker"] = path.name
            rows.append(item)
    return rows


def _load_service(token_file: Path = TOKEN_FILE):
    data = json.loads(token_file.read_text(encoding="utf-8"))
    creds = Credentials.from_authorized_user_info(data, SCOPES)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def _fetch_statistics(youtube, ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for start in range(0, len(ids), 50):
        response = youtube.videos().list(
            part="statistics,snippet",
            id=",".join(ids[start:start + 50]),
        ).execute()
        for item in response.get("items", []):
            out[str(item.get("id", ""))] = item
    return out


def _engagement_score(stats: dict) -> float:
    views = max(1, int(stats.get("viewCount", 0) or 0))
    likes = int(stats.get("likeCount", 0) or 0)
    comments = int(stats.get("commentCount", 0) or 0)
    return round((likes + comments * 2) * 100 / views, 3)


def build_snapshot(markers: list[dict], statistics: dict[str, dict]) -> tuple[dict, list[dict]]:
    observations: list[dict] = []
    category: dict[str, list[float]] = defaultdict(list)
    series: dict[str, list[float]] = defaultdict(list)
    top: list[dict] = []
    total_views = 0
    for marker in markers:
        video_id = str(marker.get("video_id", ""))
        resource = statistics.get(video_id, {})
        stats = resource.get("statistics") or {}
        views = int(stats.get("viewCount", 0) or 0)
        score = _engagement_score(stats)
        total_views += views
        category[str(marker.get("category") or "unknown")].append(score)
        series[str(marker.get("series") or "Unassigned")].append(score)
        observations.append({
            "video_id": video_id,
            "score": score,
            "experiments": marker.get("experiments") or {},
        })
        top.append({
            "video_id": video_id,
            "title": marker.get("title", ""),
            "views": views,
            "engagement_score": score,
            "share_url": marker.get("url", ""),
        })
    top.sort(key=lambda item: (item["views"], item["engagement_score"]), reverse=True)
    average = lambda values: round(sum(values) / len(values), 3) if values else 0.0
    snapshot = {
        "pulled_at": datetime.now(timezone.utc).isoformat(),
        "metric_scope": "public_video_statistics",
        "total_views": total_views,
        "shorts_tracked": len(markers),
        "avg_engagement_score": average([o["score"] for o in observations]),
        "category_avg_engagement": {k: average(v) for k, v in sorted(category.items())},
        "series_avg_engagement": {k: average(v) for k, v in sorted(series.items())},
        "top_performers": top[:10],
    }
    return snapshot, observations


def main() -> int:
    markers = _load_markers()
    if not markers:
        print("analytics: no uploaded markers yet")
        return 0
    if not TOKEN_FILE.exists():
        print("analytics: youtube_token.json missing; keeping existing snapshots")
        return 0
    try:
        stats = _fetch_statistics(_load_service(), [m["video_id"] for m in markers])
    except Exception as exc:
        print(f"analytics: public-stat refresh skipped: {exc}")
        return 0
    snapshot, observations = build_snapshot(markers, stats)
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    (ANALYTICS_DIR / "latest.json").write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    write_winners(compute_winners(observations), ANALYTICS_DIR / "experiments.json")
    print(f"analytics: refreshed {snapshot['shorts_tracked']} Shorts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
