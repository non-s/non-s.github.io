"""Testes para scripts/check_live_health.py."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import scripts.check_live_health as check_live_health


class TestIsLiveActive:
    def test_true_when_active_broadcast_exists(self):
        service = MagicMock()
        service.liveBroadcasts().list().execute.return_value = {"items": [{"id": "b1"}]}

        assert check_live_health.is_live_active(service) is True

    def test_false_when_no_active_broadcast(self):
        service = MagicMock()
        service.liveBroadcasts().list().execute.return_value = {"items": []}

        assert check_live_health.is_live_active(service) is False

    def test_queries_active_status_only(self):
        service = MagicMock()
        service.liveBroadcasts().list().execute.return_value = {"items": []}

        check_live_health.is_live_active(service)

        _, kwargs = service.liveBroadcasts().list.call_args
        assert kwargs["broadcastStatus"] == "active"
        assert kwargs["mine"] is True


class TestWriteGithubOutput:
    def test_writes_true_when_active(self, tmp_path, monkeypatch):
        output_file = tmp_path / "github_output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        check_live_health._write_github_output(True, {"timestamp": "2026-01-01T00:00:00+00:00", "live_active": True})

        content = output_file.read_text(encoding="utf-8")
        assert "live_active=true" in content

    def test_writes_false_when_inactive(self, tmp_path, monkeypatch):
        output_file = tmp_path / "github_output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        check_live_health._write_github_output(False, {"timestamp": "2026-01-01T00:00:00+00:00", "live_active": False})

        content = output_file.read_text(encoding="utf-8")
        assert "live_active=false" in content

    def test_appends_without_truncating_existing_content(self, tmp_path, monkeypatch):
        output_file = tmp_path / "github_output.txt"
        output_file.write_text("other_output=1\n", encoding="utf-8")
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        check_live_health._write_github_output(True, {"timestamp": "2026-01-01T00:00:00+00:00", "live_active": True})

        content = output_file.read_text(encoding="utf-8")
        assert "other_output=1" in content
        assert "live_active=true" in content
        assert "last_known_status=" in content
        assert "checked_at=2026-01-01T00:00:00+00:00" in content

    def test_no_op_when_github_output_unset(self, monkeypatch):
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
        check_live_health._write_github_output(True, {"timestamp": "", "live_active": True})  # nao deve levantar


class TestMain:
    def test_returns_zero_and_writes_output_when_active(self, tmp_path, monkeypatch):
        output_file = tmp_path / "github_output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
        service = MagicMock()
        service.liveBroadcasts().list().execute.return_value = {"items": [{"id": "b1"}]}

        with patch("scripts.check_live_health.get_youtube_service", return_value=service):
            code = check_live_health.main()

        assert code == 0
        assert "live_active=true" in output_file.read_text(encoding="utf-8")

    def test_returns_zero_and_writes_output_when_inactive(self, tmp_path, monkeypatch):
        output_file = tmp_path / "github_output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
        service = MagicMock()
        service.liveBroadcasts().list().execute.return_value = {"items": []}

        with patch("scripts.check_live_health.get_youtube_service", return_value=service):
            code = check_live_health.main()

        assert code == 0
        assert "live_active=false" in output_file.read_text(encoding="utf-8")

    def test_returns_nonzero_and_skips_output_on_auth_failure(self, tmp_path, monkeypatch):
        """Falha na propria checagem (auth/rede) nao deve ser confundida com
        "live esta fora do ar" - sem GITHUB_OUTPUT, o workflow nao abre nem
        fecha nenhuma issue por causa disso."""
        output_file = tmp_path / "github_output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        with patch("scripts.check_live_health.get_youtube_service", side_effect=RuntimeError("no creds")):
            code = check_live_health.main()

        assert code == 1
        assert not output_file.exists()


class TestWriteLastHealth:
    def test_writes_payload_with_timestamp_and_status(self, tmp_path, monkeypatch):
        monkeypatch.setattr(check_live_health, "LAST_HEALTH_FILE", tmp_path / "last_health.json")
        payload = check_live_health._write_last_health(True)
        assert payload["live_active"] is True
        assert "timestamp" in payload
        written = json.loads((tmp_path / "last_health.json").read_text(encoding="utf-8"))
        assert written == payload

    def test_survives_when_data_dir_not_writable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(check_live_health, "LAST_HEALTH_FILE", tmp_path / "last_health.json")

        def _raise(*a, **k):
            raise OSError("denied")
        monkeypatch.setattr(Path, "write_text", _raise)
        payload = check_live_health._write_last_health(False)
        # Payload ainda retornado mesmo se nao gravou
        assert payload["live_active"] is False
