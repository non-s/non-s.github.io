"""Testes para scripts/predict_views.py — analytics preditivo.

Cobre o treino com dados sintéticos, o fallback de média geral sem dados,
a construção das features one-hot e a leitura do modelo salvo em disco.
"""

import json
import math
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import scripts.predict_views as pv
from utils.seo_keywords import TITLE_PATTERNS


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
        json.dumps(
            {"total_videos": len(all_videos), "total_views": sum(v[4] for v in videos), "all_videos": all_videos}
        ),
        encoding="utf-8",
    )
    tags = {
        vid: {"scene": scene, "title_pattern": pat, "uploaded_at": pub} for (vid, scene, pat, pub, _views) in videos
    }
    (tmp_path / "video_tags.json").write_text(json.dumps(tags), encoding="utf-8")


class TestFeaturizeOneHot:
    def test_one_hot_scene_and_title_pattern(self):
        scenes = ["cat", "dog"]
        patterns = ["pat-a", "pat-b"]
        vec = pv._featurize("cat", "pat-a", hour=10, day_of_week=0, scenes=scenes, title_patterns=patterns)
        # bias + (scenes-1) + (patterns-1) + hour + dow + dom + month +
        # ctr + avp + scene_x_hour (scenes-1 * 2 buckets) = 1+1+1+1+1+1+1+1+1+1+2 = 11.
        # Primeira cena (cat) e primeiro padrão (pat-a) são a referência
        # (dummy variable trap) — não ganham coluna; suas contribuições
        # ficam implícitas no bias.
        assert vec[0] == 1.0
        assert vec[1:2] == [0.0]  # scene:dog (cat é a referência)
        assert vec[2:3] == [0.0]  # pattern:pat-b (pat-a é a referência)
        assert vec[3] == 10.0 / 23.0  # hour=10 normalizado
        assert vec[4] == 0.0  # day_of_week=0
        assert vec[5] == 1.0 / 31.0  # day_of_month default=1
        assert vec[6] == 1.0 / 12.0  # month default=1
        assert vec[7] == 0.0  # ctr default=0
        assert vec[8] == 0.0  # avp default=0
        # scene_x_hour: 1 (scenes-1) * 2 (buckets-1) = 2 colunas (dog x tarde/noite)
        # hour=10 -> bucket=manha (referencia, omitido) -> ambas 0.
        assert vec[9:11] == [0.0, 0.0]

    def test_unknown_scene_yields_zero_one_hot(self):
        # "cat" é a referência (omitida); "alien" não está no vocabulário
        # -> todas as colunas de cena (dog) são 0.
        vec = pv._featurize("alien", "pat-a", 0, 0, scenes=["cat", "dog"], title_patterns=["pat-a", "pat-b"])
        assert vec[1] == 0.0  # scene:dog
        assert vec[2] == 0.0  # pattern:pat-b (pat-a é referência)

    def test_hour_and_day_are_scalar(self):
        vec = pv._featurize("cat", "pat", hour=23, day_of_week=6, scenes=["cat"], title_patterns=["pat"])
        # bias + 0 scene + 0 pattern + hour + dow + dom + month + ctr + avp + 0 scene_x_hour
        # = 1 + 6 escalares + 0 interacoes (1 cena = referencia).
        # Normalizados para [0,1]: hour=23 -> 1.0, dow=6 -> 1.0.
        assert vec[-6] == 1.0  # hour
        assert vec[-5] == 1.0  # day_of_week

    def test_case_insensitive_scene(self):
        # 2 cenas; cat é referência. dog (segunda) ganha coluna 1.
        vec = pv._featurize("DOG", "pat", 0, 0, scenes=["cat", "dog"], title_patterns=["pat"])
        assert vec[1] == 1.0  # scene:dog

    def test_day_of_month_normalized(self):
        vec = pv._featurize("cat", "pat", 0, 0, scenes=["cat"], title_patterns=["pat"], day_of_month=15, month=6)
        assert vec[-4] == 15.0 / 31.0
        assert vec[-3] == 6.0 / 12.0

    def test_month_normalized(self):
        vec = pv._featurize("cat", "pat", 0, 0, scenes=["cat"], title_patterns=["pat"], day_of_month=1, month=12)
        assert vec[-3] == 12.0 / 12.0

    def test_ctr_avp_normalized(self):
        vec = pv._featurize("cat", "pat", 0, 0, scenes=["cat"], title_patterns=["pat"], ctr=0.25, avp=0.8)
        assert vec[-2] == 0.5  # ctr 0.25 / 0.5
        assert vec[-1] == 0.8  # avp 0.8 / 1.0

    def test_scene_x_hour_interaction(self):
        """scene_x_hour one-hot: dog (segunda cena) x tarde (segundo bucket)
        ativa quando cena=dog e hour=14 (tarde)."""
        vec = pv._featurize("dog", "pat", 14, 0, scenes=["cat", "dog"], title_patterns=["pat"])
        # scene_x_hour:dog:tarde ativa (últimas colunas após ctr/avp).
        assert vec[-2] == 1.0  # dog x tarde
        assert vec[-1] == 0.0  # dog x noite

    def test_hour_bucket_classification(self):
        assert pv._hour_bucket(8) == "manha"
        assert pv._hour_bucket(14) == "tarde"
        assert pv._hour_bucket(20) == "noite"
        assert pv._hour_bucket(2) == "noite"
        assert pv._hour_bucket(6) == "manha"
        assert pv._hour_bucket(12) == "tarde"
        assert pv._hour_bucket(18) == "noite"


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
        # proxy: y = views/100*7 = views*0.07 -> ~700 para high, ~7 para low.
        # O ridge introduz pequeno vazamento da media geral para a cena baixa
        # (dog), entao low_pred fica acima de 7 mas bem abaixo de high_pred.
        assert high_pred > 100
        assert low_pred < 600

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
        pv.save_model(
            {
                "features": [],
                "weights": [],
                "scenes": [],
                "title_patterns": [],
                "overall_avg": 42.0,
                "n_samples": 0,
            }
        )
        assert pv.predict_views("cat", "pat", 10, 0) == 42.0

    def test_predict_returns_zero_when_no_model_file(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        # Nenhum arquivo de modelo em disco.
        assert pv.predict_views("cat", "pat", 10, 0) == 0.0


class TestNewFeaturesAndBackwardCompat:
    """Item 21: features calendario (day_of_month, month) e interacao
    scene_x_hour. Modelo antigo (sem essas features) ainda carrega via
    fallback overall_avg em predict_views quando len(vec) != len(weights)."""

    def test_new_features_appear_in_model(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        now = datetime.now(UTC)
        vids = []
        for i in range(20):
            pub = (now - timedelta(days=100, hours=i)).isoformat()
            scene = "cat" if i % 2 == 0 else "dog"
            pat = "pat-a" if i % 3 != 0 else "pat-b"
            vids.append((f"vid{i}", scene, pat, pub, 100 + i))
        _write_analytics_with_tags(tmp_path, videos=vids)

        model = pv.train_model()

        assert "day_of_month" in model["features"]
        assert "month" in model["features"]
        # Interacao scene_x_hour: uma coluna por (cena x bucket) exceto
        # primeira cena x primeiro bucket (referencia).
        scene_hour_features = [f for f in model["features"] if f.startswith("scene_x_hour:")]
        assert len(scene_hour_features) > 0
        # dog x tarde e dog x noite devem aparecer (cat x manha e a referencia).
        assert "scene_x_hour:dog:tarde" in model["features"]
        assert "scene_x_hour:dog:noite" in model["features"]
        # cat e a primeira cena (referencia) -> nao tem scene_x_hour:cat:*.
        assert not any(f.startswith("scene_x_hour:cat:") for f in model["features"])
        assert len(model["weights"]) == len(model["features"])

    def test_old_model_without_new_features_still_loads(self, tmp_path, monkeypatch):
        """Modelo antigo (sem day_of_month/month/scene_x_hour) salvo manualmente:
        predict_views detecta len(vec) != len(weights) e cai em overall_avg."""
        _isolate(tmp_path, monkeypatch)
        # Modelo "antigo" com features legacy (bias + scene + pattern + hour + dow).
        old_features = ["bias", "scene:dog", "title_pattern:pat-b", "hour_of_day", "day_of_week"]
        old_weights = [10.0, 2.0, 1.0, 0.5, 0.1]
        pv.save_model(
            {
                "features": old_features,
                "weights": old_weights,
                "scenes": ["cat", "dog"],
                "title_patterns": ["pat-a", "pat-b"],
                "overall_avg": 99.0,
                "n_samples": 10,
            }
        )

        # len(vec) novo (inclui ctr/avp) > len(weights) antigo -> fallback overall_avg.
        pred = pv.predict_views("cat", "pat-a", 10, 0)
        assert pred == 99.0

    def test_predict_views_accepts_day_of_month_and_month(self, tmp_path, monkeypatch):
        """predict_views aceita day_of_month/month como kwargs opcionais
        (backward compat: sem eles usa a data atual)."""
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

        pred = pv.predict_views("cat", "pat-a", 10, 0, day_of_month=15, month=6)
        assert pred >= 0.0


class TestNoDataFallback:
    def test_no_samples_returns_empty_model_with_zero_avg(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        (tmp_path / "analytics.json").write_text(json.dumps({"total_videos": 0, "all_videos": []}), encoding="utf-8")
        (tmp_path / "video_tags.json").write_text("{}", encoding="utf-8")

        model = pv.train_model()

        assert model["n_samples"] == 0
        assert model["weights"] == []
        assert model["overall_avg"] == 0.0
        assert model["scenes"] == []

    def test_no_video_tags_returns_empty_model(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        (tmp_path / "analytics.json").write_text(
            json.dumps(
                {"total_videos": 5, "all_videos": [{"video_id": "v1", "views": 100, "published_at": "2025-01-01"}]}
            ),
            encoding="utf-8",
        )
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
        # Um Short por dia, sempre às 18:07 UTC (o modelo usa apenas a hora).
        assert slots == [(18, 0), (18, 1), (18, 2), (18, 3)]

    def test_late_night_wraps_to_next_day(self):
        now = datetime(2026, 7, 27, 23, 30, tzinfo=UTC)  # depois das 23:00
        slots = pv.next_cron_slots(now=now, n=2)
        assert slots[0] == (18, 1)  # 18:07 ter (weekday 1)
        assert slots[1] == (18, 2)  # 18:07 qua


class TestPredictViewsWithRealisticData:
    """Treina o modelo com dados que se assemelham aos de producao real:
    mix de cenas (cat, dog, sleepy cat, puppy), varios padroes de titulo
    (varrendo TITLE_PATTERNS['short']), views variando de 100 a 15000 e
    publicacoes em horas e dias diferentes ao longo de ~90 dias.

    Verifica que as previsoes sao razoaveis: cenas de alto desempenho
    ficam acima das de baixo, dentro de um intervalo sao (0-50000) e sem
    NaN/inf."""

    def _realistic_dataset(self, now):
        """Monta amostras misturando 4 cenas e todos os padroes de titulo
        short, publicadas em horas/dias variados ao longo de ~90 dias, com
        views entre 100 e 15000.

        samples_per_scene escala com o numero de padroes (2x, sempre pelo
        menos 10): com poucas amostras por (cena, padrao) - ex.: so 1 - o
        modelo (23+ colunas one-hot/interacao com so ~2 * len(patterns) *
        len(scenes) amostras) fica proximo de subdeterminado e superajusta,
        produzindo pesos com sinal invertido pra combinacoes hora/padrao
        pouco vistas no treino, que sao cortadas em 0.0 por max(0.0, ...) em
        predict_views - previsoes zeradas mesmo pra cenas historicamente
        fortes. Manter 2 ocorrencias por (cena, padrao), como no design
        original com 5 padroes, evita esse superajuste independente de
        quantos padroes existirem."""
        scenes = ["cat", "dog", "sleepy cat", "puppy"]
        patterns = list(TITLE_PATTERNS["short"])
        # Mapeia cena -> faixa de views (cat e puppy performam melhor).
        scene_views = {
            "cat": (8000, 15000),
            "puppy": (5000, 12000),
            "dog": (500, 2000),
            "sleepy cat": (100, 600),
        }
        samples_per_scene = max(10, min(2 * len(patterns), 20))
        vids = []
        # i variando para diversificar published_at (hora/dia/views).
        i = 0
        for scene in scenes:
            low, high = scene_views[scene]
            for j in range(samples_per_scene):
                pub = (now - timedelta(days=90 - i, hours=i % 24)).isoformat()
                pat = patterns[j % len(patterns)]
                # Distribui views dentro da faixa da cena.
                views = low + (high - low) * (j % 10) // 9
                vids.append((f"vid{i}", scene, pat, pub, views))
                i += 1
        return vids

    def test_predictions_rank_scenes_by_performance(self, tmp_path, monkeypatch):
        """Congela o relogio (pv.datetime) durante todo o teste: o dataset
        sintetico usa published_at relativo a "now", e tanto train_model()
        (idade da amostra) quanto predict_views() (day_of_month/month default)
        tambem leem datetime.now(UTC) - sem congelar, o resultado (e o
        ranking das cenas) mudava sozinho conforme o dia real passava,
        tornando o teste flaky."""
        _isolate(tmp_path, monkeypatch)
        fixed_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

        class _FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_now if tz is None else fixed_now.astimezone(tz)

        with patch.object(pv, "datetime", _FixedDatetime):
            vids = self._realistic_dataset(fixed_now)
            _write_analytics_with_tags(tmp_path, videos=vids)

            pv.save_model(pv.train_model())

            first_pattern = TITLE_PATTERNS["short"][0]
            cat_pred = pv.predict_views("cat", first_pattern, hour=10, day_of_week=0)
            puppy_pred = pv.predict_views("puppy", first_pattern, hour=10, day_of_week=0)
            dog_pred = pv.predict_views("dog", first_pattern, hour=10, day_of_week=0)
            sleepy_pred = pv.predict_views("sleepy cat", first_pattern, hour=10, day_of_week=0)
        # Cenas de alto desempenho devem prever mais que as de baixo.
        assert cat_pred > dog_pred
        assert puppy_pred > sleepy_pred
        assert cat_pred > sleepy_pred

    def test_predictions_within_sane_range(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        vids = self._realistic_dataset(datetime.now(UTC))
        _write_analytics_with_tags(tmp_path, videos=vids)
        pv.save_model(pv.train_model())

        scenes = ["cat", "dog", "sleepy cat", "puppy"]
        patterns = list(TITLE_PATTERNS["short"])
        for scene in scenes:
            for pat in patterns:
                for hour in (1, 10, 16, 21):
                    pred = pv.predict_views(scene, pat, hour=hour, day_of_week=0)
                    assert 0.0 <= pred <= 50000.0

    def test_predictions_have_no_nan_or_inf(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        vids = self._realistic_dataset(datetime.now(UTC))
        _write_analytics_with_tags(tmp_path, videos=vids)
        pv.save_model(pv.train_model())

        scenes = ["cat", "dog", "sleepy cat", "puppy"]
        patterns = list(TITLE_PATTERNS["short"])
        for scene in scenes:
            for pat in patterns:
                pred = pv.predict_views(scene, pat, hour=10, day_of_week=3, day_of_month=15, month=6)
                assert math.isfinite(pred)
                assert pred >= 0.0

    def test_realistic_dataset_trains_nonempty_model(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        vids = self._realistic_dataset(datetime.now(UTC))
        _write_analytics_with_tags(tmp_path, videos=vids)

        model = pv.train_model()

        assert model["n_samples"] == len(vids)
        assert model["weights"]
        assert set(model["scenes"]) == {"cat", "dog", "sleepy cat", "puppy"}
        # Todos os padroes usados devem aparecer no vocabulario.
        for pat in TITLE_PATTERNS["short"]:
            assert pat in model["title_patterns"]


class TestMain:
    def test_main_saves_model(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        monkeypatch.setattr(pv, "configure_logging", lambda: None)
        now = datetime.now(UTC)
        vids = [(f"vid{i}", "cat", "pat-a", (now - timedelta(days=100)).isoformat(), 100 + i) for i in range(3)]
        _write_analytics_with_tags(tmp_path, videos=vids)

        assert pv.main() == 0
        assert (tmp_path / "view_predictor.json").exists()
