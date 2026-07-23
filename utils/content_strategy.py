"""
utils/content_strategy.py — calendário editorial, SEO e estratégia de conteúdo Pata Jazz.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

# Melhores horários observados para o nicho (BRT = UTC-3)
PUBLISH_SLOTS = {
    "short": ["07:30", "11:30", "18:30"],      # Shorts: manhã, almoço, noite
    "horizontal": ["19:00", "20:30", "21:30"],  # Longos: pico noite
    "live": ["08:00", "14:00", "19:00"],       # Lives: manhã, tarde, noite
}

# Categorias de cenas com variação sazonal
SCENE_CATEGORIES: dict[str, list[str]] = {
    "fofura": ["cat", "kitten", "puppy", "dog", "sleepy cat"],
    "diversao": ["playful dog", "cat playing", "puppy playing", "dog running"],
    "relax": ["sleepy cat", "sleepy dog", "cat relaxing", "dog relaxing"],
}


def best_slot_for(kind: str, weekday: int | None = None) -> str:
    """Retorna o melhor horário de publicação para o tipo de conteúdo."""
    slots = PUBLISH_SLOTS.get(kind, ["12:00"])
    if weekday is None:
        weekday = datetime.now(timezone.utc).weekday()
    # Finais de semana: empurra para horários mais tarde
    if weekday >= 5:
        return slots[-1]
    return slots[0]


def pick_scene_category(mood: str = "") -> str:
    """Escolhe uma categoria de cena baseada no mood."""
    if mood and mood in SCENE_CATEGORIES:
        return mood
    return random.choice(list(SCENE_CATEGORIES.keys()))


def weekly_calendar() -> list[dict]:
    """Gera uma sugestão de calendário semanal equilibrado."""
    return [
        {"day": "Seg", "type": "short", "slot": best_slot_for("short", 0), "mood": "fofura"},
        {"day": "Ter", "type": "short", "slot": best_slot_for("short", 1), "mood": "relax"},
        {"day": "Qua", "type": "horizontal", "slot": best_slot_for("horizontal", 2), "mood": "fofura"},
        {"day": "Qui", "type": "short", "slot": best_slot_for("short", 3), "mood": "diversao"},
        {"day": "Sex", "type": "horizontal", "slot": best_slot_for("horizontal", 4), "mood": "diversao"},
        {"day": "Sab", "type": "live", "slot": best_slot_for("live", 5), "mood": "relax"},
        {"day": "Dom", "type": "short", "slot": best_slot_for("short", 6), "mood": "fofura"},
    ]
