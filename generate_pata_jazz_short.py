"""
generate_pata_jazz_short.py — gera Shorts verticais de gatos/cachorros + jazz.

Resolucao: 1080x1920, duracao ~30-60s, musica de jazz real em background.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from utils.log_config import configure_logging, log_exception_to_file
from utils.video_builder import build_pata_jazz_video, short_spec
from utils.content_strategy import pick_scene_category, weekly_calendar
from utils.media_pool import pick_videos

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"
THUMB_DIR = ROOT / "_assets" / "thumbnails"

log = logging.getLogger(__name__)

DEFAULT_DURATION = 35


def _generate_short(duration: int = DEFAULT_DURATION) -> Path:
    """Gera um Short com UM clipe e UMA musica de jazz.

    YouTube Shorts exige aspecto 9:16, sem bordas pretas e duracao curta.
    Por isso cortamos/padronizamos o clipe para ocupar toda a tela vertical.
    
    Usa content_strategy para selecionar mood baseado no dia da semana.
    """
    # Seleciona mood baseado no calendário editorial
    calendar = weekly_calendar()
    today_idx = None
    try:
        from datetime import datetime, timezone
        weekday = datetime.now(timezone.utc).weekday()
        today_idx = weekday % len(calendar)
    except Exception:
        today_idx = None
    
    mood = calendar[today_idx]["mood"] if today_idx is not None and today_idx < len(calendar) else "fofura"
    category = pick_scene_category(mood)
    
    # Pré-seleciona vídeos da categoria para garantir consistência
    videos = pick_videos(cuteness_sort=True)
    
    spec = short_spec(duration=duration)
    return build_pata_jazz_video(spec=spec, output_dir=OUTPUT_DIR, thumb_dir=THUMB_DIR, stem_prefix="pata_jazz_short")


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
