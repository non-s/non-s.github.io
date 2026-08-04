"""
scripts/generate_pata_jazz_long.py — gera long-form horizontal "Loop & Relax".

Resolucao: 1920x1080 (16:9), duracao entre 10 e 45 minutos, clipes de
gatos/cachorros em loop com crossfade lento + musica de jazz relaxante.

Long-form e o outro lado da estrategia do canal: enquanto Shorts constroem
alcance, videos longos (10-45min) sao assistidos por muito tempo (watch time
alto, recomendados por "pessoas que assistem isso tambem viram aquilo") e
pegam buscas de intencao de relaxamento ("jazz for cats to sleep", "relaxing
music for pets") que Shorts nunca alcançariam. Sao poucos, mas duram semanas
em "session time". Mood e sempre "relax" (o proprio formato e de relaxar).
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
import time
from pathlib import Path

from utils.content_strategy import scene_for_mood
from utils.log_config import configure_logging, log_exception_to_file
from utils.pipeline_metrics import record_pipeline_run
from utils.video_builder import build_pata_jazz_video, long_spec

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "_videos"
THUMB_DIR = ROOT / "_assets" / "thumbnails"

log = logging.getLogger(__name__)

DEFAULT_DURATION = 900
# Faixa usada quando --duration nao e passado: 10-20min. Acima disso o
# render no CI fica pesado demais para rodar com frequencia; o limite de
# 45min e aceito via CLI para geracoes manuais.
DURATION_RANGE = (900, 1200)
MIN_DURATION = 600
MAX_DURATION = 2700


def _pick_duration() -> int:
    return random.randint(*DURATION_RANGE)


def _generate_long(
    duration: int = DEFAULT_DURATION,
    scene: str | None = None,
    dry_run: bool = False,
) -> Path:
    """Gera um long-form "Loop & Relax" horizontal (16:9).

    Mood sempre 'relax': o formato inteiro e de relaxamento (dormir,
    estudar, ler). A cena vem do mood via content_strategy, a menos que
    seja passada explicitamente.
    """
    if not MIN_DURATION <= duration <= MAX_DURATION:
        raise ValueError(f"Duracao deve estar entre {MIN_DURATION}s e {MAX_DURATION}s.")
    mood = "relax"
    chosen_scene = scene if scene else scene_for_mood(mood)
    log.info("Long-form: mood=%s, cena=%s, duracao=%ds", mood, chosen_scene, duration)

    spec = long_spec(duration=duration, scene=chosen_scene, mood=mood)
    start_render = time.time()
    result = build_pata_jazz_video(
        spec=spec,
        output_dir=OUTPUT_DIR,
        thumb_dir=THUMB_DIR,
        stem_prefix="pata_jazz_long",
        dry_run=dry_run,
    )
    if not dry_run:
        log.info("Render do long-form concluido em %.1fs", time.time() - start_render)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Gerar long-form Loop & Relax Pata Jazz")
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help=(
            "Duracao em segundos (default: aleatorio entre "
            f"{DURATION_RANGE[0]}-{DURATION_RANGE[1]}, max {MAX_DURATION})"
        ),
    )
    parser.add_argument(
        "--scene",
        default=None,
        help="Cena fixa (ex: sleepy cat). Se omitido, sorteia dentro do mood relax.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Simula sem executar FFmpeg nem gerar arquivos")
    args = parser.parse_args()

    configure_logging()
    duration = args.duration if args.duration is not None else _pick_duration()

    start_time = time.time()
    success = False
    try:
        _generate_long(duration=duration, scene=args.scene, dry_run=args.dry_run)
        success = True
        return 0
    except Exception as exc:
        log.exception("Falha ao gerar long-form: %s", exc)
        log_exception_to_file(exc, OUTPUT_DIR)
        return 1
    finally:
        record_pipeline_run(
            stage="generate_long",
            success=success,
            duration_seconds=time.time() - start_time,
            kind="long",
        )


if __name__ == "__main__":
    sys.exit(main())
