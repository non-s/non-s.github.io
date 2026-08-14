"""Testes para utils/notifier.py."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from utils import notifier


def test_send_alert_no_webhook_returns_false(monkeypatch, caplog):
    monkeypatch.delenv(notifier.WEBHOOK_ENV, raising=False)
    with caplog.at_level("INFO", logger="utils.notifier"):
        result = notifier.send_alert("hello", level="warning")
    assert result is False
    assert "hello" in caplog.text


def test_send_alert_no_webhook_env_blank_returns_false(monkeypatch):
    monkeypatch.setenv(notifier.WEBHOOK_ENV, "   ")
    assert notifier.send_alert("hi") is False


def test_send_alert_slack_payload(monkeypatch):
    monkeypatch.setenv(notifier.WEBHOOK_ENV, "https://hooks.slack.com/services/T/B/xxx")
    captured: dict = {}

    class FakeResp:
        status = 200

        def getcode(self):
            return 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        captured["req"] = req
        captured["timeout"] = timeout
        return FakeResp()

    with patch("utils.notifier.urllib.request.urlopen", side_effect=fake_urlopen):
        result = notifier.send_alert("quota alert", level="warning")

    assert result is True
    body = json.loads(captured["req"].data.decode("utf-8"))
    assert body == {"text": "quota alert"}
    assert captured["req"].method == "POST"
    assert captured["req"].headers["Content-type"] == "application/json"
    assert captured["timeout"] == notifier._TIMEOUT_SECONDS


def test_send_alert_generic_payload(monkeypatch):
    monkeypatch.setenv(notifier.WEBHOOK_ENV, "https://example.com/webhook")
    captured: dict = {}

    class FakeResp:
        status = 200

        def getcode(self):
            return 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        captured["req"] = req
        return FakeResp()

    with patch("utils.notifier.urllib.request.urlopen", side_effect=fake_urlopen):
        result = notifier.send_alert("drift alert", level="error")

    assert result is True
    body = json.loads(captured["req"].data.decode("utf-8"))
    assert body == {
        "level": "error",
        "message": "drift alert",
        "source": "liquid-wire",
    }


def test_send_alert_non_2xx_returns_false(monkeypatch):
    monkeypatch.setenv(notifier.WEBHOOK_ENV, "https://example.com/webhook")

    class FakeResp:
        status = 500

        def getcode(self):
            return 500

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with patch("utils.notifier.urllib.request.urlopen", return_value=FakeResp()):
        result = notifier.send_alert("hi")
    assert result is False


def test_send_alert_network_error_returns_false(monkeypatch):
    monkeypatch.setenv(notifier.WEBHOOK_ENV, "https://example.com/webhook")
    with patch("utils.notifier.urllib.request.urlopen", side_effect=OSError("boom")):
        result = notifier.send_alert("hi")
    assert result is False


def test_send_alert_default_level(monkeypatch):
    monkeypatch.setenv(notifier.WEBHOOK_ENV, "https://example.com/webhook")
    captured: dict = {}

    class FakeResp:
        status = 200

        def getcode(self):
            return 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        captured["req"] = req
        return FakeResp()

    with patch("utils.notifier.urllib.request.urlopen", side_effect=fake_urlopen):
        notifier.send_alert("msg")

    body = json.loads(captured["req"].data.decode("utf-8"))
    assert body["level"] == "warning"


def test_is_slack_webhook_detects_slack():
    assert notifier._is_slack_webhook("https://hooks.slack.com/services/T/B/x") is True
    assert notifier._is_slack_webhook("https://example.com/hook") is False


def test_send_alert_uses_urllib_request(monkeypatch):
    """Garante que usa stdlib urllib.request (sem adicionar dependencia requests)."""
    monkeypatch.setenv(notifier.WEBHOOK_ENV, "https://example.com/webhook")
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value.getcode.return_value = 200
    mock_urlopen.return_value.__enter__.return_value.status = 200
    with patch("utils.notifier.urllib.request.urlopen", mock_urlopen):
        assert notifier.send_alert("x") is True
    mock_urlopen.assert_called_once()
