"""
utils/video_builder.py — lógica comum para construção de vídeos Pata Jazz.

Reúne pipeline compartilhado entre Shorts e vídeos horizontais:
- seleção de assets
- montagem FFmpeg
- validação do arquivo de saída
- escrita de metadados
- geração de thumbnail
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from utils.animal_branding import hook_for_scene, random_scene
from utils.ffmpeg_helpers import get_video_duration, run_ffmpeg
from utils.media_pool import ensure_dirs, pick_audio, pick_videos, pool_stats
from utils.metadata_engine import clean_title, generate_metadata

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class VideoSpec:
    """Especificação de um vídeo a ser gerado."""

    kind: str
    width: int
    height: int
    duration: int
    default_duration: int
    crop_filter: str
    thumbnail_maker: Callable[[str, str, Path], None]
    fallback_description: str


def _build_video_filter(spec: VideoSpec) -> str:
    """Constrói a cadeia de filtros FFmpeg para o aspecto-alvo."""
    w, h = spec.width, spec.height
    return (
        f"{spec.crop_filter},"
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,"
        f"setsar=1/1"
    )


def _prepare_output_paths(stem_prefix: str, output_dir: Path, thumb_dir: Path) -> tuple[Path, Path, str]:
    """Cria diretórios e retorna (video_path, thumb_path, stem)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{stem_prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    return output_dir / f"{stem}.mp4", thumb_dir / f"{stem}.png", stem


def _validate_source_pools() -> None:
    """Garante que há b-roll disponível."""
    stats = pool_stats()
    if stats["videos"] == 0:
        raise RuntimeError("Pool de b-roll vazio. Execute scripts/sync_animal_broll.py primeiro.")
    if stats["audio"] == 0:
        log.warning("Pool de jazz vazio. Vídeo será gerado sem áudio.")


def build_pata_jazz_video(
    spec: VideoSpec,
    output_dir: Path,
    thumb_dir: Path,
    stem_prefix: str,
) -> Path:
    """Pipeline comum de geração de vídeo Pata Jazz.

    Retorna o caminho do vídeo gerado.
    """
    ensure_dirs()
    _validate_source_pools()

    scene = random_scene()
    hook, emoji = hook_for_scene(scene)
    video = random.choice(pick_videos(min_count=1, max_count=1))
    audio_path = pick_audio()

    output, thumb, _ = _prepare_output_paths(stem_prefix, output_dir, thumb_dir)

    inputs = ["-stream_loop", "-1", "-i", str(video)]
    output_args: list[str] = [
        "-map", "0:v:0",
        "-vf", _build_video_filter(spec),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-t", str(spec.duration),
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
    ]
    if audio_path:
        inputs += ["-stream_loop", "-1", "-i", str(audio_path)]
        # Mapeia explicitamente o audio da faixa de jazz (input 1). Sem isso,
        # a selecao automatica do FFmpeg pode escolher o audio embutido no
        # clipe de b-roll (input 0) em vez da musica, deixando o video mudo
        # ou com o som ambiente original do clipe.
        # -shortest removido: com -stream_loop -1 em ambos inputs, -shortest
        # fazia o FFmpeg cortar na duracao do clipe original mais curto (~12s)
        # em vez de respeitar o -t {spec.duration}. O -t ja limita ambos os
        # streams corretamente quando ambos estao em loop infinito.
        output_args += ["-map", "1:a:0", "-c:a", "aac", "-b:a", "192k"]

    run_ffmpeg(inputs + output_args + [str(output)])

    # Passa o video_path para o thumbnail maker usar frame real
    spec.thumbnail_maker(hook, emoji, thumb, video_path=output)

    fallback_title = clean_title(f"{hook} | Pata Jazz")
    metadata = generate_metadata(
        hook=hook,
        scene=scene,
        duration=spec.duration,
        kind=spec.kind,
        emoji=emoji,
        fallback_title=fallback_title,
        fallback_description=spec.fallback_description,
    )
    meta = {
        **metadata,
        "scene": scene,
        "hook": hook,
        "duration": spec.duration,
        "resolution": f"{spec.width}x{spec.height}",
        "video": str(output),
        "thumbnail": str(thumb),
        "audio": str(audio_path) if audio_path else None,
    }
    output.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    from utils.video_validator import validate_generated_video
    validation = validate_generated_video(output, meta["resolution"], spec.duration)
    if not validation.ok:
        raise RuntimeError(f"Vídeo gerado não passou na validação: {'; '.join(validation.errors)}")
    log.info("%s gerado e validado: %s", spec.kind.capitalize(), output)
    return output


def short_spec(duration: int = 35) -> VideoSpec:
    """Especificação padrão para Shorts verticais 1080x1920."""
    from utils.thumbnail_engine import make_short_thumbnail
    return VideoSpec(
        kind="short",
        width=1080,
        height=1920,
        duration=duration,
        default_duration=35,
        crop_filter="crop='ih*9/16:ih:(iw-ih*9/16)/2:0'",
        thumbnail_maker=make_short_thumbnail,
        fallback_description=f"{hook_for_scene(random_scene())[0]} com jazz de fundo. 🐾🎷 #PataJazz",
    )


def horizontal_spec(duration: int = 240) -> VideoSpec:
    """Especificação padrão para vídeos horizontais 1920x1080."""
    from utils.thumbnail_engine import make_horizontal_thumbnail
    return VideoSpec(
        kind="horizontal",
        width=1920,
        height=1080,
        duration=duration,
        default_duration=240,
        crop_filter=(
            "crop='min(iw,ih*16/9):min(ih,iw*9/16):"
            "(iw-min(iw,ih*16/9))/2:(ih-min(ih,iw*9/16))/2'"
        ),
        thumbnail_maker=make_horizontal_thumbnail,
        fallback_description=(
            "Gatinhos e cachorrinhos fofos com jazz suave de fundo. "
            "Curta, relaxe e acompanhe os bichinhos. 🐾🎷 #PataJazz"
        ),
    )


def inspect_video(path: Path) -> dict:
    """Retorna informações básicas de um vídeo via ffprobe.

    Inclui duração, largura, altura, bitrate, codec de vídeo e de áudio.
    """
    import subprocess

    info: dict = {"path": str(path), "duration": get_video_duration(str(path))}
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "stream=codec_name,codec_type,width,height,bit_rate",
                "-of", "json",
                str(path),
            ],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                info["video_codec"] = stream.get("codec_name")
                info["width"] = stream.get("width")
                info["height"] = stream.get("height")
                info["video_bit_rate"] = stream.get("bit_rate")
            elif stream.get("codec_type") == "audio":
                info["audio_codec"] = stream.get("codec_name")
                info["audio_bit_rate"] = stream.get("bit_rate")
    except Exception as exc:
        log.warning("Não foi possível inspecionar %s: %s", path, exc)
    return info
