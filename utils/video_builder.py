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
    scene: str = ""
    mood: str = ""


def _build_video_filter(spec: VideoSpec) -> str:
    """Constrói a cadeia de filtros FFmpeg para o aspecto-alvo."""
    w, h = spec.width, spec.height
    return (
        f"{spec.crop_filter},"
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,"
        f"setsar=1/1"
    )


def _build_overlay_filter(hook: str, width: int, height: int) -> str:
    """Constrói filtro drawtext para mostrar o hook nos primeiros 3 segundos.

    Texto branco com sombra preta na parte inferior do video.
    Fade in/out suave para nao aparecer/desaparecer abruptamente.
    """
    safe_hook = hook.replace("'", r"\'").replace(":", r"\:").replace("\\", r"\\")
    font_size = 48 if width > height else 56  # Shorts fonte maior
    y_pos = height - 200 if width > height else height - 350
    return (
        f"drawtext=text='{safe_hook}'"
        f":fontsize={font_size}"
        f":fontcolor=white"
        f":shadowcolor=black:shadowx=2:shadowy=2"
        f":x=(w-text_w)/2:y={y_pos}"
        f":enable='between(t,0,3)'"
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


def _build_single_clip_video(
    spec: VideoSpec,
    video: Path,
    audio_path: Path | None,
    output: Path,
    hook: str = "",
) -> None:
    """Gera um video com 1 clipe em loop + musica de jazz + overlay de texto."""
    inputs = ["-stream_loop", "-1", "-i", str(video)]
    vf = _build_video_filter(spec)
    if hook:
        vf = f"{vf},{_build_overlay_filter(hook, spec.width, spec.height)}"
    output_args: list[str] = [
        "-map", "0:v:0",
        "-vf", vf,
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
        output_args += ["-map", "1:a:0", "-c:a", "aac", "-b:a", "192k"]
    run_ffmpeg(inputs + output_args + [str(output)])


def _build_multi_clip_short(
    spec: VideoSpec,
    videos: list[Path],
    audio_path: Path | None,
    output: Path,
    hook: str = "",
) -> None:
    """Gera um Short com 2-3 clipes e transicoes crossfade.

    Cada clipe e normalizado para o aspecto-alvo e concatenado com xfade.
    A musica de jazz toda por toda a duracao total.
    """
    import random as _rng

    n_clips = min(len(videos), _rng.randint(2, 3))
    selected = _rng.sample(videos, n_clips)
    per_clip = spec.duration // n_clips

    # Normaliza cada clipe individualmente
    processed: list[Path] = []
    for i, v in enumerate(selected):
        proc = output.parent / f"{output.stem}_clip_{i}.mp4"
        run_ffmpeg([
            "-i", str(v),
            "-vf", _build_video_filter(spec),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-t", str(per_clip), "-r", "30",
            "-pix_fmt", "yuv420p", "-an",
            str(proc),
        ])
        processed.append(proc)

    # Monta filter complex com xfade
    if n_clips == 1:
        run_ffmpeg(["-i", str(processed[0]), "-c", "copy", str(output)])
        return

    xfade_duration = 0.5
    filter_parts: list[str] = []
    offsets: list[float] = []

    prev_label = "0:v"
    for i in range(1, n_clips):
        offset = per_clip * i - xfade_duration * i
        offsets.append(offset)
        out_label = f"v{i}"
        filter_parts.append(
            f"[{prev_label}][{i}:v]xfade=transition=fade:duration={xfade_duration}:offset={offset}[{out_label}]"
        )
        prev_label = out_label

    # Adiciona overlay de texto (hook) no resultado do xfade
    if hook:
        overlay_label = "vtxt"
        filter_parts.append(
            f"[{prev_label}]{_build_overlay_filter(hook, spec.width, spec.height)}[{overlay_label}]"
        )
        prev_label = overlay_label

    inputs: list[str] = []
    for p in processed:
        inputs += ["-i", str(p)]

    final_label = prev_label
    cmd_args = inputs + [
        "-filter_complex", ";".join(filter_parts),
        "-map", f"[{final_label}]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-movflags", "+faststart",
    ]

    if audio_path:
        cmd_args += ["-stream_loop", "-1", "-i", str(audio_path)]
        cmd_args += ["-map", f"{n_clips}:a:0", "-c:a", "aac", "-b:a", "192k"]
        cmd_args += ["-t", str(spec.duration)]

    cmd_args += [str(output)]
    run_ffmpeg(cmd_args)

    # Limpa arquivos temporarios
    for p in processed:
        p.unlink(missing_ok=True)


def build_pata_jazz_video(
    spec: VideoSpec,
    output_dir: Path,
    thumb_dir: Path,
    stem_prefix: str,
) -> Path:
    """Pipeline comum de geração de vídeo Pata Jazz.

    Shorts usam 2-3 clipes com crossfade; horizontais usam 1 clipe em loop.
    Retorna o caminho do vídeo gerado.
    """
    ensure_dirs()
    _validate_source_pools()

    scene = spec.scene if spec.scene else random_scene()
    hook, emoji = hook_for_scene(scene)
    audio_path = pick_audio()

    output, thumb, _ = _prepare_output_paths(stem_prefix, output_dir, thumb_dir)

    if spec.kind == "short":
        # Multi-clip com crossfade para Shorts
        videos = pick_videos(min_count=2, max_count=3, cuteness_sort=True)
        if len(videos) >= 2:
            _build_multi_clip_short(spec, videos, audio_path, output, hook=hook)
        else:
            # Fallback: 1 clipe em loop
            video = random.choice(pick_videos(min_count=1, max_count=1))
            _build_single_clip_video(spec, video, audio_path, output, hook=hook)
    else:
        # Horizontais: 1 clipe em loop (sem overlay de hook, e mais longo)
        video = random.choice(pick_videos(min_count=1, max_count=1))
        _build_single_clip_video(spec, video, audio_path, output)

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
        "kind": spec.kind,
        "mood": spec.mood,
        "duration": spec.duration,
        "resolution": f"{spec.width}x{spec.height}",
        "video": str(output),
        "thumbnail": str(thumb),
        "audio": str(audio_path) if audio_path else None,
    }
    output.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # Gera legenda SRT automatica
    try:
        from utils.caption_engine import generate_srt, save_srt
        srt_content = generate_srt(hook, scene, spec.duration, spec.kind, emoji)
        srt_path = save_srt(srt_content, output)
        meta["caption"] = str(srt_path)
        output.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning("Falha ao gerar legenda: %s", exc)

    from utils.video_validator import validate_generated_video
    validation = validate_generated_video(output, meta["resolution"], spec.duration)
    if not validation.ok:
        raise RuntimeError(f"Vídeo gerado não passou na validação: {'; '.join(validation.errors)}")
    log.info("%s gerado e validado: %s", spec.kind.capitalize(), output)
    return output


def short_spec(duration: int = 35, scene: str = "", mood: str = "") -> VideoSpec:
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
        fallback_description=f"{hook_for_scene(scene or random_scene())[0]} com jazz de fundo. 🐾🎷 #PataJazz",
        scene=scene,
        mood=mood,
    )


def horizontal_spec(duration: int = 240, scene: str = "", mood: str = "") -> VideoSpec:
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
        scene=scene,
        mood=mood,
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
