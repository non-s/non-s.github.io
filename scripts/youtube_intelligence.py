#!/usr/bin/env python3
"""Build a broad YouTube API coverage snapshot for Wild Brief."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from googleapiclient.discovery import build

from utils.youtube_intelligence import ANALYTICS_REPORTS, build_payload, default_window, rows_to_dicts
from utils.youtube_oauth import (
    ANALYTICS_MONETARY_SCOPE,
    ANALYTICS_SCOPE,
    READONLY_SCOPE,
    can_read_analytics,
    can_read_youtube,
    credentials_from_token_info,
    load_token_info,
    token_grants,
    token_issue_codes,
    token_status_message,
)

TOKEN_FILE = ROOT / "youtube_token.json"
OUT = ROOT / "_data" / "youtube_intelligence.json"


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _has_observed_snapshot(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    if (payload.get("channel") or {}).get("id"):
        return True
    if int((payload.get("uploads_inventory") or {}).get("uploads_checked", 0) or 0) > 0:
        return True
    if int((payload.get("video_audit") or {}).get("videos_checked", 0) or 0) > 0:
        return True
    return any(
        (item.get("status") == "ok" and int(item.get("rows", 0) or 0) > 0)
        for item in (payload.get("analytics_reports") or [])
        if isinstance(item, dict)
    )


def _load_data_service(info):
    if not can_read_youtube(info.data):
        return None
    return build(
        "youtube", "v3", credentials=credentials_from_token_info(info, [READONLY_SCOPE]), cache_discovery=False
    )


def _load_analytics_service(info):
    if not can_read_analytics(info.data):
        return None
    # The reports.query docs now require youtube.readonly access as well, so
    # include it when the token grants it.
    analytics_scope = ANALYTICS_SCOPE if token_grants(info.data, ANALYTICS_SCOPE) else ANALYTICS_MONETARY_SCOPE
    return build(
        "youtubeAnalytics",
        "v2",
        credentials=credentials_from_token_info(info, [analytics_scope, READONLY_SCOPE]),
        cache_discovery=False,
    )


def _fetch_channel(youtube) -> dict | None:
    if youtube is None:
        return None
    response = (
        youtube.channels()
        .list(
            part="snippet,statistics,contentDetails,status,brandingSettings",
            mine=True,
        )
        .execute()
    )
    items = response.get("items") or []
    return items[0] if items else None


def _fetch_uploads(youtube, playlist_id: str, limit: int = 75) -> list[dict]:
    if youtube is None or not playlist_id:
        return []
    out = []
    page_token = None
    while len(out) < limit:
        response = (
            youtube.playlistItems()
            .list(
                part="snippet,contentDetails,status",
                playlistId=playlist_id,
                maxResults=min(50, limit - len(out)),
                pageToken=page_token,
            )
            .execute()
        )
        for item in response.get("items", []) or []:
            snippet = item.get("snippet") or {}
            content = item.get("contentDetails") or {}
            out.append(
                {
                    "video_id": content.get("videoId", ""),
                    "title": snippet.get("title", ""),
                    "published_at": content.get("videoPublishedAt") or snippet.get("publishedAt", ""),
                    "playlist_item_id": item.get("id", ""),
                }
            )
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return out


def _fetch_videos(youtube, ids: list[str]) -> list[dict]:
    if youtube is None or not ids:
        return []
    out = []
    for start in range(0, len(ids), 50):
        response = (
            youtube.videos()
            .list(
                part="snippet,statistics,status,contentDetails,topicDetails,recordingDetails,localizations",
                id=",".join(ids[start : start + 50]),
            )
            .execute()
        )
        out.extend(response.get("items") or [])
    return out


def _run_report(analytics, spec: dict) -> dict:
    start_date, end_date = default_window()
    try:
        response = (
            analytics.reports()
            .query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics=spec["metrics"],
                dimensions=spec["dimensions"],
                sort=spec.get("sort", ""),
                maxResults=50,
            )
            .execute()
        )
        rows = rows_to_dicts(response)
        return {
            "id": spec["id"],
            "status": "ok",
            "rows": len(rows),
            "sample": rows[:10],
        }
    except Exception as exc:
        return {
            "id": spec["id"],
            "status": "unavailable",
            "rows": 0,
            "error": str(exc)[:240],
        }


def _run_reports(analytics, unavailable_error: str = "yt-analytics.readonly scope missing") -> list[dict]:
    if analytics is None:
        return [
            {"id": spec["id"], "status": "not_authorized", "rows": 0, "error": unavailable_error}
            for spec in ANALYTICS_REPORTS
        ]
    return [_run_report(analytics, spec) for spec in ANALYTICS_REPORTS]


def main() -> int:
    issues = []
    info = load_token_info(TOKEN_FILE)
    if not info.present:
        if _has_observed_snapshot(_safe_json(OUT)):
            print(f"youtube intelligence: {token_status_message(info)}; keeping existing snapshot")
            return 0
        issues.extend(token_issue_codes(info))
        print(f"youtube intelligence: {token_status_message(info)}; writing unauthenticated diagnostic snapshot")
    youtube = _load_data_service(info) if info.present else None
    analytics = _load_analytics_service(info) if info.present else None
    if youtube is None and info.present:
        issues.append("youtube_readonly_scope_missing")
    if analytics is None and info.present:
        issues.append("youtube_analytics_scope_missing")
    channel = None
    uploads = []
    videos = []
    reports = []
    try:
        channel = _fetch_channel(youtube)
        playlist_id = (((channel or {}).get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads", "")
        uploads = _fetch_uploads(youtube, playlist_id)
        videos = _fetch_videos(youtube, [item["video_id"] for item in uploads if item.get("video_id")])
    except Exception as exc:
        issues.append(f"data_api_refresh_failed:{type(exc).__name__}")
    reports = _run_reports(
        analytics,
        "YouTube token missing" if not info.present else "yt-analytics.readonly scope missing",
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            build_payload(channel=channel, uploads=uploads, videos=videos, reports=reports, issues=issues),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"youtube intelligence: {len(uploads)} uploads, {len(videos)} videos, {len(reports)} reports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
