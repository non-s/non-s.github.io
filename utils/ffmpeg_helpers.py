"""
utils/ffmpeg_helpers.py — wrappers seguros para chamadas FFmpeg.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Iterable
from pathlib import Path

log = logging.getLogger(__name__)


def _has_binary(name: str) -> bool:
    try:
        subprocess.run([name, "-version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def has_ffmpeg() -> bool:
    return _has_binary("ffmpeg")


def has_ffprobe() -> bool:
    return _has_binary("ffprobe")


def run_ffmpeg(args: list[str], timeout: int | None = None, **kwargs) -> subprocess.CompletedProcess:
    """Executa ffmpeg com tratamento de erros.

    Args:
        args: argumentos do FFmpeg (sem o binario ``ffmpeg``).
        timeout: tempo maximo em segundos. None = sem timeout (mantem
            comportamento legado para compatibilidade). Use um valor
            razoavel para evitar que um FFmpeg travado (esperando input
            ou em deadlock de pipe) prenda o pipeline indefinidamente.
    """
    cmd = ["ffmpeg", "-y"] + args
    log.info("Executando ffmpeg: %s", " ".join(cmd))
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("errors", "replace")
    try:
        result = subprocess.run(cmd, timeout=timeout, **kwargs)
    except subprocess.TimeoutExpired as exc:
        log.error("FFmpeg excedeu timeout de %ss: %s", timeout, exc)
        raise
    if result.returncode != 0:
        log.error("FFmpeg falhou: %s", result.stderr[-2000:] if result.stderr else "")
        raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)
    return result


def build_concat_demuxer(paths: Iterable[str], output_txt: str) -> None:
    with open(output_txt, "w", encoding="utf-8") as f:
        for p in paths:
            safe = Path(p).resolve().as_posix().replace("'", r"\'")
            f.write(f"file '{safe}'\n")


def get_video_duration(path: str) -> float:
    """Retorna a duracao do video em segundos, ou 0.0 se impossivel determinar.

    Retorna 0.0 (e nao None ou excecao) para manter compatibilidade com
    callers existentes que somam duracoes. Callers que precisam distinguir
    "falha" de "duracao zero legitima" devem tratar 0.0 como suspeito.
    """
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
            timeout=15,
        )
        if result.returncode != 0:
            return 0.0
        val = float(result.stdout.strip())
        return val if val > 0 else 0.0
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return 0.0
