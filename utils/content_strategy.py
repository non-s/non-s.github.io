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
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
    """Retorna a hora atual em BRT (UTC-3)."""
    return (datetime.now(UTC) - timedelta(hours=3)).hour


def mood_for_now() -> str:
    """Retorna o mood apropriado para a hora atual (BRT)."""
    return _HOURLY_MOOD.get(current_brt_hour(), "fofura")


def _scene_weights() -> dict[str, float]:
    """Le _data/scene_performance.json (gerado por collect_analytics.py a
    partir de views reais por cena). Ausente/corrompido = sem preferencia."""
    try:
        data = json.loads(_SCENE_PERFORMANCE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
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
