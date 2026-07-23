"""
generate_pata_jazz_short.py — gera Shorts verticais de gatos/cachorros + jazz.

Resolucao: 1080x1920, duracao ~30-60s, musica de jazz real em background.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from utils.animal_branding import hook_for_scene, random_scene
from utils.ffmpeg_helpers import run_ffmpeg
from utils.media_pool import ensure_dirs, pick_audio, pick_videos, pool_stats
from utils.metadata_engine import clean_title, generate_metadata
from utils.thumbnail_engine import make_short_thumbnail

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"
THUMB_DIR = ROOT / "_assets" / "thumbnails"

log = logging.getLogger(__name__)

DEFAULT_DURATION = 35
DEFAULT_RESOLUTION = (1080, 1920)


def _generate_short(
    duration: int = DEFAULT_DURATION,
    target_resolution: tuple[int, int] = DEFAULT_RESOLUTION,
) -> Path:
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

    # Crop central preservando o maior retangulo 9:16 possivel, depois preenche.
    w, h = target_resolution
    vf = (
        f"crop='ih*9/16:ih:0:0',"
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,"
        f"setsar=1/1"
    )

    inputs = ["-i", str(video)]
    output_args: list[str] = [
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-t", str(duration),
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
    ]
    if audio_path:
        inputs += ["-stream_loop", "-1", "-i", str(audio_path)]
        output_args += ["-c:a", "aac", "-b:a", "192k", "-shortest"]

    run_ffmpeg(inputs + output_args + [str(output)])

    make_short_thumbnail(hook, emoji, thumb)

    metadata = generate_metadata(
        hook=hook,
        scene=scene,
        duration=duration,
        kind="short",
        emoji=emoji,
        fallback_title=clean_title(f"{hook} | Pata Jazz"),
        fallback_description=f"{hook} com jazz de fundo. 🐾🎷 #PataJazz",
    )
    meta = {
        **metadata,
        "scene": scene,
        "hook": hook,
        "duration": duration,
        "resolution": f"{w}x{h}",
        "video": str(output),
        "thumbnail": str(thumb),
        "audio": str(audio_path) if audio_path else None,
    }
    output.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("Short gerado: %s", output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Gerar Short Pata Jazz")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION, help="Duracao em segundos")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.dry_run:
        os.environ.setdefault("GEMINI_API_KEY", "dry-run")

    try:
        _generate_short(duration=args.duration)
        return 0
    except Exception as exc:
        log.exception("Falha ao gerar Short: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
