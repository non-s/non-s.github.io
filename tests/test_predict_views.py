"""Testes para scripts/predict_views.py — analytics preditivo.

Cobre o treino com dados sintéticos, o fallback de média geral sem dados,
a construção das features one-hot e a leitura do modelo salvo em disco.
"""
import json
import math
from datetime import UTC, datetime, timedelta

import scripts.predict_views as pv


def _isolate(tmp_path, monkeypatch):
    """Isola todos os arquivos de _data/ lidos pelo módulo para tmp_path."""
    monkeypatch.setattr(pv, "DATA_DIR", tmp_path)
    monkeypatch.setattr(pv, "ANALYTICS_FILE", tmp_path / "analytics.json")
    monkeypatch.setattr(pv, "VIDEO_TAGS_FILE", tmp_path / "video_tags.json")
    monkeypatch.setattr(pv, "MODEL_FILE", tmp_path / "view_predictor.json")


def _write_analytics_with_tags(tmp_path, *, videos):
    """Grava analytics.json + video_tags.json a partir de uma lista de
    descrições: (video_id, scene, title_pattern, published_at_iso, views)."""
    all_videos = [
        {"video_id": vid, "published_at": pub, "views": views, "likes": 0, "comments": 0}
        for (vid, _scene, _pat, pub, views) in videos
    ]
    (tmp_path / "analytics.json").write_text(
        json.dumps({"total_videos": len(all_videos), "total_views": sum(v[4] for v in videos),
                    "all_videos": all_videos}),
        encoding="utf-8",
    )
    tags = {
        vid: {"scene": scene, "title_pattern": pat, "uploaded_at": pub}
        for (vid, scene, pat, pub, _views) in videos
    }
    (tmp_path / "video_tags.json").write_text(json.dumps(tags), encoding="utf-8")


class TestFeaturizeOneHot:
    def test_one_hot_scene_and_title_pattern(self):
        scenes = ["cat", "dog"]
        patterns = ["pat-a", "pat-b"]
        vec = pv._featurize("cat", "pat-a", hour=10, day_of_week=0,
                            scenes=scenes, title_patterns=patterns)
        # bias + (scenes-1) + (patterns-1) + hour + dow = 1+1+1+1+1 = 5.
        # Primeira cena (cat) e primeiro padrão (pat-a) são a referência
        # (dummy variable trap) — não ganham coluna; suas contribuições
        # ficam implícitas no bias.
        assert vec[0] == 1.0
        assert vec[1:2] == [0.0]  # scene:dog (cat é a referência)
        assert vec[2:3] == [0.0]  # pattern:pat-b (pat-a é a referência)
        assert vec[3] == 10.0
        assert vec[4] == 0.0

    def test_unknown_scene_yields_zero_one_hot(self):
        # "cat" é a referência (omitida); "alien" não está no vocabulário
        # -> todas as colunas de cena (dog) são 0.
        vec = pv._featurize("alien", "pat-a", 0, 0, scenes=["cat", "dog"], title_patterns=["pat-a", "pat-b"])
        assert vec[1] == 0.0  # scene:dog
        assert vec[2] == 0.0  # pattern:pat-b (pat-a é referência)

    def test_hour_and_day_are_scalar(self):
        vec = pv._featurize("cat", "pat", hour=23, day_of_week=6,
                            scenes=["cat"], title_patterns=["pat"])
        # bias + 0 scene + 0 pattern + hour + dow = 3 (referências únicas).
        assert vec[-2] == 23.0
        assert vec[-1] == 6.0

    def test_case_insensitive_scene(self):
        # 2 cenas; cat é referência. dog (segunda) ganha coluna 1.
        vec = pv._featurize("DOG", "pat", 0, 0, scenes=["cat", "dog"], title_patterns=["pat"])
        assert vec[1] == 1.0  # scene:dog


