#!/usr/bin/env python3
"""Reply to recent YouTube comments with safe Wild Brief responses."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from utils.comment_replies import build_reply_text, is_replyable_comment

TOKEN_FILE = ROOT / "youtube_token.json"
VIDEOS_DIR = ROOT / "_videos"
LEDGER_FILE = ROOT / "_data" / "comment_replies.json"
COMMENTS_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
FULL_YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube"


def _load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _token_grants(data: dict, *accepted_scopes: str) -> bool:
    granted = set(data.get("scopes") or [])
    return bool(granted.intersection(accepted_scopes))


def _load_service(token_file: Path = TOKEN_FILE):
    data = json.loads(token_file.read_text(encoding="utf-8"))
    if not _token_grants(data, COMMENTS_SCOPE, FULL_YOUTUBE_SCOPE):
        print("reply-comments: token lacks youtube.force-ssl; skipping")
        return None
    creds = Credentials.from_authorized_user_info(data, [COMMENTS_SCOPE])
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def _load_markers(videos_dir: Path = VIDEOS_DIR) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(videos_dir.glob("*.done")):
        item = _load_json(path, {})
        if isinstance(item, dict) and item.get("video_id"):
            rows.append(item)
    return rows


def _channel_id(youtube) -> str:
    response = youtube.channels().list(part="id", mine=True, maxResults=1).execute()
    items = response.get("items") or []
    return str((items[0] if items else {}).get("id") or "")


def _fetch_threads(youtube, video_id: str, per_video: int = 25) -> list[dict]:
    response = youtube.commentThreads().list(
        part="snippet,replies",
        videoId=video_id,
        maxResults=per_video,
        order="time",
        textFormat="plainText",
    ).execute()
    return list(response.get("items") or [])


def _author_id(snippet: dict) -> str:
    return str(((snippet.get("authorChannelId") or {}).get("value") or ""))


def _already_has_channel_reply(thread: dict, channel_id: str) -> bool:
    for reply in (((thread.get("replies") or {}).get("comments") or [])):
        snippet = reply.get("snippet") or {}
        if _author_id(snippet) == channel_id:
            return True
    return False


def _insert_reply(youtube, comment_id: str, text: str) -> str:
    response = youtube.comments().insert(
        part="snippet",
        body={
            "snippet": {
                "parentId": comment_id,
                "textOriginal": text,
            }
        },
    ).execute()
    return str(response.get("id") or "")


def main() -> int:
    if os.environ.get("YOUTUBE_AUTO_REPLY_COMMENTS", "1").lower() in {"0", "false", "no"}:
        print("reply-comments: disabled")
        return 0
    if not TOKEN_FILE.exists():
        print("reply-comments: youtube_token.json missing")
        return 0
    youtube = _load_service()
    if youtube is None:
        return 0

    max_replies = int(os.environ.get("YOUTUBE_COMMENT_REPLY_LIMIT", "30"))
    markers = _load_markers()[-80:]
    ledger = _load_json(LEDGER_FILE, {"replied_comment_ids": [], "replies": []})
    replied_ids = set(str(item) for item in ledger.get("replied_comment_ids", []))
    channel_id = _channel_id(youtube)
    replies_made: list[dict] = []

    for marker in reversed(markers):
        if len(replies_made) >= max_replies:
            break
        video_id = str(marker.get("video_id") or "")
        if not video_id:
            continue
        try:
            threads = _fetch_threads(youtube, video_id)
        except Exception as exc:
            print(f"reply-comments: skipped {video_id}: {exc}")
            continue
        for thread in threads:
            if len(replies_made) >= max_replies:
                break
            top = ((thread.get("snippet") or {}).get("topLevelComment") or {})
            comment_id = str(top.get("id") or "")
            snippet = top.get("snippet") or {}
            text = str(snippet.get("textDisplay") or snippet.get("textOriginal") or "")
            if not comment_id or comment_id in replied_ids:
                continue
            if channel_id and _author_id(snippet) == channel_id:
                continue
            if channel_id and _already_has_channel_reply(thread, channel_id):
                replied_ids.add(comment_id)
                continue
            if not is_replyable_comment(text):
                continue
            reply_text = build_reply_text(text, marker)
            try:
                reply_id = _insert_reply(youtube, comment_id, reply_text)
            except Exception as exc:
                print(f"reply-comments: failed {comment_id}: {exc}")
                continue
            replied_ids.add(comment_id)
            replies_made.append({
                "comment_id": comment_id,
                "reply_id": reply_id,
                "video_id": video_id,
                "reply_text": reply_text,
                "replied_at": datetime.now(timezone.utc).isoformat(),
            })

    ledger["replied_comment_ids"] = sorted(replied_ids)
    ledger["replies"] = list(ledger.get("replies") or []) + replies_made
    ledger["updated_at"] = datetime.now(timezone.utc).isoformat()
    LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_FILE.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"reply-comments: replied to {len(replies_made)} comment(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
