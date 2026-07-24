"""
utils/content_strategy.py — calendário editorial, SEO e estratégia de conteúdo Pata Jazz.

Mapeia horário do dia -> mood para escolher cenas apropriadas:
  Manhã (06-12): diversao (energia, gatos brincando)
  Tarde  (12-18): fofura (fofo, gatinhos dormindo)
  Noite  (18-24): relax (relaxamento, cachorros dormindo)
  Madrugada (00-06): relax
"""

from __future__ import annotations

import random
from datetime import datetime, timezone, timedelta

# Janelas de publicação (BRT = UTC-3)
PUBLISH_SLOTS = {
    "short": ["07:00", "13:00", "18:00", "22:00"],
    "horizontal": ["10:00"],
    "live": ["19:00"],
}

# Categorias de cenas
SCENE_CATEGORIES: dict[str, list[str]] = {
    "fofura": ["cat", "kitten", "puppy", "dog", "sleepy cat"],
    "diversao": ["playful dog", "cat playing", "puppy playing", "dog relaxing"],
    "relax": ["sleepy cat", "sleepy dog", "cat relaxing", "dog relaxing"],
}

# Mapeamento de faixa horaria (BRT) -> mood
# Manha = energia/diversao, Tarde = fofura, Noite = relax
_HOURLY_MOOD: dict[int, str] = {}
for h in range(24):
    if 6 <= h < 12:
        _HOURLY_MOOD[h] = "diversao"
    elif 12 <= h < 18:
        _HOURLY_MOOD[h] = "fofura"
    else:
        _HOURLY_MOOD[h] = "relax"


def current_brt_hour() -> int:
    """Retorna a hora atual em BRT (UTC-3)."""
    return (datetime.now(timezone.utc) + timedelta(hours=-3)).hour


def mood_for_now() -> str:
    """Retorna o mood apropriado para a hora atual (BRT)."""
    return _HOURLY_MOOD.get(current_brt_hour(), "fofura")


def best_slot_for(kind: str, weekday: int | None = None) -> str:
    """Retorna o melhor horário de publicação para o tipo de conteúdo."""
    slots = PUBLISH_SLOTS.get(kind, ["12:00"])
    if weekday is None:
        weekday = datetime.now(timezone.utc).weekday()
    if weekday >= 5:
        return slots[-1]
    return slots[0]


def pick_scene_category(mood: str = "") -> str:
    """Escolhe uma categoria de cena baseada no mood."""
    if mood and mood in SCENE_CATEGORIES:
        return mood
    return random.choice(list(SCENE_CATEGORIES.keys()))


def scene_for_mood(mood: str) -> str:
    """Retorna uma cena especifica (ex: 'sleepy cat') para o mood dado."""
    scenes = SCENE_CATEGORIES.get(mood, SCENE_CATEGORIES["fofura"])
    return random.choice(scenes)


def weekly_calendar() -> list[dict]:
    """Gera uma sugestão de calendário semanal equilibrado."""
    days = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
    moods_cycle = ["fofura", "relax", "fofura", "diversao", "diversao", "relax", "fofura"]
    return [
        {"day": days[i], "type": "short", "slot": best_slot_for("short", i), "mood": moods_cycle[i]}
        for i in range(7)
    ]