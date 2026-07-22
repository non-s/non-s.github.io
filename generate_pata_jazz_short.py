"""
generate_pata_jazz_short.py — gera Shorts verticais de gatos/cachorros + jazz.

Resolucao: 1080x1920, duracao ~30-60s, musica de jazz real em background.
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from utils.ai_helper import ai_text
from utils.animal_branding import hook_for_scene, random_scene
from utils.ffmpeg_helpers import run_ffmpeg
from utils.media_pool import ensure_dirs, pick_audio, pick_videos, pool_stats

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"
THUMB_DIR = ROOT / "_assets" / "thumbnails"

log = logging.getLogger(__name__)


def _make_thumbnail(scene: str, hook: str, emoji: str, output: Path) -> None:
    width, height = 1080, 1920
    img = Image.new("RGB", (width, height), "#1a1a2e")
    draw = ImageDraw.Draw(img)
    try:
        font_large = ImageFont.truetype("arial.ttf", 72)
        font_small = ImageFont.truetype("arial.ttf", 48)
    except Exception:
        font_large = ImageFont.load_default()
        font_small = font_large

    # Emoji grande no centro
    bbox = draw.textbbox((0, 0), emoji, font=font_large)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, 500), emoji, font=font_large, fill="#f8f8ff")

    # Titulo
    lines = textwrap.wrap(hook, width=18)
    y = 700
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_small)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) // 2, y), line, font=font_small, fill="#f8f8ff")
        y += 70

    draw.text((width // 2 - 180, y + 40), "Pata Jazz", font=font_small, fill="#f4a261")
    img.save(output)


def _generate_description(scene: str, hook: str) -> tuple[str, str]:
    prompt = (
        f"Crie um titulo curto (maximo 80 caracteres) e uma descricao de ate 3 linhas "
        f"para um Short de YouTube sobre {hook}. O canal e Pata Jazz, so gatos e cachorros fofos com jazz. "
        f"Retorne APENAS um JSON com chaves 'title' e 'description'."
    )
    out = ai_text(prompt, json_mode=True, task="short_metadata")
    title = hook
    description = f"{hook} com jazz de fundo. 🐾🎷 #PataJazz"
    if out:
        try:
            import json

            data = json.loads(out)
            title = str(data.get("title", title))[:100]
            description = str(data.get("description", description))[:4000]
        except Exception:
            pass
    return title, description


def _generate_short(duration: int = 35, target_resolution: tuple[int, int] = (1080, 1920)) -> Path:
    """Gera um Short com UM clipe e UMA musica de jazz.

    YouTube Shorts exige aspecto 9:16, sem bordas pretas e duracao curta.
    Por isso cortamos/padronizamos o clipe para ocupar toda a tela vertical.
    """
    ensure_dirs()
    stats = pool_stats()
    if stats["videos"] == 0:
        log.error("Pool de b-roll vazio. Execute scripts/sync_animal_broll.py primeiro.")
        raise RuntimeError("Pool de b-roll vazio")
    if stats["audio"] == 0:
        log.warning("Pool de jazz vazio. Video sera gerado sem audio.")

    scene = random_scene()
    hook, emoji = hook_for_scene(scene)
    video = random.choice(pick_videos(min_count=1, max_count=1))
    audio_path = pick_audio()

    output_stem = f"pata_jazz_short_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    output = OUTPUT_DIR / f"{output_stem}.mp4"
    thumb = THUMB_DIR / f"{output_stem}.png"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)

    # Ajuste o clipe para 9:16, centralizando e preenchendo a tela.
    # Expressao sem virgulas internas para nao confundir o parser do -vf.
    vf = (
        f"crop='ih*9/16:ih:(iw-ih*9/16)/2:0',"
        f"scale={target_resolution[0]}:{target_resolution[1]},"
        f"setsar=1/1"
    )

    inputs = ["-i", str(video)]
    output_args: list[str] = [
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
    if audio_path:
        inputs += ["-i", str(audio_path)]
        output_args += ["-c:a", "aac", "-b:a", "128k", "-shortest"]

    run_ffmpeg(inputs + output_args + [str(output)])

    _make_thumbnail(scene, hook, emoji, thumb)

    title, description = _generate_description(scene, hook)
    meta = {
        "title": title,
        "description": description,
        "scene": scene,
        "hook": hook,
        "emoji": emoji,
        "duration": duration,
        "resolution": f"{target_resolution[0]}x{target_resolution[1]}",
        "video": str(output),
        "thumbnail": str(thumb),
        "audio": str(audio_path) if audio_path else None,
    }
    import json

    output.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("Short gerado: %s", output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Gerar Short Pata Jazz")
    parser.add_argument("--duration", type=int, default=35, help="Duracao em segundos")
    parser.add_argument("--dry-run", action="store_true", help="Nao chama APIs externas")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.dry_run:
        os.environ.setdefault("GEMINI_API_KEY", "dry-run")

    try:
        _generate_short(duration=args.duration)
        return 0
    except Exception as exc:
        log.exception("Falha ao gerar short: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
