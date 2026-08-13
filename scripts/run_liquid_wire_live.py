"""Create and stream a finite Liquid Wire broadcast from a generated video."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.youtube_retry import retry_youtube_call

log = logging.getLogger(__name__)


def _ingestion_url(stream: dict) -> str:
    info = (stream.get("cdn") or {}).get("ingestionInfo") or {}
    address = str(info.get("ingestionAddress") or "").strip().rstrip("/")
    name = str(info.get("streamName") or "").strip()
    if not address or not name:
        raise RuntimeError("YouTube did not return an RTMP ingestion URL.")
    return f"{address}/{name}"


def create_live(service, *, title: str, privacy: str) -> tuple[str, str]:
    start = (datetime.now(UTC) + timedelta(minutes=2)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    broadcast = retry_youtube_call(
        service.liveBroadcasts().insert(
            part="snippet,status,contentDetails",
            body={
                "snippet": {
                    "title": title,
                    "description": (
                        "A live Liquid Wire session with original procedural visuals "
                        "and locally synthesized ambient audio. No stock footage."
                    ),
                    "scheduledStartTime": start,
                },
                "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
                "contentDetails": {"enableAutoStart": True, "enableAutoStop": True, "enableDvr": True},
            },
        ).execute
    )
    stream = retry_youtube_call(
        service.liveStreams().insert(
            part="snippet,cdn,status",
            body={
                "snippet": {"title": f"{title} stream"},
                "cdn": {"ingestionType": "rtmp", "resolution": "720p", "frameRate": "30fps"},
            },
        ).execute
    )
    broadcast_id = str(broadcast.get("id") or "")
    stream_id = str(stream.get("id") or "")
    if not broadcast_id or not stream_id:
        raise RuntimeError("YouTube did not return broadcast and stream IDs.")
    retry_youtube_call(
        service.liveBroadcasts().bind(part="id,contentDetails", id=broadcast_id, streamId=stream_id).execute
    )
    return broadcast_id, _ingestion_url(stream)


def stream_video(video: Path, rtmp_url: str, duration_minutes: int) -> None:
    if not video.is_file():
        raise FileNotFoundError(video)
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostdin", "-re", "-stream_loop", "-1", "-i", str(video),
            "-t", str(duration_minutes * 60), "-c:v", "libx264", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-f", "flv", rtmp_url,
        ],
        check=True,
        timeout=duration_minutes * 60 + 300,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Broadcast Liquid Wire to YouTube Live")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--duration-minutes", type=int, default=10)
    parser.add_argument("--privacy", choices=("public", "unlisted", "private"), default="public")
    args = parser.parse_args()
    if not 5 <= args.duration_minutes <= 330:
        parser.error("--duration-minutes must be between 5 and 330")

    from utils.youtube_oauth import get_youtube_service

    service = get_youtube_service()
    broadcast_id, rtmp_url = create_live(
        service,
        title="Liquid Wire Live | Living Generative Forms",
        privacy=args.privacy,
    )
    try:
        stream_video(args.video, rtmp_url, args.duration_minutes)
    finally:
        try:
            retry_youtube_call(
                service.liveBroadcasts().transition(
                    broadcastStatus="complete", id=broadcast_id, part="status"
                ).execute
            )
        except Exception as exc:
            log.warning("Could not complete broadcast %s: %s", broadcast_id, exc)
    print(broadcast_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
