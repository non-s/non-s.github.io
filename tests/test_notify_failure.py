"""Testes para scripts/notify_failure.py."""

from __future__ import annotations

from unittest.mock import patch

import scripts.notify_failure as notify_failure


def test_run_url_builds_from_env(monkeypatch):
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "non-s/non-s.github.io")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    assert notify_failure._run_url() == "https://github.com/non-s/non-s.github.io/actions/runs/123"


def test_run_url_missing_env(monkeypatch):
    monkeypatch.delenv("GITHUB_SERVER_URL", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    assert notify_failure._run_url() == "(run URL indisponivel)"


def test_main_calls_notify_error_with_workflow_name(monkeypatch):
    monkeypatch.setattr(notify_failure.sys, "argv", ["notify_failure.py", "Meu Workflow"])
    with patch.object(notify_failure, "notify_error") as mock_notify:
        assert notify_failure.main() == 0
        mock_notify.assert_called_once()
        args = mock_notify.call_args[0]
        assert "Meu Workflow" in args[0]


def test_main_falls_back_to_github_workflow_env(monkeypatch):
    monkeypatch.setattr(notify_failure.sys, "argv", ["notify_failure.py"])
    monkeypatch.setenv("GITHUB_WORKFLOW", "Workflow do Env")
    with patch.object(notify_failure, "notify_error") as mock_notify:
        notify_failure.main()
        args = mock_notify.call_args[0]
        assert "Workflow do Env" in args[0]
