"""
generate_pata_jazz_horizontal.py — gera videos longos horizontais de gatos/cachorros + jazz.

Resolucao: 1920x1080, duracao ~3-5 minutos, musica de jazz real em background.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from utils.ai_helper import ai_text
from utils.animal_branding import hook_for_scene, random_scene
from utils.ffmpeg_helpers import build_concat_demuxer, run_ffmpeg
from utils.media_pool import ensure_dirs, pick_audio, pick_videos, pool_stats

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"
THUMB_DIR = ROOT / "_assets" / "thumbnails"

log = logging.getLogger(__name__)


def _make_thumbnail(scene: str, hook: str, output: Path) -> None:
    width, height = 1280, 720
    img = Image.new("RGB", (width, height), "#1a1a2e")
    draw = ImageDraw.Draw(img)
    try:
        font_large = ImageFont.truetype("arial.ttf", 64)
        font_small = ImageFont.truetype("arial.ttf", 36)
    except Exception:
        font_large = ImageFont.load_default()
        font_small = font_large

    draw.text((width // 2 - 200, 200), "Pata Jazz", font=font_large, fill="#f4a261")
    draw.text((width // 2 - 250, 320), hook, font=font_small, fill="#f8f8ff")
    draw.text((width // 2 - 80, 420), "🐾🎷", font=font_large, fill="#f8f8ff")
    img.save(output)


def _generate_metadata(scene: str, hook: str) -> tuple[str, str]:
    prompt = (
        f"Crie um titulo amigavel (maximo 100 caracteres) e uma descricao de 2 a 4 linhas "
        f"para um video do YouTube sobre {hook} com jazz de fundo. "
        f"O canal e Pata Jazz (gatos e cachorros fofos + jazz). "
        f"Retorne APENAS JSON com chaves 'title' e 'description'."
    )
    out = ai_text(prompt, json_mode=True, task="horizontal_metadata")
    title = f"{hook} | Pata Jazz"
    description = f"{hook} com jazz suave de fundo. Curta, relaxe e acompanhe os bichinhos fofos. 🐾🎷 #PataJazz"
    if out:
        try:
            import json

            data = json.loads(out)
            title = str(data.get("title", title))[:100]
            description = str(data.get("description", description))[:4000]
        except Exception:
            pass
    return title, description


def _generate_horizontal(duration: int = 240, resolution: tuple[int, int] = (1920, 1080)) -> Path:
    """Gera um video horizontal com UM clipe e UMA musica de jazz."""
    ensure_dirs()
    stats = pool_stats()
    if stats["videos"] == 0:
        raise RuntimeError("Pool de b-roll vazio")
    if stats["audio"] == 0:
        log.warning("Pool de jazz vazio. Video sera gerado sem audio.")

    scene = random_scene()
    hook, emoji = hook_for_scene(scene)
    video = random.choice(pick_videos(min_count=1, max_count=1))
    audio_path = pick_audio()

    output_stem = f"pata_jazz_horizontal_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    output = OUTPUT_DIR / f"{output_stem}.mp4"
    thumb = THUMB_DIR / f"{output_stem}.png"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)

    vf = (
        f"crop='min(iw,ih*16/9):min(ih,iw*9/16)':(iw-min(iw,ih*16/9))/2:(ih-min(ih,iw*9/16))/2,"
        f"scale={resolution[0]}:{resolution[1]},"
        f"setsar=1:1"
    )

    audio_args: list[str] = []
    if audio_path:
        audio_args = [
            "-i",
            str(audio_path),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
        ]

    run_ffmpeg(
        [
            "-i",
            str(video),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-t",
            str(duration),
            "-r",
            "30",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
        ]
        + audio_args
        + [str(output)]
    )

    _make_thumbnail(scene, hook, thumb)

    title, description = _generate_metadata(scene, hook)
    meta = {
        "title": title,
        "description": description,
        "scene": scene,
        "hook": hook,
        "duration": duration,
        "resolution": f"{resolution[0]}x{resolution[1]}",
        "video": str(output),
        "thumbnail": str(thumb),
        "audio": str(audio_path) if audio_path else None,
    }
    import json

    output.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("Video horizontal gerado: %s", output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Gerar video horizontal Pata Jazz")
    parser.add_argument("--duration", type=int, default=240, help="Duracao em segundos")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.dry_run:
        os.environ.setdefault("GEMINI_API_KEY", "dry-run")

    try:
        _generate_horizontal(duration=args.duration)
        return 0
    except Exception as exc:
        log.exception("Falha ao gerar video horizontal: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
