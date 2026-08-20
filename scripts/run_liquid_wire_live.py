"""Create and stream a finite Liquid Wire broadcast from a generated video."""

from __future__ import annotations

import argparse
import logging
import math
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.atomic_state import atomic_write_json
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
                "cdn": {"ingestionType": "rtmp", "resolution": "1080p", "frameRate": "30fps"},
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


def prepare_live_asset(video: Path, output: Path) -> Path:
    """Encode the short loop once to a YouTube-safe, low-CPU delivery asset."""
    if not video.is_file():
        raise FileNotFoundError(video)
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-i", str(video),
            "-c:v", "libx264", "-preset", "fast", "-profile:v", "high", "-level", "4.2",
            "-b:v", "6000k", "-maxrate", "7500k", "-bufsize", "12000k",
            "-g", "60", "-keyint_min", "60", "-sc_threshold", "0", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-movflags", "+faststart",
            str(output),
        ],
        check=True,
        timeout=600,
    )
    if not output.is_file() or output.stat().st_size < 1024:
        raise RuntimeError("FFmpeg did not produce a valid live delivery asset.")
    return output


def stream_video(
    video: Path,
    rtmp_url: str,
    duration_minutes: int,
    *,
    chaos_after_seconds: int = 0,
) -> None:
    if not video.is_file():
        raise FileNotFoundError(video)
    command = [
        "ffmpeg", "-hide_banner", "-nostdin", "-re", "-stream_loop", "-1",
        "-fflags", "+genpts", "-i", str(video), "-t", str(duration_minutes * 60),
        "-c", "copy", "-flvflags", "no_duration_filesize", "-f", "flv", rtmp_url,
    ]
    if chaos_after_seconds:
        process = subprocess.Popen(command)
        try:
            process.wait(timeout=chaos_after_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=30)
            raise subprocess.CalledProcessError(86, command, stderr="intentional chaos disconnect") from None
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, command)
        return
    subprocess.run(command, check=True, timeout=duration_minutes * 60 + 300)


def _write_journal(path: Path | None, payload: dict) -> None:
    if path is not None:
        atomic_write_json(path, payload, backup=False)


def broadcast_resilient(
    service,
    video: Path,
    duration_minutes: int,
    privacy: str,
    max_restarts: int = 10,
    *,
    chaos_after_seconds: int = 0,
    journal_path: Path | None = None,
    preparation_seconds: float | None = None,
) -> list[str]:
    """Reconnect with a fresh broadcast immediately after an RTMP failure."""
    remaining = duration_minutes
    broadcast_ids: list[str] = []
    journal: dict[str, Any] = {
        "schema_version": 1,
        "started_at": datetime.now(UTC).isoformat(),
        "target_minutes": duration_minutes,
        "privacy": privacy,
        "source_preparation_seconds": (
            round(preparation_seconds, 3) if preparation_seconds is not None else None
        ),
        "attempts": [],
        "completed": False,
    }
    _write_journal(journal_path, journal)
    failed_at: float | None = None
    for attempt in range(max_restarts + 1):
        try:
            broadcast_id, rtmp_url = create_live(
                service, title="Liquid Wire Live | Living Generative Forms", privacy=privacy
            )
        except Exception as exc:
            failed_at = failed_at or time.monotonic()
            journal["attempts"].append({
                "attempt": attempt + 1,
                "created_at": datetime.now(UTC).isoformat(),
                "outcome": "creation_failed",
                "error_type": type(exc).__name__,
                "remaining_minutes": remaining,
            })
            _write_journal(journal_path, journal)
            if attempt >= max_restarts:
                raise
            time.sleep(min(30, 2 ** attempt))
            continue
        created_at = time.monotonic()
        broadcast_ids.append(broadcast_id)
        entry = {
            "attempt": attempt + 1,
            "broadcast_id": broadcast_id,
            "created_at": datetime.now(UTC).isoformat(),
            "recovery_latency_seconds": round(created_at - failed_at, 3) if failed_at is not None else None,
            "remaining_minutes": remaining,
            "outcome": "streaming",
        }
        journal["attempts"].append(entry)
        _write_journal(journal_path, journal)
        started = created_at
        failure: (subprocess.CalledProcessError | subprocess.TimeoutExpired) | None = None
        try:
            stream_video(
                video,
                rtmp_url,
                remaining,
                chaos_after_seconds=chaos_after_seconds if attempt == 0 else 0,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            failure = exc
        finally:
            try:
                retry_youtube_call(
                    service.liveBroadcasts().transition(
                        broadcastStatus="complete", id=broadcast_id, part="status"
                    ).execute
                )
            except Exception as exc:
                log.warning("Could not complete broadcast %s: %s", broadcast_id, exc)
        if failure is None:
            entry["outcome"] = "completed"
            entry["streamed_seconds"] = round(time.monotonic() - started, 3)
            journal["completed"] = True
            journal["completed_at"] = datetime.now(UTC).isoformat()
            _write_journal(journal_path, journal)
            return broadcast_ids
        failed_at = time.monotonic()
        elapsed_seconds = failed_at - started
        entry["outcome"] = "disconnected"
        entry["streamed_seconds"] = round(elapsed_seconds, 3)
        entry["error_type"] = type(failure).__name__
        _write_journal(journal_path, journal)
        elapsed_minutes = max(1, math.ceil(elapsed_seconds / 60))
        remaining -= elapsed_minutes
        if attempt >= max_restarts or remaining < 5:
            raise failure
        log.warning(
            "RTMP disconnected after %d minute(s); creating replacement broadcast immediately "
            "(attempt %d/%d, %d minutes remaining).",
            elapsed_minutes, attempt + 1, max_restarts, remaining,
        )
    return broadcast_ids


def main() -> int:
    parser = argparse.ArgumentParser(description="Broadcast Liquid Wire to YouTube Live")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--duration-minutes", type=int, default=10)
    parser.add_argument("--privacy", choices=("public", "unlisted", "private"), default="public")
    parser.add_argument("--max-restarts", type=int, default=10)
    parser.add_argument("--chaos-after-seconds", type=int, default=0)
    args = parser.parse_args()
    if not 5 <= args.duration_minutes <= 330:
        parser.error("--duration-minutes must be between 5 and 330")

    from utils.youtube_oauth import get_youtube_service

    service = get_youtube_service()
    if not 0 <= args.max_restarts <= 10:
        parser.error("--max-restarts must be between 0 and 10")
    if not 0 <= args.chaos_after_seconds <= args.duration_minutes * 60:
        parser.error("--chaos-after-seconds must fit inside the session")
    preparation_started = time.monotonic()
    delivery = prepare_live_asset(args.video, args.video.with_name(f"{args.video.stem}_delivery.mp4"))
    preparation_seconds = time.monotonic() - preparation_started
    journal = ROOT / "_data" / "live_continuity.json"
    broadcast_ids = broadcast_resilient(
        service,
        delivery,
        args.duration_minutes,
        args.privacy,
        args.max_restarts,
        chaos_after_seconds=args.chaos_after_seconds,
        journal_path=journal,
        preparation_seconds=preparation_seconds,
    )
    print(broadcast_ids[-1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
