"""
generate_pata_jazz_short.py — gera Shorts verticais de gatos/cachorros + jazz.

Resolucao: 1080x1920, duracao ~35s, musica de jazz real em background.
Mood selecionado automaticamente pelo horario (manha=diversao, tarde=fofura, noite=relax).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from utils.log_config import configure_logging, log_exception_to_file
from utils.video_builder import build_pata_jazz_video, short_spec
from utils.content_strategy import mood_for_now, scene_for_mood

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"
THUMB_DIR = ROOT / "_assets" / "thumbnails"

log = logging.getLogger(__name__)

DEFAULT_DURATION = 35


def _generate_short(duration: int = DEFAULT_DURATION) -> Path:
    """Gera um Short vertical com clipes de gatos/cachorros + musica de jazz.

    Seleciona o mood automaticamente pela hora atual (BRT):
      manha  (06-12): diversao (energia, brincando)
      tarde  (12-18): fofura (fofo, dormindo)
      noite  (18-06): relax (relaxamento, calmo)
    """
    mood = mood_for_now()
    scene = scene_for_mood(mood)
    log.info("Mood=%s, cena=%s, horario BRT=%dh", mood, scene, None)

    spec = short_spec(duration=duration, scene=scene, mood=mood)
    return build_pata_jazz_video(
        spec=spec,
        output_dir=OUTPUT_DIR,
        thumb_dir=THUMB_DIR,
        stem_prefix="pata_jazz_short",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Gerar Short Pata Jazz")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION, help="Duracao em segundos")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    configure_logging()
    if args.dry_run:
        os.environ.setdefault("GEMINI_API_KEY", "dry-run")

    try:
        _generate_short(duration=args.duration)
        return 0
    except Exception as exc:
        log.exception("Falha ao gerar Short: %s", exc)
        log_exception_to_file(exc, OUTPUT_DIR)
        return 1


if __name__ == "__main__":
    sys.exit(main())