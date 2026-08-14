"""Testes para scripts/generate_dashboard.py.

Nenhum destes testes bate em rede/API - o script so consome os arquivos ja
gravados em _data/ por collect_analytics.py e upload_youtube.py. Cobre
principalmente o caminho "sem dados ainda" (canal novo, antes da primeira
coleta) e o caminho "com dados", garantindo que o HTML gerado e valido e
contem a informacao esperada.
"""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

import scripts.generate_dashboard as dashboard

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"
FULL_HTML_HASH_FILE = SNAPSHOT_DIR / "dashboard_full_html_hash.txt"


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard, "ANALYTICS_FILE", tmp_path / "analytics.json")
    monkeypatch.setattr(dashboard, "HISTORY_FILE", tmp_path / "analytics_history.json")
    monkeypatch.setattr(dashboard, "SCENE_PERFORMANCE_FILE", tmp_path / "scene_performance.json")
    monkeypatch.setattr(dashboard, "TITLE_PATTERN_PERFORMANCE_FILE", tmp_path / "title_pattern_performance.json")
    monkeypatch.setattr(dashboard, "VIEW_PREDICTOR_FILE", tmp_path / "view_predictor.json")
    monkeypatch.setattr(dashboard, "VIDEO_TAGS_FILE", tmp_path / "video_tags.json")
    monkeypatch.setattr(dashboard, "QUALITY_HISTORY_FILE", tmp_path / "quality_history.json")


