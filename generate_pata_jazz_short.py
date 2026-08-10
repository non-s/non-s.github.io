"""
generate_pata_jazz_short.py — gera Shorts verticais de gatos/cachorros + jazz.

Resolucao: 1080x1920, duracao ~35s, musica de jazz real em background.
Mood selecionado automaticamente pelo horario (manha=diversao, tarde=fofura, noite=relax).
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from utils.content_strategy import current_brt_hour, mood_for_now, scene_for_mood
from utils.log_config import configure_logging, log_exception_to_file
from utils.pipeline_metrics import record_pipeline_run
from utils.seo_keywords import pick_upload_language
from utils.slot_optimizer import optimized_scene_and_pattern
from utils.video_builder import build_pata_jazz_video, short_spec

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"
THUMB_DIR = ROOT / "_assets" / "thumbnails"

log = logging.getLogger(__name__)

DEFAULT_DURATION = 35
# Faixa usada quando --duration nao e passado explicitamente: variedade de
# duracao entre Shorts (todos saindo com exatamente 35s toda vez e outro
# sinal de conteudo repetitivo/automatizado). utils.video_builder ja ajusta
# o numero de clipes e o offset do crossfade dinamicamente pra qualquer
# duracao (_build_multi_clip_short), entao variar aqui e seguro.
DURATION_RANGE = (28, 42)


def _pick_duration() -> int:
    return random.randint(*DURATION_RANGE)


def _generate_short(duration: int = DEFAULT_DURATION, dry_run: bool = False) -> Path:
    """Gera um Short vertical com clipes de gatos/cachorros + musica de jazz.

    Seleciona o mood automaticamente pela hora atual (BRT):
      manha  (06-12): diversao (energia, brincando)
      tarde  (12-18): fofura (fofo, dormindo)
      noite  (18-06): relax (relaxamento, calmo)

    A cena/padrao sao escolhidos por previsao de views (utils/slot_optimizer)
    quando o modelo preditivo esta treinado; sem modelo, cai no sorteio
    ponderado por performance historica (content_strategy).
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
    log.info(
        "Mood=%s, cena=%s, padrao=%s, horario BRT=%dh",
        mood,
        scene,
        pattern_hint or "(sorteio)",
        current_brt_hour(),
    )

    # A3: decide o idioma do upload (EN/PT-BR/ES) baseado num contador
    # persistente. 1 a cada 6 uploads vira PT-BR, 1 a cada 12 vira ES,
    # resto EN - captura publico lusofono/hispanofono sem custo adicional.
    lang = pick_upload_language()
    log.info("Idioma do upload: %s", lang)

    spec = short_spec(
        duration=duration, scene=scene, mood=mood, title_pattern_hint=pattern_hint or "", lang=lang
    )
    return build_pata_jazz_video(
        spec=spec,
        output_dir=OUTPUT_DIR,
        thumb_dir=THUMB_DIR,
        stem_prefix="pata_jazz_short",
        dry_run=dry_run,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Gerar Short Pata Jazz")
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help=f"Duracao em segundos (default: aleatorio entre {DURATION_RANGE[0]}-{DURATION_RANGE[1]})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Simula sem executar FFmpeg nem gerar arquivos")
    args = parser.parse_args()

    configure_logging()
    duration = args.duration if args.duration is not None else _pick_duration()

    start_time = time.time()
    success = False
    try:
        _generate_short(duration=duration, dry_run=args.dry_run)
        success = True
        return 0
    except Exception as exc:
        log.exception("Falha ao gerar Short: %s", exc)
        log_exception_to_file(exc, OUTPUT_DIR)
        return 1
    finally:
        record_pipeline_run(
            stage="generate_short",
            success=success,
            duration_seconds=time.time() - start_time,
            kind="vertical",
        )


if __name__ == "__main__":
    sys.exit(main())