class TestSolveNormalEquation:
    def test_recovers_linear_weights(self):
        # y = 10 + 2*x1 + 3*x2, com x2 = x1^2 (não colinear com x1).
        X = [[1.0, float(i), float(i * i)] for i in range(1, 11)]
        y = [10.0 + 2.0 * i + 3.0 * (i * i) for i in range(1, 11)]
        w = pv._solve_normal_equation(X, y)
        assert w is not None
        assert math.isclose(w[0], 10.0, abs_tol=1e-3)
        assert math.isclose(w[1], 2.0, abs_tol=1e-3)
        assert math.isclose(w[2], 3.0, abs_tol=1e-3)

    def test_singular_system_with_ridge_still_solves(self):
        """Coluna perfeitamente colinear com o bias seria singular no OLS
        puro, mas o ridge (λ=1e-6) regulariza e devolve uma solução
        aproximada — evita o fallback de média geral em dados reais onde
        a colinearidade é inevitável (cenas/padrões correlacionados)."""
        X = [[1.0, 1.0], [1.0, 1.0], [1.0, 1.0]]
        y = [1.0, 2.0, 3.0]
        w = pv._solve_normal_equation(X, y)
        assert w is not None
        assert len(w) == 2

    def test_empty_returns_none(self):
        assert pv._solve_normal_equation([], []) is None


