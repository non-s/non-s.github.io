"""
utils/video_validator.py — validação de qualidade de vídeos gerados.

Garante que o arquivo de saída atende aos requisitos técnicos do YouTube:
- resolução exata
- duração dentro da tolerância
- codec H.264 + AAC
- presença de áudio quando esperado
- bitrate mínimo
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils.ffmpeg_helpers import get_video_duration

log = logging.getLogger(__name__)

TOLERANCE_SECONDS = 1.0


@dataclass(frozen=True)
class VideoValidation:
    """Resultado de uma validação de vídeo."""

    ok: bool
    errors: list[str]
    info: dict[str, Any]


def _run_ffprobe(path: Path) -> dict:
    """Retorna o JSON do ffprobe com os streams do arquivo."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "stream=codec_type,codec_name,width,height,bit_rate,duration",
                "-of", "json",
                str(path),
            ],
            capture_output=True, text=True, check=True,
        )
        return json.loads(result.stdout)
    except Exception as exc:
        raise RuntimeError(f"ffprobe falhou para {path}: {exc}")


def _extract_stream_info(probe: dict) -> dict[str, Any]:
    """Extrai informações relevantes dos streams de vídeo e áudio."""
    info: dict[str, Any] = {"has_video": False, "has_audio": False}
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            info["has_video"] = True
            info["video_codec"] = stream.get("codec_name")
            info["width"] = stream.get("width")
            info["height"] = stream.get("height")
            info["video_bit_rate"] = _to_int(stream.get("bit_rate"))
        elif stream.get("codec_type") == "audio":
            info["has_audio"] = True
            info["audio_codec"] = stream.get("codec_name")
            info["audio_bit_rate"] = _to_int(stream.get("bit_rate"))
    return info


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def validate_video(
    path: Path,
    expected_width: int,
    expected_height: int,
    expected_duration: float,
    expect_audio: bool = True,
    min_video_bitrate_kbps: int = 100,
) -> VideoValidation:
    """Valida um vídeo contra especificações técnicas.

    Args:
        path: caminho do arquivo de vídeo.
        expected_width: largura esperada em pixels.
        expected_height: altura esperada em pixels.
        expected_duration: duração esperada em segundos (com tolerância).
        expect_audio: se True, exige stream de áudio.
        min_video_bitrate_kbps: bitrate mínimo de vídeo em kbps.
    """
    errors: list[str] = []
    if not path.exists():
        return VideoValidation(ok=False, errors=[f"Arquivo não encontrado: {path}"], info={})

    try:
        probe = _run_ffprobe(path)
        info = _extract_stream_info(probe)
    except Exception as exc:
        return VideoValidation(ok=False, errors=[str(exc)], info={"path": str(path)})

    duration = get_video_duration(str(path))
    info["duration"] = duration

    if not info.get("has_video"):
        errors.append("Stream de vídeo ausente.")
    else:
        if info.get("video_codec") != "h264":
            errors.append(f"Codec de vídeo inesperado: {info.get('video_codec')} (esperado h264).")
        if info.get("width") != expected_width or info.get("height") != expected_height:
            errors.append(
                f"Resolução inesperada: {info.get('width')}x{info.get('height')} "
                f"(esperado {expected_width}x{expected_height})."
            )
        video_br = info.get("video_bit_rate")
        if video_br is not None and video_br < min_video_bitrate_kbps * 1000:
            errors.append(f"Bitrate de vídeo muito baixo: {video_br // 1000} kbps.")

    if expect_audio and not info.get("has_audio"):
        errors.append("Stream de áudio ausente.")
    if info.get("has_audio") and info.get("audio_codec") != "aac":
        errors.append(f"Codec de áudio inesperado: {info.get('audio_codec')} (esperado aac).")

    if duration == 0:
        errors.append("Não foi possível determinar a duração do vídeo.")
    elif abs(duration - expected_duration) > TOLERANCE_SECONDS:
        errors.append(f"Duração fora da tolerância: {duration:.2f}s (esperado ~{expected_duration}s).")

    ok = len(errors) == 0
    if not ok:
        log.error("Validação falhou para %s: %s", path, "; ".join(errors))
    else:
        log.info("Vídeo validado: %s (%sx%s, %.2fs)", path, info.get("width"), info.get("height"), duration)

    return VideoValidation(ok=ok, errors=errors, info=info)


def validate_generated_video(path: Path, expected_resolution: str, expected_duration: int) -> VideoValidation:
    """Valida um vídeo gerado pelo Pata Jazz a partir da string de resolução."""
    try:
        w, h = (int(x) for x in expected_resolution.split("x"))
    except ValueError:
        return VideoValidation(
            ok=False,
            errors=[f"Resolução esperada inválida: {expected_resolution}"],
            info={},
        )
    return validate_video(path, expected_width=w, expected_height=h, expected_duration=expected_duration)
