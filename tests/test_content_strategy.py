"""Testes para content_strategy.py."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
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

    def test_custom_offset_via_env(self, monkeypatch):
        # offset customizado de -5h: 15:00 UTC - 5h = 10:00
        monkeypatch.setenv("BRT_OFFSET_HOURS", "-5")
        with _mock_now(15):
            assert content_strategy.current_brt_hour() == 10


class TestMoodForNow:
    def test_morning_is_focus(self):
        # 6h-12h BRT = 9h-15h UTC
        with _mock_now(10):  # 7h BRT
            assert content_strategy.mood_for_now() == "focus"

    def test_afternoon_is_ambient(self):
        # 12h-18h BRT = 15h-21h UTC
        with _mock_now(16):  # 13h BRT
            assert content_strategy.mood_for_now() == "ambient"

    def test_night_is_relax(self):
        # 18h-24h e 0h-6h BRT = relax
        with _mock_now(22):  # 19h BRT
            assert content_strategy.mood_for_now() == "relax"


class TestSceneForMood:
    def test_returns_scene_from_correct_category(self):
        for mood, scenes in content_strategy.SCENE_CATEGORIES.items():
            for _ in range(10):  # random.choice - checa varias vezes
                assert content_strategy.scene_for_mood(mood) in scenes

    def test_unknown_mood_falls_back_to_ambient(self):
        scene = content_strategy.scene_for_mood("mood-que-nao-existe")
        assert scene in content_strategy.SCENE_CATEGORIES["ambient"]


class TestMinQualityScoreForSlot:
    """Frente E — min_quality_score_for_slot: threshold configurable por
    horario (manha mais exigente, madrugada mais tolerante)."""

    def test_morning_requires_higher_score(self):
        for hour in range(6, 12):
            assert content_strategy.min_quality_score_for_slot(hour) == 0.82

    def test_late_night_is_lenient(self):
        for hour in [22, 23, 0, 1, 2, 3, 4, 5]:
            assert content_strategy.min_quality_score_for_slot(hour) == 0.75

    def test_afternoon_evening_uses_default(self):
        for hour in list(range(12, 18)) + [18, 19, 20, 21]:
            assert content_strategy.min_quality_score_for_slot(hour) == 0.78

    def test_morning_higher_than_night(self):
        assert content_strategy.min_quality_score_for_slot(9) > content_strategy.min_quality_score_for_slot(3)


class TestSceneWeights:
    """scene_for_mood pondera pela performance real (scene_performance.json,
    gerado por collect_analytics.py) quando ela existe, sem nunca excluir
    nenhuma cena da categoria."""

    def _isolate(self, tmp_path, monkeypatch):
        perf_file = tmp_path / "scene_performance.json"
        monkeypatch.setattr(content_strategy, "_scene_performance_file", lambda: perf_file)
        return perf_file

    def test_no_performance_file_falls_back_to_uniform(self, tmp_path, monkeypatch):
        self._isolate(tmp_path, monkeypatch)
        assert content_strategy._scene_weights() == {}

    def test_reads_weights_from_file(self, tmp_path, monkeypatch):
        perf_file = self._isolate(tmp_path, monkeypatch)
        perf_file.write_text(json.dumps({"dark liquid wire": 2.0}), encoding="utf-8")

        assert content_strategy._scene_weights() == {"dark liquid wire": 2.0}

    def test_corrupted_file_falls_back_to_empty(self, tmp_path, monkeypatch):
        perf_file = self._isolate(tmp_path, monkeypatch)
        perf_file.write_text("not json", encoding="utf-8")

        assert content_strategy._scene_weights() == {}

    def test_scene_for_mood_still_stays_within_category_when_weighted(self, tmp_path, monkeypatch):
        perf_file = self._isolate(tmp_path, monkeypatch)
        perf_file.write_text(json.dumps({"dark liquid wire": 2.5, "nebula cloud": 0.4}), encoding="utf-8")

        for _ in range(20):
            assert content_strategy.scene_for_mood("relax") in content_strategy.SCENE_CATEGORIES["relax"]

    def test_heavily_weighted_scene_is_picked_far_more_often(self, tmp_path, monkeypatch):
        import random

        random.seed(42)
        perf_file = self._isolate(tmp_path, monkeypatch)
        perf_file.write_text(json.dumps({"dark liquid wire": 2.5, "nebula cloud": 0.4}), encoding="utf-8")

        results = [content_strategy.scene_for_mood("relax") for _ in range(200)]
        assert results.count("dark liquid wire") > results.count("nebula cloud")


class TestViralBoostedScenes:
    """viral_boosted_scenes: le viral_signals.json e retorna scene -> boost
    (2.0) para cenas que apareceram em virais recentes (ultimos 14 dias).
    Conservador: so cenas nomeadas e com detected_at dentro da janela entram."""

    def _isolate(self, tmp_path, monkeypatch):
        viral_file = tmp_path / "viral_signals.json"
        monkeypatch.setattr(content_strategy, "_viral_signals_file", lambda: viral_file)
        return viral_file

    def _now_iso(self):
        return datetime.now(UTC).isoformat()

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        self._isolate(tmp_path, monkeypatch)
        assert content_strategy.viral_boosted_scenes() == {}

    def test_corrupted_file_returns_empty(self, tmp_path, monkeypatch):
        viral_file = self._isolate(tmp_path, monkeypatch)
        viral_file.write_text("not json", encoding="utf-8")
        assert content_strategy.viral_boosted_scenes() == {}

    def test_recent_viral_scene_gets_boost(self, tmp_path, monkeypatch):
        viral_file = self._isolate(tmp_path, monkeypatch)
        viral_file.write_text(
            json.dumps(
                [
                    {
                        "scene": "dark liquid wire",
                        "title_pattern": "p",
                        "views": 5000,
                        "viral_factor": 50.0,
                        "detected_at": self._now_iso(),
                    },
                ]
            ),
            encoding="utf-8",
        )

        boosted = content_strategy.viral_boosted_scenes()
        assert boosted == {"dark liquid wire": content_strategy._VIRAL_BOOST}

    def test_old_viral_outside_window_is_ignored(self, tmp_path, monkeypatch):
        viral_file = self._isolate(tmp_path, monkeypatch)
        old = (datetime.now(UTC) - timedelta(days=20)).isoformat()
        viral_file.write_text(
            json.dumps(
                [
                    {"scene": "dark liquid wire", "detected_at": old},
                ]
            ),
            encoding="utf-8",
        )

        assert content_strategy.viral_boosted_scenes() == {}

    def test_viral_without_scene_is_ignored(self, tmp_path, monkeypatch):
        viral_file = self._isolate(tmp_path, monkeypatch)
        viral_file.write_text(
            json.dumps(
                [
                    {"scene": "", "detected_at": self._now_iso()},
                ]
            ),
            encoding="utf-8",
        )

        assert content_strategy.viral_boosted_scenes() == {}

    def test_viral_without_detected_at_is_ignored(self, tmp_path, monkeypatch):
        viral_file = self._isolate(tmp_path, monkeypatch)
        viral_file.write_text(
            json.dumps(
                [
                    {"scene": "dark liquid wire"},  # sem detected_at
                ]
            ),
            encoding="utf-8",
        )

        assert content_strategy.viral_boosted_scenes() == {}

    def test_multiple_recent_virals_same_scene_collapse_to_single_boost(self, tmp_path, monkeypatch):
        viral_file = self._isolate(tmp_path, monkeypatch)
        now = self._now_iso()
        viral_file.write_text(
            json.dumps(
                [
                    {"scene": "dark liquid wire", "detected_at": now},
                    {"scene": "dark liquid wire", "detected_at": now},
                    {"scene": "nebula cloud", "detected_at": now},
                ]
            ),
            encoding="utf-8",
        )

        boosted = content_strategy.viral_boosted_scenes()
        assert boosted == {
            "dark liquid wire": content_strategy._VIRAL_BOOST,
            "nebula cloud": content_strategy._VIRAL_BOOST,
        }


class TestSceneForMoodViralBoostIntegration:
    """scene_for_mood aplica o boost viral multiplicando o peso da cena -
    conservador: so se a cena ja esta na lista do mood, e multiplicando
    (nao substituindo nem criando peso do nada)."""

    def test_viral_boost_increases_pick_probability(self, tmp_path, monkeypatch):
        import random

        random.seed(42)
        perf_file = tmp_path / "scene_performance.json"
        monkeypatch.setattr(content_strategy, "_scene_performance_file", lambda: perf_file)
        viral_file = tmp_path / "viral_signals.json"
        monkeypatch.setattr(content_strategy, "_viral_signals_file", lambda: viral_file)
        # Pesos iguais pra ambas as cenas; so o boost diferencia.
        perf_file.write_text(json.dumps({"dark liquid wire": 1.0, "nebula cloud": 1.0}), encoding="utf-8")
        viral_file.write_text(
            json.dumps(
                [
                    {"scene": "dark liquid wire", "detected_at": datetime.now(UTC).isoformat()},
                ]
            ),
            encoding="utf-8",
        )

        results = [content_strategy.scene_for_mood("relax") for _ in range(200)]
        # dark liquid wire tem peso 1.0 * boost(2.0) = 2.0 vs 1.0 -> escolhido ~2x mais.
        assert results.count("dark liquid wire") > results.count("nebula cloud")

    def test_viral_boost_does_not_introduce_scene_outside_mood_list(self, tmp_path, monkeypatch):
        """Boost em cena fora da categoria do mood nao injeta ela na escolha."""
        perf_file = tmp_path / "scene_performance.json"
        monkeypatch.setattr(content_strategy, "_scene_performance_file", lambda: perf_file)
        viral_file = tmp_path / "viral_signals.json"
        monkeypatch.setattr(content_strategy, "_viral_signals_file", lambda: viral_file)
        viral_file.write_text(
            json.dumps(
                [
                    # "calm wireframe flow" esta na categoria focus, nao em relax.
                    {"scene": "calm wireframe flow", "detected_at": datetime.now(UTC).isoformat()},
                ]
            ),
            encoding="utf-8",
        )

        for _ in range(50):
            assert content_strategy.scene_for_mood("relax") in content_strategy.SCENE_CATEGORIES["relax"]

    def test_viral_boost_with_no_performance_weights_still_picks_from_mood(self, tmp_path, monkeypatch):
        """Sem scene_performance.json mas com virais, o boost ainda aplica
        (peso base 1.0 * boost) - a cena viralizada fica mais provavel."""
        import random

        random.seed(7)
        monkeypatch.setattr(content_strategy, "_scene_performance_file", lambda: tmp_path / "missing_perf.json")
        viral_file = tmp_path / "viral_signals.json"
        monkeypatch.setattr(content_strategy, "_viral_signals_file", lambda: viral_file)
        viral_file.write_text(
            json.dumps(
                [
                    {"scene": "dark liquid wire", "detected_at": datetime.now(UTC).isoformat()},
                ]
            ),
            encoding="utf-8",
        )

        results = [content_strategy.scene_for_mood("relax") for _ in range(200)]
        assert results.count("dark liquid wire") > results.count("nebula cloud")
