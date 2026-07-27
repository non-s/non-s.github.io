"""Testes para retry do YouTube API em utils/youtube_retry.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from utils.youtube_retry import _YOUTUBE_MAX_RETRIES
from utils.youtube_retry import retry_youtube_call as _retry_youtube_call


def test_retry_youtube_call_success():
    """Testa chamada bem-sucedida sem retry."""
    mock_func = MagicMock(return_value={"id": "test123"})
    result = _retry_youtube_call(mock_func, "arg1", kwarg="value")
    assert result == {"id": "test123"}
    mock_func.assert_called_once_with("arg1", kwarg="value")


@patch("utils.youtube_retry.time.sleep")
def test_retry_youtube_call_retry_429(mock_sleep):
    """Testa retry para erro 429 (rate limit)."""
    mock_func = MagicMock()
    # Primeira chamada falha com 429, segunda tem sucesso
    error_429 = HttpError(MagicMock(status=429), b'{"error": "rate limit"}')
    mock_func.side_effect = [error_429, {"id": "test123"}]

    result = _retry_youtube_call(mock_func)
    assert result == {"id": "test123"}
    assert mock_func.call_count == 2
    mock_sleep.assert_called_once()  # Backoff


@patch("utils.youtube_retry.time.sleep")
def test_retry_youtube_call_retry_503(mock_sleep):
    """Testa retry para erro 503 (service unavailable)."""
    mock_func = MagicMock()
    error_503 = HttpError(MagicMock(status=503), b'{"error": "unavailable"}')
    mock_func.side_effect = [error_503, error_503, {"id": "test123"}]

    result = _retry_youtube_call(mock_func)
    assert result == {"id": "test123"}
    assert mock_func.call_count == 3
    assert mock_sleep.call_count == 2  # Dois backoffs


@patch("utils.youtube_retry.time.sleep")
def test_retry_youtube_call_exhaust_retries(mock_sleep):
    """Testa esgotamento de retries."""
    mock_func = MagicMock()
    error_503 = HttpError(MagicMock(status=503), b'{"error": "unavailable"}')
    mock_func.side_effect = [error_503] * _YOUTUBE_MAX_RETRIES

    with pytest.raises(RuntimeError, match="maximo de tentativas"):
        _retry_youtube_call(mock_func)
    assert mock_func.call_count == _YOUTUBE_MAX_RETRIES
    # Sleep é chamado após cada tentativa (incluindo a última)
    assert mock_sleep.call_count == _YOUTUBE_MAX_RETRIES


def test_retry_youtube_call_non_retryable_400():
    """Testa que erro 400 não faz retry."""
    mock_func = MagicMock()
    error_400 = HttpError(MagicMock(status=400), b'{"error": "bad request"}')
    mock_func.side_effect = error_400

    with pytest.raises(HttpError):
        _retry_youtube_call(mock_func)

    assert mock_func.call_count == 1  # Sem retry


@patch("utils.youtube_retry.time.sleep")
def test_retry_youtube_call_network_error_then_success(mock_sleep):
    """Erro de rede transitório (OSError) faz retry e depois sucede."""
    mock_func = MagicMock()
    mock_func.side_effect = [OSError("net boom"), {"id": "ok"}]
    result = _retry_youtube_call(mock_func)
    assert result == {"id": "ok"}
    assert mock_func.call_count == 2
    mock_sleep.assert_called()


@patch("utils.youtube_retry.time.sleep")
def test_retry_youtube_call_network_error_exhausts(mock_sleep):
    """Erro de rede persistente esgota retries e re-raise."""
    mock_func = MagicMock()
    mock_func.side_effect = ConnectionError("dead")
    with pytest.raises(ConnectionError):
        _retry_youtube_call(mock_func)
    assert mock_func.call_count == _YOUTUBE_MAX_RETRIES


@patch("utils.youtube_retry.time.sleep")
def test_retry_youtube_call_timeout_error_retries(mock_sleep):
    """TimeoutError é tratado como rede transitória."""
    mock_func = MagicMock()
    mock_func.side_effect = [TimeoutError("slow"), {"id": "ok"}]
    result = _retry_youtube_call(mock_func)
    assert result == {"id": "ok"}
    assert mock_func.call_count == 2


def test_retry_youtube_call_propagates_value_error():
    """Bugs de programação (ValueError) não fazem retry."""
    mock_func = MagicMock()
    mock_func.side_effect = ValueError("bug")
    with pytest.raises(ValueError):
        _retry_youtube_call(mock_func)
    assert mock_func.call_count == 1


def test_retry_youtube_call_httperror_without_resp():
    """HttpError com resp.status ausente/zero não é retryable."""
    mock_func = MagicMock()
    err = HttpError(MagicMock(), b'{"error": "x"}')
    # resp.status = 0 -> nao bate em nenhum dos status retryable
    err.resp = MagicMock(status=0)
    mock_func.side_effect = err
    with pytest.raises(HttpError):
        _retry_youtube_call(mock_func)
    assert mock_func.call_count == 1
