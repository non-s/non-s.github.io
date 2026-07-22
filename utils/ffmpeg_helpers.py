"""
utils/ffmpeg_helpers.py — wrappers seguros para chamadas FFmpeg.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)


def has_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def run_ffmpeg(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    cmd = ["ffmpeg", "-y"] + args
    log.info("Executando ffmpeg: %s", " ".join(cmd))
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("errors", "replace")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        log.error("FFmpeg falhou: %s", result.stderr[-2000:] if result.stderr else "")
        raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)
    return result


def build_concat_demuxer(paths: Iterable[str], output_txt: str) -> None:
    with open(output_txt, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(f"file '{Path(p).resolve().as_posix()}'\n")


def get_video_duration(path: str) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0
