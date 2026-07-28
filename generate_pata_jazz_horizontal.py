"""
generate_pata_jazz_horizontal.py — gera videos longos horizontais de gatos/cachorros + jazz.

Resolucao: 1920x1080, duracao ~4min, musica de jazz real em background.
Mood selecionado automaticamente pelo horario.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from utils.channel_config import set_channel_from_env
from utils.content_strategy import mood_for_now, scene_for_mood
from utils.log_config import configure_logging, log_exception_to_file
from utils.slot_optimizer import optimized_scene_and_pattern
from utils.video_builder import build_pata_jazz_video, horizontal_spec

# Ativa o canal via YOUTUBE_CHANNEL env var (multi-canal).
set_channel_from_env()

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"
THUMB_DIR = ROOT / "_assets" / "thumbnails"

log = logging.getLogger(__name__)

DEFAULT_DURATION = 240


def _generate_horizontal(duration: int = DEFAULT_DURATION, dry_run: bool = False) -> Path:
    """Gera um video horizontal com clipes de gatos/cachorros + musica de jazz.

    Mood automatico pela hora atual (BRT). Cena/padrao escolhidos por
    previsao de views (utils/slot_optimizer) quando modelo treinado.
    """
    mood = mood_for_now()
    fallback_scene = scene_for_mood(mood)
    now = datetime.now(UTC)
    scene, pattern_hint = optimized_scene_and_pattern(
        mood=mood,
        fallback_scene=fallback_scene,
        hour=now.hour,
        day_of_week=now.weekday(),
    )
    log.info("Mood=%s, cena=%s, padrao=%s", mood, scene, pattern_hint or "(sorteio)")

    spec = horizontal_spec(duration=duration, scene=scene, mood=mood, title_pattern_hint=pattern_hint or "")
    return build_pata_jazz_video(
        spec=spec,
        output_dir=OUTPUT_DIR,
        thumb_dir=THUMB_DIR,
        stem_prefix="pata_jazz_horizontal",
        dry_run=dry_run,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Gerar video horizontal Pata Jazz")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION, help="Duracao em segundos")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem executar FFmpeg nem gerar arquivos")
    args = parser.parse_args()

    configure_logging()

    try:
        _generate_horizontal(duration=args.duration, dry_run=args.dry_run)
        return 0
    except Exception as exc:
        log.exception("Falha ao gerar video horizontal: %s", exc)
        log_exception_to_file(exc, OUTPUT_DIR)
        return 1


if __name__ == "__main__":
    sys.exit(main())
