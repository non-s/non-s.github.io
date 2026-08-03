"""tests/test_slot_optimizer.py — cobertura para utils/slot_optimizer.py.

Mocka scripts.predict_views para testar caminhos com/sem modelo e
fallback para content_strategy.scene_for_mood.
"""

from __future__ import annotations

import pytest

from utils import slot_optimizer


@pytest.fixture(autouse=True)
def _reset_content_strategy():
    """Garante SCENE_CATEGORIES estavel entre testes."""
    from utils.content_strategy import SCENE_CATEGORIES

    original = dict(SCENE_CATEGORIES)
    yield
    SCENE_CATEGORIES.clear()
    SCENE_CATEGORIES.update(original)


def test_best_title_pattern_no_model(monkeypatch):
    """Sem modelo, best_title_pattern_for_scene retorna None."""
    monkeypatch.setattr(slot_optimizer, "best_title_pattern_for_scene", lambda scene, hour, dow: None)
    assert slot_optimizer.best_title_pattern_for_scene("cat", 12, 0) is None


def test_best_scene_no_model(monkeypatch):
    """Sem modelo, best_scene_for_mood retorna None."""
    monkeypatch.setattr(slot_optimizer, "best_scene_for_mood", lambda mood, hour, dow: None)
    assert slot_optimizer.best_scene_for_mood("fofura", 12, 0) is None


def test_best_title_pattern_with_model(tmp_path, monkeypatch):
    """Com modelo valido, escolhe o padrao de maior score."""
    fake_model = {
        "weights": [1.0],
        "n_samples": 10,
        "scenes": ["cat", "dog"],
        "title_patterns": ["A", "B"],
    }

    def fake_load_model():
        return fake_model

    def fake_predict(scene, pattern, hour, day_of_week):
        return {"A": 10.0, "B": 20.0}[pattern]

    monkeypatch.setattr("scripts.predict_views.load_model", fake_load_model)
    monkeypatch.setattr("scripts.predict_views.predict_views", fake_predict)
    result = slot_optimizer.best_title_pattern_for_scene("cat", 10, 1)
    assert result == "B"


def test_best_scene_for_mood_with_model(tmp_path, monkeypatch):
    """Com modelo valido, escolhe a cena de maior media sobre padroes."""
    from utils.content_strategy import SCENE_CATEGORIES

    SCENE_CATEGORIES["fofura"] = ["cat", "dog"]
    fake_model = {
        "weights": [1.0],
        "n_samples": 10,
        "scenes": ["cat", "dog"],
        "title_patterns": ["A"],
    }

    def fake_load_model():
        return fake_model

    def fake_predict(scene, pattern, hour, day_of_week):
        return {"cat": 5.0, "dog": 15.0}[scene]

    monkeypatch.setattr("scripts.predict_views.load_model", fake_load_model)
    monkeypatch.setattr("scripts.predict_views.predict_views", fake_predict)
    result = slot_optimizer.best_scene_for_mood("fofura", 10, 1)
    assert result == "dog"


def test_optimized_scene_and_pattern_uses_fallback(monkeypatch):
    """Sem modelo retorna fallback_scene e pattern None."""
    monkeypatch.setattr(slot_optimizer, "best_scene_for_mood", lambda mood, hour, dow: None)
    monkeypatch.setattr(slot_optimizer, "best_title_pattern_for_scene", lambda scene, hour, dow: None)
    scene, pattern = slot_optimizer.optimized_scene_and_pattern("fofura", "cat", 12, 0)
    assert scene == "cat"
    assert pattern is None


def test_best_scene_for_mood_mood_not_in_categories(monkeypatch):
    """Mood inexistente usa fallback 'fofura' e retorna None sem modelo."""
    from utils.content_strategy import SCENE_CATEGORIES

    monkeypatch.setattr("scripts.predict_views.load_model", lambda: None)
    SCENE_CATEGORIES["fofura"] = ["cat"]
    assert slot_optimizer.best_scene_for_mood("unknown", 10, 1) is None