class TestBuildDashboardHtmlEmpty:
    """Sem nenhum arquivo em _data/ (canal novo): o dashboard ainda precisa
    gerar HTML valido, so com avisos de "sem dados" em vez de quebrar."""

    def test_generates_valid_html_with_no_data_files(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)

        html = dashboard.build_dashboard_html()

        assert html.startswith("<!doctype html>")
        assert "</html>" in html
        assert "Liquid Wire" in html
        assert "Nenhum dado de analytics coletado ainda." in html
        assert "Sem histórico semanal ainda" in html
        assert "Sem dados suficientes ainda" in html

    def test_corrupted_files_do_not_crash(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        dashboard.ANALYTICS_FILE.write_text("not json", encoding="utf-8")
        dashboard.HISTORY_FILE.write_text("not json", encoding="utf-8")

        html = dashboard.build_dashboard_html()

        assert html.startswith("<!doctype html>")

    def test_empty_data_still_includes_chart_scaffold(self, tmp_path, monkeypatch):
        """Mesmo sem dados, o HTML precisa trazer o CDN do Chart.js e os
        canvases - os graficos so ficam vazios."""
        _isolate(tmp_path, monkeypatch)

        html = dashboard.build_dashboard_html()

        assert "cdn.jsdelivr.net/npm/chart.js" in html
        # Cada grafico tem seu canvas.
        for cid in ("viewsChart", "sceneChart", "titlePatternChart", "topVideosChart"):
            assert f'id="{cid}"' in html


class TestBuildDashboardHtmlWithData:
    def test_includes_summary_cards(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        dashboard.ANALYTICS_FILE.write_text(
            json.dumps(
                {
                    "total_videos": 42,
                    "total_views": 158340,
                    "total_likes": 3021,
                    "total_comments": 412,
                    "avg_views": 3770,
                    "top_10": [],
                }
            ),
            encoding="utf-8",
        )

        html = dashboard.build_dashboard_html()

        assert "42" in html
        assert "158.340" in html or "158340" in html

    def test_includes_top_videos_with_youtube_link(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        dashboard.ANALYTICS_FILE.write_text(
            json.dumps(
                {
                    "total_videos": 1,
                    "total_views": 100,
                    "total_likes": 1,
                    "total_comments": 0,
                    "avg_views": 100,
                    "top_10": [{"video_id": "abc123", "title": "Cute Cat & Jazz", "views": 100, "likes": 1}],
                }
            ),
            encoding="utf-8",
        )

        html = dashboard.build_dashboard_html()

        assert "Cute Cat &amp; Jazz" in html
        assert "https://youtu.be/abc123" in html

    def test_escapes_title_to_prevent_xss(self, tmp_path, monkeypatch):
        """Titulos vem do YouTube (snippet.title) - nao sao confiaveis por
        padrao, mesmo sendo o proprio conteudo do canal."""
        _isolate(tmp_path, monkeypatch)
        dashboard.ANALYTICS_FILE.write_text(
            json.dumps(
                {
                    "total_videos": 1,
                    "total_views": 1,
                    "total_likes": 0,
                    "total_comments": 0,
                    "avg_views": 1,
                    "top_10": [{"video_id": "x", "title": "<script>alert(1)</script>", "views": 1, "likes": 0}],
                }
            ),
            encoding="utf-8",
        )

        html = dashboard.build_dashboard_html()

        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_includes_history_rows(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        history = [
            {"collected_at": "2026-07-01T00:00:00+00:00", "total_views": 1000, "total_likes": 10, "avg_views": 100},
            {"collected_at": "2026-07-08T00:00:00+00:00", "total_views": 2000, "total_likes": 20, "avg_views": 150},
        ]
        dashboard.HISTORY_FILE.write_text(json.dumps(history), encoding="utf-8")

        html = dashboard.build_dashboard_html()

        assert "2026-07-01" in html
        assert "2026-07-08" in html

    def test_caps_history_rows_to_recent_ones(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        history = [
            {"collected_at": f"2026-01-{i:02d}T00:00:00+00:00", "total_views": i, "total_likes": 0, "avg_views": i}
            for i in range(1, 20)
        ]
        dashboard.HISTORY_FILE.write_text(json.dumps(history), encoding="utf-8")

        html = dashboard.build_dashboard_html()

        assert "2026-01-01" not in html  # fora da janela dos mais recentes
        assert "2026-01-19" in html

    def test_scene_performance_sorted_by_weight_desc(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        dashboard.SCENE_PERFORMANCE_FILE.write_text(
            json.dumps({"cat": 0.5, "sleepy dog": 2.1, "puppy": 1.0}), encoding="utf-8"
        )

        html = dashboard.build_dashboard_html()

        first = html.index("sleepy dog")
        second = html.index("puppy")
        third = html.index("cat")
        assert first < second < third

    def test_title_pattern_performance_rendered(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        dashboard.TITLE_PATTERN_PERFORMANCE_FILE.write_text(json.dumps({"{emoji} {animal}": 1.8}), encoding="utf-8")

        html = dashboard.build_dashboard_html()

        assert "{emoji} {animal}" in html
        assert "1.80×" in html


class TestChartsAndInteractivity:
    """Chart.js via CDN, graficos embutidos, JSON dos dados e filtro de
    periodo."""

    def test_includes_chartjs_cdn(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        html = dashboard.build_dashboard_html()
        assert '<script src="https://cdn.jsdelivr.net/npm/chart.js' in html
        assert "chart.umd.min.js" in html

    def test_instantiate_chart_for_each_graph(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        dashboard.ANALYTICS_FILE.write_text(
            json.dumps(
                {
                    "total_videos": 1,
                    "total_views": 100,
                    "total_likes": 1,
                    "total_comments": 0,
                    "avg_views": 100,
                    "top_10": [{"video_id": "x", "title": "T", "views": 100, "likes": 1}],
                }
            ),
            encoding="utf-8",
        )
        dashboard.HISTORY_FILE.write_text(
            json.dumps(
                [
                    {
                        "collected_at": "2026-07-01T00:00:00+00:00",
                        "total_views": 100,
                        "total_likes": 1,
                        "avg_views": 100,
                    },
                ]
            ),
            encoding="utf-8",
        )
        dashboard.SCENE_PERFORMANCE_FILE.write_text(json.dumps({"cat": 1.0}), encoding="utf-8")
        dashboard.TITLE_PATTERN_PERFORMANCE_FILE.write_text(json.dumps({"pat": 1.0}), encoding="utf-8")

        html = dashboard.build_dashboard_html()

        # Um new Chart por grafico (7 graficos: views, viewsByDay, scene,
        # title, top videos, thumbnail variants A/B/C e diversity scatter).
        assert html.count("new Chart(") == 7

    def test_analytics_history_data_embedded_as_json(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        history = [
            {"collected_at": "2026-07-01T00:00:00+00:00", "total_views": 1234, "total_likes": 7, "avg_views": 99},
        ]
        dashboard.HISTORY_FILE.write_text(json.dumps(history), encoding="utf-8")

        html = dashboard.build_dashboard_html()

        # Labels e dados aparecem no JSON embutido dentro de <script>.
        assert "2026-07-01" in html
        assert "1234" in html
        assert "HISTORY_DS" in html

    def test_period_filter_present(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        html = dashboard.build_dashboard_html()
        assert 'id="period-filter"' in html
        assert "Últimas 4 semanas" in html
        assert "Últimas 12 semanas" in html
        assert "Tudo" in html

    def test_xss_protection_on_embedded_json_labels(self, tmp_path, monkeypatch):
        """Dados de _data/ injetados em <script> JSON tambem precisam estar
        escapados (pelo menos a sequencia </script> nao pode aparecer)."""
        _isolate(tmp_path, monkeypatch)
        malicious = "</script><script>alert('xss')</script>"
        dashboard.SCENE_PERFORMANCE_FILE.write_text(json.dumps({malicious: 1.0}), encoding="utf-8")

        html = dashboard.build_dashboard_html()

        assert "</script><script>alert('xss')</script>" not in html
        # "</" dentro do JSON embutido precisa estar quebrado (</ -> <\/).
        assert "<\\/script" in html or "</script>" not in html.split("var SCENE_DS")[1].split("</script>")[0]

    def test_empty_data_does_not_break_charts(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        html = dashboard.build_dashboard_html()
        # Sem dados, ainda gera HTML valido e o guard `if (!ds.labels.length) return;`
        # protege os graficos que dependem de dados (scene/title/live/top).
        assert html.startswith("<!doctype html>")
        assert "makeViewsChart" in html
        assert "makeSceneChart" in html


class TestRefreshButtonAndLiveFetch:
    """Item 17: botao "Atualizar dados" + funcao JS que faz fetch de
    analytics.json hospedado no mesmo GitHub Pages (se publicado) e
    atualiza os cards/graficos a cada 60s."""

    def test_html_contains_refresh_button(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        html = dashboard.build_dashboard_html()
        assert 'id="refresh-btn"' in html
        assert "Atualizar dados" in html

    def test_html_contains_fetch_live_analytics_function(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        html = dashboard.build_dashboard_html()
        assert "fetchLiveAnalytics" in html
        assert "fetch(" in html
        assert "analytics.json" in html

    def test_html_contains_refresh_interval_60s(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        html = dashboard.build_dashboard_html()
        assert "60000" in html
        assert "setInterval" in html

    def test_html_documents_weekly_update_limitation(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        html = dashboard.build_dashboard_html()
        assert "liquid-wire-analytics.yml" in html
        assert "semanal" in html

    def test_refresh_button_click_triggers_fetch(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        html = dashboard.build_dashboard_html()
        assert "refreshBtn.addEventListener" in html
        assert "click" in html


class TestMain:
    def test_writes_index_html_to_dashboard_dir(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        monkeypatch.setattr(dashboard, "ROOT", tmp_path)

        code = dashboard.main()

        assert code == 0
        output = tmp_path / "_dashboard" / "index.html"
        assert output.exists()
        assert output.read_text(encoding="utf-8").startswith("<!doctype html>")


class TestSceneHourHeatmap:
    """Item 6.4: heatmap cena × horário usando o view_predictor. Renderiza
    tabela HTML colorida (CSS inline background-color) sem Chart.js."""

    def _predictor(self, scenes, patterns):
        return {
            "scenes": scenes,
            "title_patterns": patterns,
            "n_samples": 10,
            "weights": [0.1] * 20,
            "overall_avg": 100.0,
        }

    def test_no_model_renders_empty_message(self, tmp_path, monkeypatch):
        html = dashboard._render_scene_hour_heatmap({})
        assert "Sem modelo de previsão" in html

    def test_zero_samples_renders_empty_message(self, tmp_path, monkeypatch):
        html = dashboard._render_scene_hour_heatmap({"n_samples": 0})
        assert "Sem modelo de previsão" in html

    def test_renders_table_with_scenes_and_buckets(self, tmp_path, monkeypatch):
        predictor = self._predictor(["cat", "dog"], ["pat"])
        monkeypatch.setattr("scripts.predict_views.predict_views", lambda s, p, h, d: 50.0)
        html = dashboard._render_scene_hour_heatmap(predictor)
        assert "Cena × Horário" in html
        assert "manhã" in html
        assert "tarde" in html
        assert "noite" in html
        assert "cat" in html
        assert "dog" in html

    def test_renders_colored_cells(self, tmp_path, monkeypatch):
        predictor = self._predictor(["cat"], ["pat"])
        monkeypatch.setattr("scripts.predict_views.predict_views", lambda s, p, h, d: 50.0)
        html = dashboard._render_scene_hour_heatmap(predictor)
        assert "background:rgb(" in html

    def test_matrix_structure(self, tmp_path, monkeypatch):
        predictor = self._predictor(["cat", "dog"], ["pat"])
        monkeypatch.setattr("scripts.predict_views.predict_views", lambda s, p, h, d: float(h))
        data = dashboard._build_scene_hour_matrix(predictor)
        assert data["scenes"] == ["cat", "dog"]
        assert data["buckets"] == ["manhã", "tarde", "noite"]
        assert "cat" in data["matrix"]
        # hora representativa manha=9, tarde=15, noite=21
        assert data["matrix"]["cat"]["manhã"] == 9.0
        assert data["matrix"]["cat"]["tarde"] == 15.0
        assert data["matrix"]["cat"]["noite"] == 21.0

    def test_heatmap_color_zero_returns_fondo(self):
        assert dashboard._heatmap_color(0.0) == "#2a2a40"

    def test_heatmap_color_one_near_accent(self):
        color = dashboard._heatmap_color(1.0)
        assert "244" in color or "rgb(" in color

    def test_heatmap_color_negative_clamped(self):
        assert dashboard._heatmap_color(-1.0) == "#2a2a40"

    def test_heatmap_section_present_in_dashboard(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        html = dashboard.build_dashboard_html()
        assert "Heatmap cena × horário" in html

    def test_no_patterns_uses_empty_pattern(self, tmp_path, monkeypatch):
        predictor = self._predictor(["cat"], [])
        monkeypatch.setattr("scripts.predict_views.predict_views", lambda s, p, h, d: 30.0)
        data = dashboard._build_scene_hour_matrix(predictor)
        assert data["matrix"]["cat"]["manhã"] == 30.0


class TestFullHtmlSnapshot:
    """Snapshot do HTML completo do dashboard com um conjunto de fixtures
    diferente de tests/test_dashboard_snapshot.py (para regressao independente).

    Compara o hash SHA-256 do HTML gerado (datetime.now fixado) contra um
    baseline em tests/snapshots/dashboard_full_html_hash.txt. Para regenerar:

        UPDATE_SNAPSHOTS=1 python -m pytest tests/test_generate_dashboard.py::TestFullHtmlSnapshot
    """

    def _seed_fixtures(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)

        dashboard.ANALYTICS_FILE.write_text(
            json.dumps(
                {
                    "total_videos": 7,
                    "total_views": 42195,
                    "total_likes": 882,
                    "total_comments": 77,
                    "avg_views": 6028,
                    "top_10": [
                        {"video_id": "snapA", "title": "Sleepy Kitten & Soft Jazz", "views": 12000, "likes": 300},
                        {"video_id": "snapB", "title": "Playful Puppy Jazz Time", "views": 9000, "likes": 250},
                    ],
                }
            ),
            encoding="utf-8",
        )
        dashboard.HISTORY_FILE.write_text(
            json.dumps(
                [
                    {
                        "collected_at": "2026-03-01T00:00:00+00:00",
                        "total_views": 5000,
                        "total_likes": 50,
                        "avg_views": 700,
                    },
                    {
                        "collected_at": "2026-03-08T00:00:00+00:00",
                        "total_views": 9000,
                        "total_likes": 90,
                        "avg_views": 1200,
                    },
                ]
            ),
            encoding="utf-8",
        )
        dashboard.SCENE_PERFORMANCE_FILE.write_text(
            json.dumps({"puppy": 1.7, "sleepy cat": 0.9, "dog": 1.2}), encoding="utf-8"
        )
        dashboard.TITLE_PATTERN_PERFORMANCE_FILE.write_text(
            json.dumps({"{animal} vibes": 2.3, "{emoji} jazz": 1.1}), encoding="utf-8"
        )
        dashboard.VIEW_PREDICTOR_FILE.write_text(
            json.dumps({"n_samples": 10, "hour": [1.0], "dow": [0.5], "intercept": 100.0}),
            encoding="utf-8",
        )
        dashboard.VIDEO_TAGS_FILE.write_text(
            json.dumps({"snapA": {"scene": "sleepy cat", "thumbnail_variant": "A", "views": 12000}}),
            encoding="utf-8",
        )

    def test_full_html_snapshot(self, tmp_path, monkeypatch):
        self._seed_fixtures(tmp_path, monkeypatch)
        fixed = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)

        class _FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed if tz is None else fixed.astimezone(tz)

        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        import scripts.predict_views as predict_views

        with (
            patch.object(dashboard, "datetime", _FixedDatetime),
            patch.object(predict_views, "datetime", _FixedDatetime),
        ):
            html = dashboard.build_dashboard_html()

        digest = hashlib.sha256(html.encode("utf-8")).hexdigest()

        if os.environ.get("UPDATE_SNAPSHOTS") == "1":
            FULL_HTML_HASH_FILE.write_text(digest + "\n", encoding="utf-8")
            return

        if not FULL_HTML_HASH_FILE.exists():
            pytest.skip(
                f"Nenhum baseline em {FULL_HTML_HASH_FILE}. Rode com UPDATE_SNAPSHOTS=1 "
                f"para criar (hash atual: {digest})."
            )

        baseline = FULL_HTML_HASH_FILE.read_text(encoding="utf-8").strip()
        if baseline != digest:
            # Divergencias entre Windows/Linux podem ocorrer por diferencas
            # de locale ou line endings. Avisa em vez de falhar em non-Linux.
            import sys

            if sys.platform == "linux":
                pytest.fail(
                    f"Dashboard HTML divergiu no Linux. Rode "
                    f"`UPDATE_SNAPSHOTS=1 python -m pytest "
                    f"tests/test_generate_dashboard.py::TestFullHtmlSnapshot` "
                    f"para regenerar (hash atual: {digest}, baseline: {baseline})."
                )
            else:
                pytest.skip(
                    f"Snapshot diverge em non-Linux (normal): hash={digest} baseline={baseline}."
                )
