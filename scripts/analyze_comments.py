#!/usr/bin/env python3
"""Refresh audience-comment learning signals for uploaded Shorts."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from utils.comment_intelligence import analyze_comments

TOKEN_FILE = ROOT / "youtube_token.json"
VIDEOS_DIR = ROOT / "_videos"
ANALYTICS_DIR = ROOT / "_data" / "analytics"
OUT_FILE = ANALYTICS_DIR / "comments.json"
READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
FULL_YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube"


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
            rows.append(item)
    return rows


def _token_grants(data: dict, *accepted_scopes: str) -> bool:
    granted = set(data.get("scopes") or [])
    return bool(granted.intersection(accepted_scopes))


def _load_service(token_file: Path = TOKEN_FILE):
    data = json.loads(token_file.read_text(encoding="utf-8"))
    if not _token_grants(data, READONLY_SCOPE, FULL_YOUTUBE_SCOPE):
        print("comments: token lacks youtube.readonly; skipping comment refresh")
        return None
    creds = Credentials.from_authorized_user_info(data, [READONLY_SCOPE])
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def _fetch_comments(youtube, video_ids: list[str], per_video: int = 40) -> list[dict]:
    comments: list[dict] = []
    if youtube is None:
        return comments
    for video_id in video_ids:
        try:
            response = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=per_video,
                order="relevance",
                textFormat="plainText",
            ).execute()
        except Exception as exc:
            print(f"comments: skipped {video_id}: {exc}")
            continue
        for item in response.get("items", []):
            snippet = (
                ((item.get("snippet") or {}).get("topLevelComment") or {})
                .get("snippet") or {}
            )
            comments.append({
                "video_id": video_id,
                "text": snippet.get("textDisplay") or snippet.get("textOriginal") or "",
                "likeCount": snippet.get("likeCount", 0),
                "publishedAt": snippet.get("publishedAt", ""),
            })
    return comments


def build_payload(comments: list[dict]) -> dict:
    summary = analyze_comments(comments)
    summary.update({
        "pulled_at": datetime.now(timezone.utc).isoformat(),
        "source": "youtube_comments",
    })
    return summary


def main() -> int:
    markers = _load_markers()
    if not markers:
        print("comments: no uploaded markers yet")
        return 0
    if not TOKEN_FILE.exists():
        print("comments: youtube_token.json missing; keeping existing comment snapshot")
        return 0
    youtube = _load_service()
    if youtube is None:
        return 0
    comments = _fetch_comments(youtube, [str(m["video_id"]) for m in markers[-60:]])
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(build_payload(comments), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"comments: refreshed {len(comments)} comments")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
