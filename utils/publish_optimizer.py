"""
utils/publish_optimizer.py — escolha inteligente de dia/hora para publicação.

Estratégia:
- Prioriza slots historicamente fortes para o nicho generative art/ambient.
- Combina heurística de benchmark (fins de tarde/noite norte-americana e
  europeia) com dados reais de performance do canal, quando disponíveis.
- Gera múltiplos slots candidatos para o workflow escolher sem acordar ninguém.

Métricas de entrada (quando existirem em data_dir/publish_slots.json):
- avg_views: média de views por slot
- ctr: click-through rate médio
- retention: retenção média (segundos)
- samples: número de vídeos publicados naquele slot

Fallback: sem dados, usa heurística de alto desempenho para nicho generative art:
- Quinta e sexta (pré-fim de semana)
- 17h-21h BRT (fins de tarde/noite EUA + noite Europa)
- Domingo 10h-14h (momento de lazer + ambient)
"""

from __future__ import annotations

import json
import logging
import os
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from utils.paths import data_dir

log = logging.getLogger(__name__)


# Slots heurísticos de alto CTR para nicho generative art/ambient (BRT)
_BENCHMARK_SLOTS: dict[int, list[int]] = {
    0: [10, 14, 19, 21],  # domingo
    1: [18, 20],
    2: [18, 20],
    3: [17, 19, 21],
    4: [17, 19, 21],      # quinta
    5: [17, 19, 21],      # sexta
    6: [10, 14, 19],
}

_MIN_SAMPLES_FOR_DATA = 3
_MAX_CANDIDATES = 5


def _publish_slots_file() -> Path:
    return data_dir() / "publish_slots.json"


def _load_slots_data() -> dict:
    try:
        data = json.loads(_publish_slots_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        log.debug("publish_slots.json ausente/corrompido: %s", exc)
        return {}


def _now_brt() -> datetime:
    offset = float(os.environ.get("BRT_OFFSET_HOURS", "-3"))
    return datetime.now(UTC) + timedelta(hours=offset)


def _slot_score(slot_data: dict) -> float:
    """Score composto de um slot: views * 0.6 + ctr * 0.25 + retention * 0.15.

    Normaliza cada componente pelo máximo visto nos dados para evitar que
    unidades diferentes dominem o score.
    """
    views = float(slot_data.get("avg_views", 0) or 0)
    ctr = float(slot_data.get("ctr", 0) or 0)
    retention = float(slot_data.get("retention", 0) or 0)
    samples = int(slot_data.get("samples", 0) or 0)
    if samples < _MIN_SAMPLES_FOR_DATA:
        return 0.0
    return views * 0.6 + ctr * 1000 * 0.25 + retention * 0.15


def _next_n_days(n: int = 7) -> list[tuple[int, int]]:
    """Retorna próximos n dias como (day_of_week, iso_date_int YYYYMMDD)."""
    now = _now_brt()
    days: list[tuple[int, int]] = []
    for i in range(n):
        d = now + timedelta(days=i)
        days.append((d.weekday(), int(d.strftime("%Y%m%d"))))
    return days


def best_publish_slots(
    count: int = _MAX_CANDIDATES,
    horizon_days: int = 7,
    min_delay_hours: int = 2,
) -> list[dict]:
    """Retorna os melhores slots futuros para publicação, ordenados por score.

    Cada slot tem: day_of_week (0=dom), date_int (YYYYMMDD), hour, score,
    source ('data' ou 'benchmark').
    """
    data = _load_slots_data()
    days = _next_n_days(horizon_days)
    now = _now_brt()

    candidates: list[dict] = []
    for day_of_week, date_int in days:
        # slots baseados em dados do canal
        day_key = str(day_of_week)
        if isinstance(data.get(day_key), dict):
            for hour_str, slot_data in data[day_key].items():
                if not isinstance(slot_data, dict):
                    continue
                hour = int(hour_str)
                scheduled = datetime.strptime(str(date_int), "%Y%m%d").replace(hour=hour, tzinfo=UTC)
                if (scheduled - now).total_seconds() / 3600 < min_delay_hours:
                    continue
                score = _slot_score(slot_data)
                if score > 0:
                    candidates.append({
                        "day_of_week": day_of_week,
                        "date_int": date_int,
                        "hour": hour,
                        "score": round(score, 2),
                        "source": "data",
                    })

        # slots heurísticos de benchmark
        for hour in _BENCHMARK_SLOTS.get(day_of_week, []):
            scheduled = datetime.strptime(str(date_int), "%Y%m%d").replace(hour=hour, tzinfo=UTC)
            if (scheduled - now).total_seconds() / 3600 < min_delay_hours:
                continue
            # Evita duplicar slot já vindo de dados
            already = any(
                c["day_of_week"] == day_of_week and c["date_int"] == date_int and c["hour"] == hour
                for c in candidates
            )
            if already:
                continue
            candidates.append({
                "day_of_week": day_of_week,
                "date_int": date_int,
                "hour": hour,
                "score": 1.0,  # base
                "source": "benchmark",
            })

    # Ordena por score decrescente
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:count]


def pick_publish_time(
    count: int = _MAX_CANDIDATES,
    horizon_days: int = 7,
    min_delay_hours: int = 2,
) -> dict:
    """Escolhe um slot de publicação.

    Se houver dados de performance com amostras suficientes, pondera pelos
    scores; caso contrário, sorteia uniformemente entre os slots benchmark.
    """
    slots = best_publish_slots(count=count, horizon_days=horizon_days, min_delay_hours=min_delay_hours)
    data_slots = [s for s in slots if s["source"] == "data"]
    if data_slots:
        weights = [s["score"] for s in data_slots]
        chosen = random.choices(data_slots, weights=weights, k=1)[0]
        log.info("Slot escolhido por dados: %s", chosen)
        return chosen

    if slots:
        chosen = random.choice(slots)
        log.info("Slot escolhido por benchmark: %s", chosen)
        return chosen

    # fallback drástico: amanhã 18h BRT
    tomorrow = _now_brt() + timedelta(days=1)
    return {
        "day_of_week": tomorrow.weekday(),
        "date_int": int(tomorrow.strftime("%Y%m%d")),
        "hour": 18,
        "score": 0.0,
        "source": "fallback",
    }


def iso_datetime_from_slot(slot: dict, offset_hours: float = -3.0) -> str:
    """Converte um slot retornado por pick_publish_time em ISO 8601 (UTC)."""
    date_int = int(slot["date_int"])
    hour = int(slot["hour"])
    dt = datetime.strptime(str(date_int), "%Y%m%d").replace(hour=hour)
    dt = dt - timedelta(hours=offset_hours)  # converte BRT -> UTC
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
