"""Testes para scripts/generate_dashboard.py.

Nenhum destes testes bate em rede/API - o script so consome os arquivos ja
gravados em _data/ por collect_analytics.py e upload_youtube.py. Cobre
principalmente o caminho "sem dados ainda" (canal novo, antes da primeira
coleta) e o caminho "com dados", garantindo que o HTML gerado e valido e
contem a informacao esperada.
"""

import json

import scripts.generate_dashboard as dashboard


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard, "ANALYTICS_FILE", tmp_path / "analytics.json")
    monkeypatch.setattr(dashboard, "HISTORY_FILE", tmp_path / "analytics_history.json")
    monkeypatch.setattr(dashboard, "SCENE_PERFORMANCE_FILE", tmp_path / "scene_performance.json")
    monkeypatch.setattr(dashboard, "TITLE_PATTERN_PERFORMANCE_FILE", tmp_path / "title_pattern_performance.json")
    monkeypatch.setattr(dashboard, "LIVE_VIEWER_HISTORY_FILE", tmp_path / "live_viewer_history.json")


class TestBuildDashboardHtmlEmpty:
    """Sem nenhum arquivo em _data/ (canal novo): o dashboard ainda precisa
    gerar HTML valido, so com avisos de "sem dados" em vez de quebrar."""

    def test_generates_valid_html_with_no_data_files(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)

        html = dashboard.build_dashboard_html()

        assert html.startswith("<!doctype html>")
        assert "</html>" in html
        assert "Pata Jazz" in html
        assert "Nenhum dado de analytics coletado ainda." in html
        assert "Sem histórico semanal ainda" in html
        assert "Sem dados suficientes ainda" in html
        assert "Sem amostras de audiência da live ainda." in html

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
        for cid in ("viewsChart", "sceneChart", "titlePatternChart", "liveChart", "topVideosChart"):
            assert f'id="{cid}"' in html


class TestBuildDashboardHtmlWithData:
    def test_includes_summary_cards(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        dashboard.ANALYTICS_FILE.write_text(
            json.dumps({
                "total_videos": 42, "total_views": 158340, "total_likes": 3021,
                "total_comments": 412, "avg_views": 3770, "top_10": [],
            }),
            encoding="utf-8",
        )

        html = dashboard.build_dashboard_html()

        assert "42" in html
        assert "158.340" in html or "158340" in html

    def test_includes_top_videos_with_youtube_link(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        dashboard.ANALYTICS_FILE.write_text(
            json.dumps({
                "total_videos": 1, "total_views": 100, "total_likes": 1,
                "total_comments": 0, "avg_views": 100,
                "top_10": [{"video_id": "abc123", "title": "Cute Cat & Jazz", "views": 100, "likes": 1}],
            }),
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
            json.dumps({
                "total_videos": 1, "total_views": 1, "total_likes": 0, "total_comments": 0, "avg_views": 1,
                "top_10": [{"video_id": "x", "title": "<script>alert(1)</script>", "views": 1, "likes": 0}],
            }),
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
        dashboard.TITLE_PATTERN_PERFORMANCE_FILE.write_text(
            json.dumps({"{emoji} {animal}": 1.8}), encoding="utf-8"
        )

        html = dashboard.build_dashboard_html()

        assert "{emoji} {animal}" in html
        assert "1.80×" in html

    def test_live_audience_summary(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        snapshots = [{"collected_at": "t", "video_id": "v", "concurrent_viewers": v} for v in [10, 20, 30]]
        dashboard.LIVE_VIEWER_HISTORY_FILE.write_text(json.dumps(snapshots), encoding="utf-8")

        html = dashboard.build_dashboard_html()

        assert "30" in html  # pico
        assert "20" in html  # media


class TestChartsAndInteractivity:
    """Chart.js via CDN, graficos embutidos, JSON dos dados e filtro de
    periodo."""

    def test_includes_chartjs_cdn(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        html = dashboard.build_dashboard_html()
        assert "<script src=\"https://cdn.jsdelivr.net/npm/chart.js" in html
        assert "chart.umd.min.js" in html

    def test_instantiate_chart_for_each_graph(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        dashboard.ANALYTICS_FILE.write_text(
            json.dumps({
                "total_videos": 1, "total_views": 100, "total_likes": 1,
                "total_comments": 0, "avg_views": 100,
                "top_10": [{"video_id": "x", "title": "T", "views": 100, "likes": 1}],
            }),
            encoding="utf-8",
        )
        dashboard.HISTORY_FILE.write_text(
            json.dumps([
                {"collected_at": "2026-07-01T00:00:00+00:00", "total_views": 100, "total_likes": 1, "avg_views": 100},
            ]),
            encoding="utf-8",
        )
        dashboard.SCENE_PERFORMANCE_FILE.write_text(json.dumps({"cat": 1.0}), encoding="utf-8")
        dashboard.TITLE_PATTERN_PERFORMANCE_FILE.write_text(json.dumps({"pat": 1.0}), encoding="utf-8")
        dashboard.LIVE_VIEWER_HISTORY_FILE.write_text(
            json.dumps([{"collected_at": "t", "video_id": "v", "concurrent_viewers": 5}]), encoding="utf-8"
        )

        html = dashboard.build_dashboard_html()

        # Um new Chart por grafico (5 graficos).
        assert html.count("new Chart(") == 5

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
        dashboard.SCENE_PERFORMANCE_FILE.write_text(
            json.dumps({malicious: 1.0}), encoding="utf-8"
        )

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
    analytics.json e live_viewer_history.json hospedados no mesmo GitHub
    Pages (se publicados) e atualiza os cards/graficos a cada 60s."""

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
        assert "live_viewer_history.json" in html

    def test_html_contains_refresh_interval_60s(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        html = dashboard.build_dashboard_html()
        assert "60000" in html
        assert "setInterval" in html

    def test_html_documents_weekly_update_limitation(self, tmp_path, monkeypatch):
        _isolate(tmp_path, monkeypatch)
        html = dashboard.build_dashboard_html()
        assert "pata-jazz-analytics.yml" in html
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