class TestTrainModelSynthetic:
    def test_trains_and_saves_model(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        # 2 cenas E 2 padrões alternados (one-hot não colinear com bias)
        # + horas variadas (escalar não constante).
        now = datetime.now(UTC)
        vids = []
        for i in range(20):
            pub = (now - timedelta(days=100, hours=i)).isoformat()
            scene = "cat" if i % 2 == 0 else "dog"
            pat = "pat-a" if i % 3 != 0 else "pat-b"
            vids.append((f"vid{i}", scene, pat, pub, 100 + i))
        _write_analytics_with_tags(tmp_path, videos=vids)

        model = pv.train_model()

        assert model["n_samples"] == 20
        assert model["scenes"] == ["cat", "dog"]
        assert model["title_patterns"] == ["pat-a", "pat-b"]
        assert len(model["weights"]) == len(model["features"])
        assert model["features"][0] == "bias"
        # cat (primeira) é a referência — fica implícita no bias e não
        # ganha coluna própria (dummy variable trap).
        assert "scene:dog" in model["features"]
        assert "title_pattern:pat-b" in model["features"]
        assert "hour_of_day" in model["features"]

    def test_model_predicts_approximately_correct(self, tmp_path, monkeypatch):
        """Com duas cenas distintas com views muito diferentes, a previsão
        para a cena de alto desempenho deve ser maior que a de baixo.

        Cena e padrão variam independentemente (cat aparece com pat-a E
        pat-b, dog idem) para evitar colinearidade perfeita entre as
        colunas one-hot — o modelo ridge resolve, mas sem variação a
        contribuição de cena e padrão é indistinguível."""
        _isolate(tmp_path, monkeypatch)
        now = datetime.now(UTC)
        high_videos = []
        low_videos = []
        for i in range(10):
            pub = (now - timedelta(days=100, hours=i)).isoformat()
            # cat sempre alto, com padrões alternados
            high_videos.append((f"high{i}", "cat", "pat-a" if i % 2 else "pat-b", pub, 10000))
        for i in range(10):
            pub = (now - timedelta(days=100, hours=i + 10)).isoformat()
            low_videos.append((f"low{i}", "dog", "pat-a" if i % 2 else "pat-b", pub, 100))
        _write_analytics_with_tags(tmp_path, videos=high_videos + low_videos)

        model = pv.train_model()
        pv.save_model(model)

        high_pred = pv.predict_views("cat", "pat-a", hour=10, day_of_week=0)
        low_pred = pv.predict_views("dog", "pat-a", hour=10, day_of_week=0)
        assert high_pred > low_pred
        # proxy: y = views/100*7 = views*0.07 -> ~700 para high, ~7 para low
        assert high_pred > 100
        assert low_pred < 50

    def test_predict_views_reads_saved_model(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        now = datetime.now(UTC)
        vids = []
        for i in range(20):
            pub = (now - timedelta(days=100, hours=i)).isoformat()
            scene = "cat" if i % 2 == 0 else "dog"
            pat = "pat-a" if i % 3 != 0 else "pat-b"
            vids.append((f"vid{i}", scene, pat, pub, 100 + i))
        _write_analytics_with_tags(tmp_path, videos=vids)

        pv.save_model(pv.train_model())
        # predict_views() lê MODEL_FILE em disco (não variável em memória).
        pred = pv.predict_views("cat", "pat-a", hour=10, day_of_week=0)
        assert pred > 0

    def test_predict_returns_overall_avg_when_model_empty(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        # Modelo "vazio" salvo manualmente: n_samples=0, weights=[].
        pv.save_model({
            "features": [], "weights": [], "scenes": [], "title_patterns": [],
            "overall_avg": 42.0, "n_samples": 0,
        })
        assert pv.predict_views("cat", "pat", 10, 0) == 42.0

    def test_predict_returns_zero_when_no_model_file(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        # Nenhum arquivo de modelo em disco.
        assert pv.predict_views("cat", "pat", 10, 0) == 0.0


class TestNoDataFallback:
    def test_no_samples_returns_empty_model_with_zero_avg(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        (tmp_path / "analytics.json").write_text(
            json.dumps({"total_videos": 0, "all_videos": []}), encoding="utf-8")
        (tmp_path / "video_tags.json").write_text("{}", encoding="utf-8")

        model = pv.train_model()

        assert model["n_samples"] == 0
        assert model["weights"] == []
        assert model["overall_avg"] == 0.0
        assert model["scenes"] == []

    def test_no_video_tags_returns_empty_model(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        (tmp_path / "analytics.json").write_text(
            json.dumps({"total_videos": 5, "all_videos": [
                {"video_id": "v1", "views": 100, "published_at": "2025-01-01"}
            ]}), encoding="utf-8")
        # video_tags.json ausente.

        model = pv.train_model()
        assert model["n_samples"] == 0

    def test_video_too_recent_skipped(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        now = datetime.now(UTC)
        # publicado há 0.5 dias -> dias_desde_upload < 1.0 -> descartado.
        pub = (now - timedelta(hours=12)).isoformat()
        _write_analytics_with_tags(tmp_path, videos=[("v1", "cat", "pat", pub, 1000)])

        model = pv.train_model()
        assert model["n_samples"] == 0


class TestNextCronSlots:
    def test_returns_four_slots(self, monkeypatch):
        now = datetime(2026, 7, 27, 9, 0, tzinfo=UTC)  # 09:00 UTC, seg
        slots = pv.next_cron_slots(now=now, n=4)
        assert len(slots) == 4
        # Próximo slot: 10:00 (hora 10), segunda (weekday 0).
        assert slots[0] == (10, 0)
        assert slots[1] == (16, 0)
        assert slots[2] == (21, 0)
        # 01:00 do dia seguinte: 1, ter (weekday 1)
        assert slots[3] == (1, 1)

    def test_late_night_wraps_to_next_day(self):
        now = datetime(2026, 7, 27, 23, 30, tzinfo=UTC)  # depois do 21:00
        slots = pv.next_cron_slots(now=now, n=2)
        assert slots[0] == (1, 1)  # 01:00 ter
        assert slots[1] == (10, 1)  # 10:00 ter


class TestMain:
    def test_main_saves_model(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        monkeypatch.setattr(pv, "configure_logging", lambda: None)
        now = datetime.now(UTC)
        vids = [
            (f"vid{i}", "cat", "pat-a", (now - timedelta(days=100)).isoformat(), 100 + i)
            for i in range(3)
        ]
        _write_analytics_with_tags(tmp_path, videos=vids)

        assert pv.main() == 0
        assert (tmp_path / "view_predictor.json").exists()
