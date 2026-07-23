"""Testes para retry do YouTube API no upload_youtube.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from upload_youtube import _retry_youtube_call, _YOUTUBE_MAX_RETRIES


def test_retry_youtube_call_success():
    """Testa chamada bem-sucedida sem retry."""
    mock_func = MagicMock(return_value={"id": "test123"})
    result = _retry_youtube_call(mock_func, "arg1", kwarg="value")
    assert result == {"id": "test123"}
    mock_func.assert_called_once_with("arg1", kwarg="value")


@patch("upload_youtube.time.sleep")
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


@patch("upload_youtube.time.sleep")
def test_retry_youtube_call_retry_503(mock_sleep):
    """Testa retry para erro 503 (service unavailable)."""
    mock_func = MagicMock()
    error_503 = HttpError(MagicMock(status=503), b'{"error": "unavailable"}')
    mock_func.side_effect = [error_503, error_503, {"id": "test123"}]
    
    result = _retry_youtube_call(mock_func)
    assert result == {"id": "test123"}
    assert mock_func.call_count == 3
    assert mock_sleep.call_count == 2  # Dois backoffs


@patch("upload_youtube.time.sleep")
def test_retry_youtube_call_exhaust_retries(mock_sleep):
    """Testa esgotamento de retries."""
    mock_func = MagicMock()
    error_503 = HttpError(MagicMock(status=503), b'{"error": "unavailable"}')
    mock_func.side_effect = [error_503] * _YOUTUBE_MAX_RETRIES
    
    result = _retry_youtube_call(mock_func)
    assert result is None
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
