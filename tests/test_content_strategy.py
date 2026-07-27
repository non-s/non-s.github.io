"""Testes para content_strategy.py."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import patch

from utils import content_strategy


def _mock_now(utc_hour: int):
    """Mock de datetime.now(UTC) fixado numa hora UTC especifica."""
    return patch(
        "utils.content_strategy.datetime",
        **{"now.return_value": datetime(2026, 7, 25, utc_hour, 0, 0, tzinfo=UTC)},
    )


class TestCurrentBrtHour:
    def test_converts_utc_to_brt_minus_3(self):
        # 15:00 UTC - 3h = 12:00 BRT
        with _mock_now(15):
            assert content_strategy.current_brt_hour() == 12

    def test_wraps_around_midnight(self):
        # 1:00 UTC - 3h = 22:00 BRT do dia anterior
        with _mock_now(1):
            assert content_strategy.current_brt_hour() == 22


class TestMoodForNow:
    def test_morning_is_diversao(self):
        # 6h-12h BRT = 9h-15h UTC
        with _mock_now(10):  # 7h BRT
            assert content_strategy.mood_for_now() == "diversao"

    def test_afternoon_is_fofura(self):
        # 12h-18h BRT = 15h-21h UTC
        with _mock_now(16):  # 13h BRT
            assert content_strategy.mood_for_now() == "fofura"

    def test_night_is_relax(self):
        # 18h-24h e 0h-6h BRT = relax
        with _mock_now(22):  # 19h BRT
            assert content_strategy.mood_for_now() == "relax"


class TestSceneForMood:
    def test_returns_scene_from_correct_category(self):
        for mood, scenes in content_strategy.SCENE_CATEGORIES.items():
            for _ in range(10):  # random.choice - checa varias vezes
                assert content_strategy.scene_for_mood(mood) in scenes

    def test_unknown_mood_falls_back_to_fofura(self):
        scene = content_strategy.scene_for_mood("mood-que-nao-existe")
        assert scene in content_strategy.SCENE_CATEGORIES["fofura"]


class TestSceneWeights:
    """scene_for_mood pondera pela performance real (scene_performance.json,
    gerado por collect_analytics.py) quando ela existe, sem nunca excluir
    nenhuma cena da categoria."""

    def _isolate(self, tmp_path, monkeypatch):
        perf_file = tmp_path / "scene_performance.json"
        monkeypatch.setattr(content_strategy, "_SCENE_PERFORMANCE_FILE", perf_file)
        return perf_file

    def test_no_performance_file_falls_back_to_uniform(self, tmp_path, monkeypatch):
        self._isolate(tmp_path, monkeypatch)
        assert content_strategy._scene_weights() == {}

    def test_reads_weights_from_file(self, tmp_path, monkeypatch):
        perf_file = self._isolate(tmp_path, monkeypatch)
        perf_file.write_text(json.dumps({"cat": 2.0}), encoding="utf-8")

        assert content_strategy._scene_weights() == {"cat": 2.0}

    def test_corrupted_file_falls_back_to_empty(self, tmp_path, monkeypatch):
        perf_file = self._isolate(tmp_path, monkeypatch)
        perf_file.write_text("not json", encoding="utf-8")

        assert content_strategy._scene_weights() == {}

    def test_scene_for_mood_still_stays_within_category_when_weighted(self, tmp_path, monkeypatch):
        perf_file = self._isolate(tmp_path, monkeypatch)
        perf_file.write_text(json.dumps({"sleepy cat": 2.5, "sleepy dog": 0.4}), encoding="utf-8")

        for _ in range(20):
            assert content_strategy.scene_for_mood("relax") in content_strategy.SCENE_CATEGORIES["relax"]

    def test_heavily_weighted_scene_is_picked_far_more_often(self, tmp_path, monkeypatch):
        import random
        random.seed(42)
        perf_file = self._isolate(tmp_path, monkeypatch)
        perf_file.write_text(json.dumps({"sleepy cat": 2.5, "sleepy dog": 0.4}), encoding="utf-8")

        results = [content_strategy.scene_for_mood("relax") for _ in range(200)]
        assert results.count("sleepy cat") > results.count("sleepy dog")
