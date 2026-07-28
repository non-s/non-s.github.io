"""
utils/content_strategy.py — estratégia de conteúdo Pata Jazz (mood/cena por horário).

Mapeia horário do dia -> mood para escolher cenas apropriadas:
  Manhã (06-12): diversao (energia, gatos brincando)
  Tarde  (12-18): fofura (fofo, gatinhos dormindo)
  Noite  (18-24): relax (relaxamento, cachorros dormindo)
  Madrugada (00-06): relax
"""

from __future__ import annotations

import json
import logging
import os
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
_SCENE_PERFORMANCE_FILE = ROOT / "_data" / "scene_performance.json"

# Categorias de cenas
SCENE_CATEGORIES: dict[str, list[str]] = {
    "fofura": ["cat", "kitten", "puppy", "dog", "sleepy cat"],
    "diversao": ["playful dog", "cat playing", "puppy playing", "dog relaxing"],
    "relax": ["sleepy cat", "sleepy dog", "cat relaxing", "dog relaxing"],
}

# Mapeamento de faixa horaria (BRT) -> mood
# Manha = energia/diversao, Tarde = fofura, Noite/Madrugada = relax
_HOURLY_MOOD: dict[int, str] = {
    h: ("diversao" if 6 <= h < 12 else "fofura" if 12 <= h < 18 else "relax")
    for h in range(24)
}


def current_brt_hour() -> int:
    """Retorna a hora atual em BRT (UTC-3 por default, configuravel via
    BRT_OFFSET_HOURS)."""
    offset = float(os.environ.get("BRT_OFFSET_HOURS", "-3"))
    return (datetime.now(UTC) + timedelta(hours=offset)).hour


def mood_for_now() -> str:
    """Retorna o mood apropriado para a hora atual (BRT).

    Mood sazonal tem prioridade: se a data atual cai num periodo sazonal
    definido (ex: Natal, Ano Novo, Black Friday), o mood correspondente e
    retornado em vez do horario fixo - datas geram picos de busca por
    "relaxing pet music" e o conteudo deve refletir a sazonalidade.
    """
    seasonal = _seasonal_mood()
    if seasonal:
        return seasonal
    return _HOURLY_MOOD.get(current_brt_hour(), "fofura")


# Datas sazonais (mes, dia) -> mood. Janela de alguns dias antes para capturar
# a busca antecipada. None = sem sazonalidade ativa hoje.
_SEASONAL_MOODS: list[tuple[int, int, int, int, str]] = [
    # (mes_inicio, dia_inicio, mes_fim, dia_fim, mood)
    (12, 20, 12, 31, "relax"),      # Natal / festas de fim de ano
    (1, 1, 1, 6, "relax"),          # Ano novo
    (11, 20, 11, 30, "fofura"),     # Black Friday / Thanksgiving (fofura/volta as aulas EUA)
    (2, 10, 2, 16, "diversao"),     # Valentines Day (energia/diversao)
    (10, 28, 11, 3, "fofura"),      # Halloween
]


def _seasonal_mood() -> str | None:
    """Retorna o mood sazonal para a data atual (BRT), se houver."""
    offset = float(os.environ.get("BRT_OFFSET_HOURS", "-3"))
    now = datetime.now(UTC) + timedelta(hours=offset)
    for m1, d1, m2, d2, mood in _SEASONAL_MOODS:
        start = now.replace(month=m1, day=d1, hour=0, minute=0, second=0, microsecond=0)
        try:
            end = now.replace(month=m2, day=d2, hour=23, minute=59, second=59, microsecond=0)
        except ValueError:
            continue
        if start <= now <= end:
            log.info("Mood sazonal ativo: %s (%02d/%02d-%02d/%02d)", mood, m1, d1, m2, d2)
            return mood
    return None


def _scene_weights() -> dict[str, float]:
    """Le _data/scene_performance.json (gerado por collect_analytics.py a
    partir de views reais por cena). Ausente/corrompido = sem preferencia."""
    try:
        data = json.loads(_SCENE_PERFORMANCE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        log.debug("scene_performance.json ausente/corrompido: %s", exc)
        return {}


def scene_for_mood(mood: str) -> str:
    """Retorna uma cena especifica (ex: 'sleepy cat') para o mood dado.

    Quando ha dados reais de performance (scene_performance.json), a
    escolha e ponderada por eles em vez de puramente uniforme - cenas que
    historicamente tiveram mais views por video ficam mais provaveis, sem
    nunca zerar a chance das outras (ver _MIN_WEIGHT em collect_analytics.py).
    """
    scenes = SCENE_CATEGORIES.get(mood, SCENE_CATEGORIES["fofura"])
    weights_by_scene = _scene_weights()
    if not weights_by_scene:
        return random.choice(scenes)
    weights = [weights_by_scene.get(scene, 1.0) for scene in scenes]
    return random.choices(scenes, weights=weights, k=1)[0]
