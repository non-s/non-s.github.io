"""Testes para scripts/batch_generate.py."""

from __future__ import annotations

from unittest.mock import patch

import scripts.batch_generate as batch_generate


class TestMainValidation:
    def test_rejects_invalid_kind(self, monkeypatch):
        monkeypatch.setenv("BATCH_KIND", "invalid")
        assert batch_generate.main() == 1

    def test_rejects_non_numeric_count(self, monkeypatch):
        monkeypatch.setenv("BATCH_KIND", "short")
        monkeypatch.setenv("BATCH_COUNT", "abc")
        assert batch_generate.main() == 1

    def test_rejects_count_out_of_range(self, monkeypatch):
        monkeypatch.setenv("BATCH_KIND", "short")
        monkeypatch.setenv("BATCH_COUNT", "11")
        assert batch_generate.main() == 1

    def test_rejects_count_zero(self, monkeypatch):
        monkeypatch.setenv("BATCH_KIND", "short")
        monkeypatch.setenv("BATCH_COUNT", "0")
        assert batch_generate.main() == 1


class TestMainGeneration:
    def test_generates_short_and_uploads_in_english(self, monkeypatch):
        """Regressao: upload_youtube.py era chamado com --language pt, um
        resquicio de antes da migracao do conteudo pra ingles - todo o
        resto do pipeline (titulo/descricao/hashtags/legenda) ja e gerado
        em ingles, entao a tag de idioma do upload tinha que bater."""
        monkeypatch.setenv("BATCH_KIND", "short")
        monkeypatch.setenv("BATCH_COUNT", "1")
        monkeypatch.setenv("BATCH_UPLOAD", "true")

        with patch("scripts.batch_generate._run", return_value=0) as mock_run:
            code = batch_generate.main()

        assert code == 0
        calls = [call.args[0] for call in mock_run.call_args_list]
        assert any("generate_pata_jazz_short.py" in cmd for cmd in calls)
        upload_calls = [cmd for cmd in calls if "upload_youtube.py" in cmd]
        assert len(upload_calls) == 1
        assert "--language" in upload_calls[0]
        assert upload_calls[0][upload_calls[0].index("--language") + 1] == "en"

    def test_horizontal_kind_runs_horizontal_generator(self, monkeypatch):
        monkeypatch.setenv("BATCH_KIND", "horizontal")
        monkeypatch.setenv("BATCH_COUNT", "1")
        monkeypatch.setenv("BATCH_UPLOAD", "false")

        with patch("scripts.batch_generate._run", return_value=0) as mock_run:
            code = batch_generate.main()

        assert code == 0
        calls = [call.args[0] for call in mock_run.call_args_list]
        assert any("generate_pata_jazz_horizontal.py" in cmd for cmd in calls)
        assert not any("upload_youtube.py" in cmd for cmd in calls)

    def test_live_kind_never_uploads_even_if_batch_upload_true(self, monkeypatch):
        """Live nao tem um arquivo pra fazer upload depois (run_live.py ja
        publica a propria transmissao) - upload=true nao deve tentar rodar
        upload_youtube.py nesse caso."""
        monkeypatch.setenv("BATCH_KIND", "live")
        monkeypatch.setenv("BATCH_COUNT", "1")
        monkeypatch.setenv("BATCH_UPLOAD", "true")

        with patch("scripts.batch_generate._run", return_value=0) as mock_run:
            code = batch_generate.main()

        assert code == 0
        calls = [call.args[0] for call in mock_run.call_args_list]
        assert any("scripts/run_live.py" in cmd for cmd in calls)
        assert not any("upload_youtube.py" in cmd for cmd in calls)

    def test_stops_on_generation_failure(self, monkeypatch):
        monkeypatch.setenv("BATCH_KIND", "short")
        monkeypatch.setenv("BATCH_COUNT", "3")
        monkeypatch.setenv("BATCH_UPLOAD", "false")

        with patch("scripts.batch_generate._run", return_value=1) as mock_run:
            code = batch_generate.main()

        assert code == 1
        assert mock_run.call_count == 1

    def test_stops_on_upload_failure(self, monkeypatch):
        monkeypatch.setenv("BATCH_KIND", "short")
        monkeypatch.setenv("BATCH_COUNT", "2")
        monkeypatch.setenv("BATCH_UPLOAD", "true")

        with patch("scripts.batch_generate._run", side_effect=[0, 1]) as mock_run:
            code = batch_generate.main()

        assert code == 1
        assert mock_run.call_count == 2

    def test_generates_requested_count(self, monkeypatch):
        monkeypatch.setenv("BATCH_KIND", "short")
        monkeypatch.setenv("BATCH_COUNT", "3")
        monkeypatch.setenv("BATCH_UPLOAD", "false")

        with patch("scripts.batch_generate._run", return_value=0) as mock_run:
            code = batch_generate.main()

        assert code == 0
        assert mock_run.call_count == 3

    def test_live_propagates_live_env_vars(self, monkeypatch):
        monkeypatch.setenv("BATCH_KIND", "live")
        monkeypatch.setenv("BATCH_COUNT", "1")
        monkeypatch.setenv("YOUTUBE_PRIVACY", "unlisted")
        monkeypatch.setenv("LIVE_RESOLUTION", "1280x720")
        monkeypatch.setenv("LIVE_DURATION_MINUTES", "30")

        with patch("scripts.batch_generate._run", return_value=0) as mock_run:
            code = batch_generate.main()

        assert code == 0
        env = mock_run.call_args.kwargs.get("env")
        assert env == {
            "YOUTUBE_PRIVACY": "unlisted",
            "LIVE_RESOLUTION": "1280x720",
            "LIVE_DURATION_MINUTES": "30",
        }
