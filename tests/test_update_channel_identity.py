"""Testes para scripts/update_channel_identity.py."""

from __future__ import annotations

from unittest.mock import patch

import scripts.update_channel_identity as upd


class TestMain:
    @patch("scripts.update_channel_identity.record_pipeline_run")
    @patch("scripts.update_channel_identity.log_exception_to_file")
    @patch("scripts.update_channel_identity.run_identity_update")
    @patch("scripts.update_channel_identity._own_channel_id", return_value="UC123")
    @patch("scripts.update_channel_identity.get_youtube_service")
    @patch("scripts.update_channel_identity.configure_logging")
    def test_dry_run_returns_zero(self, _log, _svc, mock_id, mock_run, _log_exc, mock_pipeline, monkeypatch):
        monkeypatch.setenv("LIQUID_WIRE_ENABLED", "1")
        monkeypatch.setenv("LIQUID_WIRE_IDENTITY_ENABLED", "1")
        mock_run.return_value = {"iso_week": 31, "changed": True, "updated": False, "dry_run": True}
        monkeypatch.setattr("sys.argv", ["upd", "--dry-run"])
        assert upd.main() == 0
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["dry_run"] is True
        assert mock_run.call_args.kwargs["force"] is False

    @patch("scripts.update_channel_identity.record_pipeline_run")
    @patch("scripts.update_channel_identity.run_identity_update")
    @patch("scripts.update_channel_identity._own_channel_id", return_value="UC123")
    @patch("scripts.update_channel_identity.get_youtube_service")
    @patch("scripts.update_channel_identity.configure_logging")
    def test_force_returns_zero(self, _log, _svc, mock_id, mock_run, mock_pipeline, monkeypatch):
        monkeypatch.setenv("LIQUID_WIRE_ENABLED", "1")
        monkeypatch.setenv("LIQUID_WIRE_IDENTITY_ENABLED", "1")
        mock_run.return_value = {"iso_week": 31, "changed": True, "updated": True, "dry_run": False}
        monkeypatch.setattr("sys.argv", ["upd", "--force"])
        assert upd.main() == 0
        assert mock_run.call_args.kwargs["force"] is True

    @patch("scripts.update_channel_identity.run_identity_update")
    @patch("scripts.update_channel_identity.configure_logging")
    def test_guards_off_returns_zero(self, _log, mock_run, monkeypatch):
        monkeypatch.delenv("LIQUID_WIRE_ENABLED", raising=False)
        monkeypatch.delenv("LIQUID_WIRE_IDENTITY_ENABLED", raising=False)
        monkeypatch.setattr("sys.argv", ["upd"])
        assert upd.main() == 0
        mock_run.assert_not_called()

    @patch("scripts.update_channel_identity.record_pipeline_run")
    @patch("scripts.update_channel_identity.log_exception_to_file")
    @patch("scripts.update_channel_identity.run_identity_update", side_effect=RuntimeError("boom"))
    @patch("scripts.update_channel_identity._own_channel_id", return_value="UC123")
    @patch("scripts.update_channel_identity.get_youtube_service")
    @patch("scripts.update_channel_identity.configure_logging")
    def test_exception_returns_one(self, _log, _svc, mock_id, mock_run, mock_log_exc, mock_pipeline, monkeypatch):
        monkeypatch.setenv("LIQUID_WIRE_ENABLED", "1")
        monkeypatch.setenv("LIQUID_WIRE_IDENTITY_ENABLED", "1")
        monkeypatch.setattr("sys.argv", ["upd"])
        assert upd.main() == 1
        mock_log_exc.assert_called_once()
        mock_pipeline.assert_called_once()
        assert mock_pipeline.call_args.kwargs["stage"] == "channel_identity"
        assert mock_pipeline.call_args.kwargs["kind"] == "identity"
        assert mock_pipeline.call_args.kwargs["success"] is False
