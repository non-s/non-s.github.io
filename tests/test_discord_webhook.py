"""Testes para discord_webhook.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from utils import discord_webhook


@patch("utils.discord_webhook._DISCORD_WEBHOOK_URL", "")
def test_send_notification_no_webhook():
    result = discord_webhook.send_notification("Teste", "Mensagem")
    assert result is False


@patch("utils.discord_webhook._DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
@patch("utils.discord_webhook.requests.post")
def test_send_notification_success(mock_post):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response
    
    result = discord_webhook.send_notification("Teste", "Mensagem")
    assert result is True
    mock_post.assert_called_once()


@patch("utils.discord_webhook._DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
@patch("utils.discord_webhook.requests.post")
def test_send_notification_failure(mock_post):
    import requests.exceptions
    mock_post.side_effect = requests.exceptions.RequestException("Erro")
    
    result = discord_webhook.send_notification("Teste", "Mensagem")
    assert result is False


@patch("utils.discord_webhook._DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
@patch("utils.discord_webhook.requests.post")
def test_notify_live_start(mock_post):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response
    
    result = discord_webhook.notify_live_start(
        title="Live Teste",
        stream_url="https://youtube.com/watch?v=test",
        thumbnail="https://img.youtube.com/test.jpg"
    )
    assert result is True
    call_args = mock_post.call_args
    assert call_args[1]["json"]["embeds"][0]["color"] == 0xff0000  # vermelho


@patch("utils.discord_webhook._DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
@patch("utils.discord_webhook.requests.post")
def test_notify_live_end(mock_post):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response
    
    result = discord_webhook.notify_live_end(title="Live Teste", duration_minutes=60)
    assert result is True
    call_args = mock_post.call_args
    assert call_args[1]["json"]["embeds"][0]["color"] == 0x808080  # cinza


@patch("utils.discord_webhook._DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
@patch("utils.discord_webhook.requests.post")
def test_notify_video_upload(mock_post):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response
    
    result = discord_webhook.notify_video_upload(
        title="Video Teste",
        video_url="https://youtube.com/watch?v=test"
    )
    assert result is True
    call_args = mock_post.call_args
    assert call_args[1]["json"]["embeds"][0]["color"] == 0x0000ff  # azul


@patch("utils.discord_webhook._DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
@patch("utils.discord_webhook.requests.post")
def test_notify_error(mock_post):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response
    
    result = discord_webhook.notify_error(
        error_message="Erro de teste",
        stack_trace="Traceback..."
    )
    assert result is True
    call_args = mock_post.call_args
    assert call_args[1]["json"]["embeds"][0]["color"] == 0xff0000  # vermelho
