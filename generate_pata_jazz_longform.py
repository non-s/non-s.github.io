"""
generate_pata_jazz_longform.py — gera compilações temáticas longas (1-10h) de
gatos/cachorros + jazz, horizontais 1920x1080.

Resolução: 1920x1080, duração 1h (3600s) por padrão (até 10h). Mesmo pipeline
do horizontal (1 clipe em loop + áudio em loop), mas com chapters de 1h e
descrição longa. Sem overlay de hook (vídeo longo, "ambiente").
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from utils.channel_config import set_channel_from_env
from utils.content_strategy import mood_for_now, scene_for_mood
from utils.log_config import configure_logging, log_exception_to_file
from utils.media_pool import audio_pool, ensure_dirs, pool_stats
from utils.pipeline_metrics import record_pipeline_run
from utils.slot_optimizer import optimized_scene_and_pattern
from utils.video_builder import build_pata_jazz_video, longform_spec

set_channel_from_env()

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"
THUMB_DIR = ROOT / "_assets" / "thumbnails"

log = logging.getLogger(__name__)

DEFAULT_DURATION = 3600


def _generate_longform(duration: int = DEFAULT_DURATION, dry_run: bool = False) -> Path:
    """Gera uma compilação longa (1h+) horizontal com clipes de gatos/cachorros + jazz.

    Mood automático pela hora atual (BRT). Cena/padrão escolhidos por previsão
    de views (utils/slot_optimizer) quando modelo treinado. Reusa o caminho de
    1 clipe em loop do horizontal (estável, sem re-encode de concat longos).
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
    log.info("Longform mood=%s, cena=%s, padrao=%s", mood, scene, pattern_hint or "(sorteio)")

    ensure_dirs()
    stats = pool_stats()
    log.info(
        "Pool: %d clipes, %d faixas de jazz (longform usa 1 clipe em loop + 1 faixa em loop)",
        stats["videos"], stats["audio"],
    )
    audio_count = len(audio_pool())
    if audio_count > 0:
        log.info("Playlist de jazz completa (~%d faixas) coberta pelo loop do audio", audio_count)

    spec = longform_spec(duration=duration, scene=scene, mood=mood, title_pattern_hint=pattern_hint or "")
    return build_pata_jazz_video(
        spec=spec,
        output_dir=OUTPUT_DIR,
        thumb_dir=THUMB_DIR,
        stem_prefix="pata_jazz_longform",
        dry_run=dry_run,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Gerar compilação longa Pata Jazz (1-10h)")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION, help="Duração em segundos (3600-36000)")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem executar FFmpeg nem gerar arquivos")
    args = parser.parse_args()

    if not 3600 <= args.duration <= 36000:
        log.error("Duração %d fora do intervalo longform (3600-36000s).", args.duration)
        return 1

    configure_logging()

    start_time = time.time()
    success = False
    try:
        _generate_longform(duration=args.duration, dry_run=args.dry_run)
        success = True
        return 0
    except Exception as exc:
        log.exception("Falha ao gerar compilação longa: %s", exc)
        log_exception_to_file(exc, OUTPUT_DIR)
        return 1
    finally:
        record_pipeline_run(
            stage="generate_longform",
            success=success,
            duration_seconds=time.time() - start_time,
            kind="longform",
        )


if __name__ == "__main__":
    sys.exit(main())
