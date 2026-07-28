"""utils/slot_optimizer.py — escolha ativa de cena/padrao por previsao.

O gerador de Shorts/horizontais sortearva cenas/padroes uniformemente (ou
ponderado por performance historica passiva). Este modulo usa o modelo
preditivo em _data/view_predictor.json para escolher, entre as cenas e
padroes candidatos do mood atual, a combinacao com maior previsao de views
para o horario de publicacao - otimizacao ativa em vez de descritiva.

Fallback seguro: sem modelo treinado (n_samples==0) ou sem pesos, cai no
comportamento legado (random ponderado por scene_performance.json via
content_strategy.scene_for_mood).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.content_strategy import SCENE_CATEGORIES  # noqa: F401

log = logging.getLogger(__name__)


def best_title_pattern_for_scene(scene: str, hour: int, day_of_week: int) -> str | None:
    """Retorna o padrao de titulo com maior previsao de views para a cena
    dada no horario/dia. Sem modelo, retorna None (caller usa fallback).
    """
    try:
        from scripts.predict_views import load_model, predict_views
    except Exception:
        return None

    model = load_model()
    if not model or not model.get("weights") or model.get("n_samples", 0) == 0:
        return None

    patterns = model.get("title_patterns") or []
    if not patterns:
        return None

    best_pattern = None
    best_score = -1.0
    for pattern in patterns:
        try:
            score = predict_views(scene, pattern, hour, day_of_week)
        except Exception:
            continue
        if score > best_score:
            best_score = score
            best_pattern = pattern

    if best_pattern and best_score > 0:
        log.info(
            "Padrao otimo para cena=%s slot=%02dh: %s (views previstos=%.0f)",
            scene, hour, best_pattern, best_score,
        )
        return best_pattern
    return None


def best_scene_for_mood(mood: str, hour: int, day_of_week: int) -> str | None:
    """Retorna a cena (do mood dado) com maior previsao de views no slot.

    Sem modelo treinado ou sem pesos, retorna None para que o caller caia
    no comportamento legado (content_strategy.scene_for_mood, que pondera
    por scene_performance.json).
    """
    try:
        from scripts.predict_views import load_model, predict_views
    except Exception:
        return None

    model = load_model()
    if not model or not model.get("weights") or model.get("n_samples", 0) == 0:
        return None

    scenes_model = model.get("scenes") or []
    if not scenes_model:
        return None

    # Intersecao: cenas do mood atual que tambem existem no modelo.
    from utils.content_strategy import SCENE_CATEGORIES
    mood_scenes = SCENE_CATEGORIES.get(mood, SCENE_CATEGORIES["fofura"])
    candidates = [s for s in mood_scenes if s in scenes_model]
    if not candidates:
        return None

    patterns = model.get("title_patterns") or [""]
    best_scene = None
    best_score = -1.0
    for scene in candidates:
        # Media sobre os padroes (nao sabemos qual padrao sera usado ainda;
        # otimiza a cena isoladamente).
        scores = []
        for pattern in patterns:
            try:
                scores.append(predict_views(scene, pattern, hour, day_of_week))
            except Exception:
                continue
        avg = sum(scores) / len(scores) if scores else 0.0
        if avg > best_score:
            best_score = avg
            best_scene = scene

    if best_scene and best_score > 0:
        log.info(
            "Cena otima para mood=%s slot=%02dh: %s (views previstos media=%.0f)",
            mood, hour, best_scene, best_score,
        )
        return best_scene
    return None


def optimized_scene_and_pattern(
    mood: str, fallback_scene: str, hour: int, day_of_week: int,
) -> tuple[str, str | None]:
    """Retorna (scene, title_pattern) otimizados por previsao.

    Primeiro escolhe a melhor cena do mood; depois o melhor padrao para
    essa cena. Se nada for possivel (sem modelo), retorna (fallback_scene, None)
    e o caller usa o comportamento legado para ambos.
    """
    scene = best_scene_for_mood(mood, hour, day_of_week) or fallback_scene
    pattern = best_title_pattern_for_scene(scene, hour, day_of_week)
    return scene, pattern
