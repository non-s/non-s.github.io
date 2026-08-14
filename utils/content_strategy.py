"""
utils/content_strategy.py — estratégia de conteúdo Liquid Wire (mood/cena por horário).

Mapeia horário do dia -> mood para escolher cenas apropriadas:
  Manhã (06-12): focus (energia, concentração, geometria precisa)
  Tarde  (12-18): ambient (calma, fluxo contínuo, orgânico)
  Noite  (18-24): relax (relaxamento, pausa, fluido)
  Madrugada (00-06): relax
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


def _scene_performance_file() -> Path:
    return data_dir() / "scene_performance.json"


def _viral_signals_file() -> Path:
    return data_dir() / "viral_signals.json"


_VIRAL_BOOST = 2.0
_VIRAL_BOOST_WINDOW_DAYS = 14

# Categorias de cenas — arte generativa
SCENE_CATEGORIES: dict[str, list[str]] = {
    "focus": ["calm wireframe flow", "geometric drift", "crystal lattice", "precise wireframe"],
    "ambient": ["liquid wireframe blob", "slow wireframe gel", "fluid mesh form", "particle drift"],
    "relax": ["dark liquid wire", "night ambient mesh", "slowform drift", "nebula cloud"],
}


_FIRST_UPLOADS_PRIORITY_SCENES = [
    "calm wireframe flow", "liquid wireframe blob", "fluid mesh form", "geometric drift",
]
_FIRST_UPLOADS_THRESHOLD = 10

# Mapeamento de faixa horaria (BRT) -> mood
_HOURLY_MOOD: dict[int, str] = {
    h: ("focus" if 6 <= h < 12 else "ambient" if 12 <= h < 18 else "relax") for h in range(24)
}


def current_brt_hour() -> int:
    offset = float(os.environ.get("BRT_OFFSET_HOURS", "-3"))
    return (datetime.now(UTC) + timedelta(hours=offset)).hour


def min_quality_score_for_slot(hour: int) -> float:
    """Return minimum quality score for the given hour (BRT).

    Morning hours (6-12) require a higher score (0.82) because audience
    competition is higher and viewers are more selective. Late night
    (22-6) can be more lenient (0.75) since the audience is smaller and
    more tolerant of slower, sparser content. Default: 0.78.

    Used by generate_liquid_wire_video.py to set the per-slot quality gate
    threshold via assess_video(min_score=...) instead of a hardcoded 0.78.
    """
    if 6 <= hour < 12:
        return 0.82
    elif 22 <= hour or hour < 6:
        return 0.75
    return 0.78


def mood_for_now() -> str:
    """Retorna o mood apropriado para a hora atual (BRT).

    Mood sazonal tem prioridade.
    """
    seasonal = _seasonal_mood()
    if seasonal:
        return seasonal
    return _HOURLY_MOOD.get(current_brt_hour(), "ambient")


_SEASONAL_MOODS: list[tuple[int, int, int, int, str]] = [
    (12, 20, 12, 31, "relax"),
    (1, 1, 1, 6, "relax"),
    (11, 20, 11, 30, "ambient"),
    (2, 10, 2, 16, "focus"),
    (10, 28, 11, 3, "ambient"),
]


def _seasonal_mood() -> str | None:
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
    try:
        data = json.loads(_scene_performance_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        log.debug("scene_performance.json ausente/corrompido: %s", exc)
        return {}


def viral_boosted_scenes() -> dict[str, float]:
    try:
        data = json.loads(_viral_signals_file().read_text(encoding="utf-8"))
    except Exception as exc:
        log.debug("viral_signals.json ausente/corrompido: %s", exc)
        return {}
    if not isinstance(data, list):
        return {}

    now = datetime.now(UTC)
    cutoff = now - timedelta(days=_VIRAL_BOOST_WINDOW_DAYS)
    boosted: dict[str, float] = {}
    for signal in data:
        if not isinstance(signal, dict):
            continue
        scene = (signal.get("scene") or "").strip()
        if not scene:
            continue
        detected_at = signal.get("detected_at")
        if not detected_at:
            continue
        try:
            s = str(detected_at).strip()
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
        except Exception:
            continue
        if dt.astimezone(UTC) < cutoff:
            continue

        boost = _VIRAL_BOOST
        try:
            ctr = float(signal.get("ctr", 0) or 0)
            avp = float(signal.get("avp", 0) or 0)
        except Exception:
            ctr, avp = 0.0, 0.0
        if ctr > 0.05:
            boost += 0.3
        if avp > 0.5:
            boost += 0.2
        boosted[scene] = boost
    return boosted


def scene_for_mood(mood: str) -> str:
    """Retorna uma cena especifica (ex: 'calm wireframe flow') para o mood dado.

    Quando ha dados reais de performance, a escolha e ponderada por eles.
    Cenas que geraram virais recentes recebem um boost conservador.
    """
    scenes = SCENE_CATEGORIES.get(mood, SCENE_CATEGORIES["ambient"])
    weights_by_scene = _scene_weights()
    viral_boosts = viral_boosted_scenes()

    use_priority = False
    priority_boost: dict[str, float] = {}
    try:
        from utils.paths import data_dir as _data_dir

        counter_file = _data_dir() / "upload_language_counter.json"
        if counter_file.exists():
            import json

            data = json.loads(counter_file.read_text(encoding="utf-8"))
            count = int(data.get("count", 0)) if isinstance(data, dict) else 0
            if count < _FIRST_UPLOADS_THRESHOLD:
                use_priority = True
                for s in _FIRST_UPLOADS_PRIORITY_SCENES:
                    if s in scenes:
                        priority_boost[s] = 2.5
    except Exception:
        pass

    if not weights_by_scene and not viral_boosts and not use_priority:
        return random.choice(scenes)
    weights = []
    for scene in scenes:
        w = weights_by_scene.get(scene, 1.0)
        if scene in viral_boosts:
            w *= viral_boosts[scene]
        if use_priority and scene in priority_boost:
            w *= priority_boost[scene]
        weights.append(w)
    return random.choices(scenes, weights=weights, k=1)[0]
