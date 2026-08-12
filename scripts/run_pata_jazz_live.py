"""Cria e transmite uma live temporaria do Pata Jazz a partir de um video pronto.

Este comando nunca roda por cron. Ele e pensado para um workflow manual apos
o pre-flight confirmar que YouTube Live esta habilitado na conta.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
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
        raise RuntimeError("YouTube nao retornou a URL RTMP de ingestao.")
    return f"{address}/{name}"


def create_live(service, *, title: str, privacy: str, continuous: bool = False) -> tuple[str, str]:
    """Create, bind and return (broadcast_id, rtmp_url)."""
    start = (datetime.now(UTC) + timedelta(minutes=2)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    broadcast = retry_youtube_call(
        service.liveBroadcasts()
        .insert(
            part="snippet,status,contentDetails",
            body={
                "snippet": {"title": title, "scheduledStartTime": start},
                "status": {"privacyStatus": privacy},
                "contentDetails": {
                    "enableAutoStart": True,
                    "enableAutoStop": not continuous,
                    "enableDvr": True,
                },
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


def find_reusable_live(service, *, title: str, privacy: str) -> tuple[str, str] | None:
    """Return an existing matching broadcast and its RTMP URL, when available."""
    response = retry_youtube_call(
        service.liveBroadcasts()
        .list(part="id,snippet,status,contentDetails", mine=True, maxResults=50)
        .execute
    )
    reusable_states = {"created", "ready", "testing", "testStarting", "live", "liveStarting"}
    for broadcast in response.get("items") or []:
        snippet = broadcast.get("snippet") or {}
        status = broadcast.get("status") or {}
        details = broadcast.get("contentDetails") or {}
        if status.get("lifeCycleStatus") not in reusable_states:
            continue
        if snippet.get("title") != title or status.get("privacyStatus") != privacy:
            continue
        broadcast_id = str(broadcast.get("id") or "")
        stream_id = str(details.get("boundStreamId") or "")
        if not broadcast_id or not stream_id:
            continue
        streams = retry_youtube_call(
            service.liveStreams().list(part="id,cdn,status", id=stream_id, maxResults=1).execute
        )
        items = streams.get("items") or []
        if items:
            log.info("Reutilizando a live %s apos reinicio do processo.", broadcast_id)
            return broadcast_id, _ingestion_url(items[0])
    return None


def get_or_create_live(service, *, title: str, privacy: str, continuous: bool) -> tuple[str, str]:
    if continuous:
        reusable = find_reusable_live(service, title=title, privacy=privacy)
        if reusable:
            return reusable
    return create_live(service, title=title, privacy=privacy, continuous=continuous)


def stream_video(
    video: Path,
    rtmp_url: str,
    duration_minutes: int,
    *,
    restart_delay_seconds: int = 15,
    max_restarts: int | None = None,
) -> None:
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
    timeout = None
    if duration_seconds:
        command[command.index("-c:v"):command.index("-c:v")] = ["-t", str(duration_seconds)]
        timeout = duration_seconds + 300
    restarts = 0
    while True:
        try:
            subprocess.run(command, check=True, timeout=timeout)
        except subprocess.CalledProcessError as exc:
            if duration_seconds:
                raise
            log.warning("FFmpeg caiu com codigo %s; reconectando em %ds.", exc.returncode, restart_delay_seconds)
        else:
            if duration_seconds:
                return
            log.warning("FFmpeg encerrou sem erro; reiniciando a transmissao em %ds.", restart_delay_seconds)

        if max_restarts is not None and restarts >= max_restarts:
            return
        restarts += 1
        time.sleep(restart_delay_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Transmitir live temporaria do Pata Jazz.")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=60,
        help="Duracao entre 5 e 300 minutos; use 0 para transmitir ate interrupcao.",
    )
    parser.add_argument("--privacy", choices=("public", "unlisted", "private"), default="public")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.duration_minutes != 0 and not 5 <= args.duration_minutes <= 300:
        parser.error("--duration-minutes deve ser 0 (continua) ou ficar entre 5 e 300.")
    if args.dry_run:
        log.info("[DRY-RUN] live de %d min com %s (%s)", args.duration_minutes, args.video, args.privacy)
        return 0

    from utils.youtube_oauth import get_youtube_service

    title = "Pata Jazz | Cozy Cat & Dog Jazz Live"
    continuous = args.duration_minutes == 0
    service = get_youtube_service()
    broadcast_id, rtmp_url = get_or_create_live(
        service, title=title, privacy=args.privacy, continuous=continuous
    )
    try:
        stream_video(args.video, rtmp_url, args.duration_minutes)
    finally:
        try:
            retry_youtube_call(
                service.liveBroadcasts()
                .transition(broadcastStatus="complete", id=broadcast_id, part="status")
                .execute
            )
        except Exception as exc:
            log.warning("Nao foi possivel encerrar a live %s via API: %s", broadcast_id, exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
