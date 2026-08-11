"""Public, high-level competitive research for editorial inspiration.

This module analyses public metadata through the official YouTube API. It is
deliberately restricted to patterns and never produces content to copy.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from utils.paths import data_dir
from utils.state_lock import state_lock
from utils.youtube_retry import retry_youtube_call

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config" / "benchmark_channels.json"


def _output_file() -> Path:
    return data_dir() / "competitive_intelligence.json"


def load_benchmark_channels() -> list[dict[str, str]]:
    """Load a transparent, user-editable panel of public reference channels."""
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        channels = data.get("channels", []) if isinstance(data, dict) else []
        return [
            {"id": str(channel["id"]), "label": str(channel.get("label", channel["id"]))}
            for channel in channels
            if isinstance(channel, dict) and channel.get("id")
        ]
    except (OSError, json.JSONDecodeError, KeyError):
        return []


def collect_competitive_intelligence(service, max_videos: int = 6) -> dict:
    """Collect current public metadata from the configured reference panel."""
    panel = load_benchmark_channels()
    if not panel:
        return {"generated_at": datetime.now(UTC).isoformat(), "channels": []}
    channel_ids = ",".join(item["id"] for item in panel)
    request = service.channels().list(part="snippet,statistics,contentDetails", id=channel_ids)
    response = retry_youtube_call(request.execute)
    labels = {item["id"]: item["label"] for item in panel}
    channels: list[dict] = []
    for item in response.get("items", []):
        uploads = (item.get("contentDetails") or {}).get("relatedPlaylists", {}).get("uploads")
        recent: list[dict[str, str]] = []
        if uploads:
            videos = retry_youtube_call(
                service.playlistItems()
                .list(part="snippet,contentDetails", playlistId=uploads, maxResults=max_videos)
                .execute
            )
            for video in videos.get("items", []):
                snippet = video.get("snippet") or {}
                recent.append(
                    {
                        "title": str(snippet.get("title", ""))[:160],
                        "published_at": str(snippet.get("publishedAt", "")),
                        "video_id": str((video.get("contentDetails") or {}).get("videoId", "")),
                    }
                )
        stats = item.get("statistics") or {}
        channels.append(
            {
                "channel_id": str(item.get("id", "")),
                "label": labels.get(str(item.get("id", "")), str((item.get("snippet") or {}).get("title", ""))),
                "title": str((item.get("snippet") or {}).get("title", "")),
                "subscriber_count": str(stats.get("subscriberCount", "")),
                "video_count": str(stats.get("videoCount", "")),
                "recent_videos": recent,
            }
        )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "method": "public metadata only; no copying permitted",
        "channels": channels,
    }


def save_competitive_intelligence(report: dict) -> None:
    path = _output_file()
    with state_lock(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
