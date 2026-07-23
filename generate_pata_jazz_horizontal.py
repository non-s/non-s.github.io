"""
generate_pata_jazz_horizontal.py — gera videos longos horizontais de gatos/cachorros + jazz.

Resolucao: 1920x1080, duracao ~3-5 minutos, musica de jazz real em background.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from utils.log_config import configure_logging, log_exception_to_file
from utils.video_builder import build_pata_jazz_video, horizontal_spec
from utils.content_strategy import pick_scene_category, weekly_calendar

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"
THUMB_DIR = ROOT / "_assets" / "thumbnails"

log = logging.getLogger(__name__)

DEFAULT_DURATION = 240


def _generate_horizontal(duration: int = DEFAULT_DURATION) -> Path:
    """Gera um video horizontal com UM clipe e UMA musica de jazz.
    
    Usa content_strategy para selecionar mood baseado no dia da semana.
    """
    # Seleciona mood baseado no calendário editorial
    calendar = weekly_calendar()
    try:
        from datetime import datetime, timezone
        weekday = datetime.now(timezone.utc).weekday()
        today_entry = next((e for e in calendar if e["day"].lower() == ["seg", "ter", "qua", "qui", "sex", "sab", "dom"][weekday]), None)
        mood = today_entry["mood"] if today_entry else "fofura"
    except Exception:
        mood = "fofura"
    
    category = pick_scene_category(mood)
    log.info("Usando categoria '%s' (mood: %s) para video horizontal", category, mood)
    
    spec = horizontal_spec(duration=duration)
    return build_pata_jazz_video(
        spec=spec,
        output_dir=OUTPUT_DIR,
        thumb_dir=THUMB_DIR,
        stem_prefix="pata_jazz_horizontal",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Gerar video horizontal Pata Jazz")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION, help="Duracao em segundos")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    configure_logging()
    if args.dry_run:
        os.environ.setdefault("GEMINI_API_KEY", "dry-run")

    try:
        _generate_horizontal(duration=args.duration)
        return 0
    except Exception as exc:
        log.exception("Falha ao gerar video horizontal: %s", exc)
        log_exception_to_file(exc, OUTPUT_DIR)
        return 1


if __name__ == "__main__":
    sys.exit(main())
