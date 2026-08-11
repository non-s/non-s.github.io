"""Cria e transmite uma live temporaria do Pata Jazz a partir de um video pronto.

Este comando nunca roda por cron. Ele e pensado para um workflow manual apos
o pre-flight confirmar que YouTube Live esta habilitado na conta.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from utils.youtube_retry import retry_youtube_call

log = logging.getLogger(__name__)


def _ingestion_url(stream: dict) -> str:
    info = (stream.get("cdn") or {}).get("ingestionInfo") or {}
    address = str(info.get("ingestionAddress") or "").strip().rstrip("/")
    name = str(info.get("streamName") or "").strip()
    if not address or not name:
        raise RuntimeError("YouTube nao retornou a URL RTMP de ingestao.")
    return f"{address}/{name}"


def create_live(service, *, title: str, privacy: str) -> tuple[str, str]:
    """Create, bind and return (broadcast_id, rtmp_url)."""
    start = (datetime.now(UTC) + timedelta(minutes=2)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    broadcast = retry_youtube_call(
        service.liveBroadcasts()
        .insert(
            part="snippet,status,contentDetails",
            body={
                "snippet": {"title": title, "scheduledStartTime": start},
                "status": {"privacyStatus": privacy},
                "contentDetails": {"enableAutoStart": True, "enableAutoStop": True, "enableDvr": True},
            },
        )
        .execute
    )
    stream = retry_youtube_call(
        service.liveStreams()
        .insert(
            part="snippet,cdn,status",
            body={
                "snippet": {"title": f"{title} stream"},
                "cdn": {"ingestionType": "rtmp", "resolution": "1080p", "frameRate": "30fps"},
            },
        )
        .execute
    )
    broadcast_id = str(broadcast.get("id") or "")
    stream_id = str(stream.get("id") or "")
    if not broadcast_id or not stream_id:
        raise RuntimeError("YouTube nao retornou IDs de broadcast/stream.")
    retry_youtube_call(
        service.liveBroadcasts().bind(part="id,contentDetails", id=broadcast_id, streamId=stream_id).execute
    )
    return broadcast_id, _ingestion_url(stream)


def stream_video(video: Path, rtmp_url: str, duration_minutes: int) -> None:
    if not video.is_file():
        raise FileNotFoundError(f"Video de live nao encontrado: {video}")
    duration_seconds = duration_minutes * 60
    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-re",
        "-stream_loop",
        "-1",
        "-i",
        str(video),
        "-t",
        str(duration_seconds),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-f",
        "flv",
        rtmp_url,
    ]
    subprocess.run(command, check=True, timeout=duration_seconds + 300)


def main() -> int:
    parser = argparse.ArgumentParser(description="Transmitir live temporaria do Pata Jazz.")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--duration-minutes", type=int, default=60)
    parser.add_argument("--privacy", choices=("public", "unlisted", "private"), default="public")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 5 <= args.duration_minutes <= 300:
        parser.error("--duration-minutes deve ficar entre 5 e 300.")
    if args.dry_run:
        log.info("[DRY-RUN] live de %d min com %s (%s)", args.duration_minutes, args.video, args.privacy)
        return 0

    from utils.youtube_oauth import get_youtube_service

    title = "Pata Jazz | Cozy Cat & Dog Jazz Live"
    broadcast_id, rtmp_url = create_live(get_youtube_service(), title=title, privacy=args.privacy)
    try:
        stream_video(args.video, rtmp_url, args.duration_minutes)
    finally:
        try:
            retry_youtube_call(
                get_youtube_service()
                .liveBroadcasts()
                .transition(broadcastStatus="complete", id=broadcast_id, part="status")
                .execute
            )
        except Exception as exc:
            log.warning("Nao foi possivel encerrar a live %s via API: %s", broadcast_id, exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
