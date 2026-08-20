"""Targeted coverage for utils/ai_helper.py uncovered paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import utils.ai_helper as ai_helper


@pytest.fixture(autouse=True)
def _isolate_metrics(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(ai_helper, "_ai_metrics_file", lambda: tmp_path / "ai_metrics.json")
    ai_helper._gemini_429_streak = 0
    ai_helper._gemini_circuit_open = False
    ai_helper._gemini_circuit_open_until = 0.0
    yield
    ai_helper._gemini_429_streak = 0
    ai_helper._gemini_circuit_open = False
    ai_helper._gemini_circuit_open_until = 0.0


def test_is_safe_ai_text_rejects_medical_healing_claims() -> None:
    assert ai_helper.is_safe_ai_text("This music provides healing") is False
    assert ai_helper.is_safe_ai_text("anxiety relief for everyone") is False
    assert ai_helper.is_safe_ai_text("therapy music for deep sleep") is False
    assert ai_helper.is_safe_ai_text("cure for stress") is False
    assert ai_helper.is_safe_ai_text("reduce anxiety with ambient") is False


def test_is_safe_ai_text_accepts_clean_text() -> None:
    assert ai_helper.is_safe_ai_text("A calm generative visual moment") is True


def test_default_system_prompt_contains_generative_art_terms() -> None:
    prompt = ai_helper._default_system_prompt()
    assert "generative art" in prompt.lower() or "generative" in prompt.lower()
    assert "procedural music" in prompt.lower()
    assert "English" in prompt
    assert "Liquid Wire" in prompt


def test_gemini_kill_switch_uses_fallback_without_network(monkeypatch) -> None:
    monkeypatch.setenv("LIQUID_WIRE_DISABLE_GEMINI", "1")
    with patch.object(ai_helper._session, "post") as post:
        assert ai_helper.ai_text("prompt", task="kill_switch") == ""
        post.assert_not_called()
    data = __import__("json").loads(ai_helper._ai_metrics_file().read_text(encoding="utf-8"))
    assert data[-1]["fell_back"] is True
    assert data[-1]["prompt_hash"]


@patch("utils.ai_helper._session")
@patch("utils.ai_helper.os.environ")
def test_ai_grounded_research_no_key_returns_empty(mock_env, mock_session) -> None:
    mock_env.get.return_value = ""
    result = ai_helper.ai_grounded_research("query")
    assert result == {"text": "", "sources": []}
    mock_session.post.assert_not_called()


@patch("utils.ai_helper._session")
@patch("utils.ai_helper.os.environ")
def test_ai_grounded_research_success_with_sources(mock_env, mock_session) -> None:
    mock_env.get.return_value = "key"
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {"parts": [{"text": "Research result"}]},
                "groundingMetadata": {
                    "groundingChunks": [
                        {"web": {"title": "Source A", "uri": "https://example.com/a"}},
                        {"web": {"uri": "https://example.com/b"}},
                    ]
                },
            }
        ]
    }
    mock_session.post.return_value = mock_response
    result = ai_helper.ai_grounded_research("query")
    assert result["text"] == "Research result"
    assert len(result["sources"]) == 2
    assert result["sources"][0]["url"] == "https://example.com/a"
    assert result["sources"][1]["title"] == ""


@patch("utils.ai_helper._session")
@patch("utils.ai_helper.os.environ")
def test_ai_grounded_research_request_exception_returns_empty(mock_env, mock_session) -> None:
    import requests

    mock_env.get.return_value = "key"
    mock_session.post.side_effect = requests.RequestException("boom")
    result = ai_helper.ai_grounded_research("query")
    assert result == {"text": "", "sources": []}


@patch("utils.ai_helper._session")
@patch("utils.ai_helper.os.environ")
def test_ai_batch_metadata_returns_parsed_dict(mock_env, mock_session) -> None:
    mock_env.get.return_value = "key"
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": '{"title": "T", "hook": "H"}'}]}}]
    }
    mock_session.post.return_value = mock_response
    result = ai_helper.ai_batch_metadata("prompt")
    assert result == {"title": "T", "hook": "H"}


@patch("utils.ai_helper._session")
@patch("utils.ai_helper.os.environ")
def test_ai_batch_metadata_returns_none_on_empty(mock_env, mock_session) -> None:
    mock_env.get.return_value = "key"
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"candidates": []}
    mock_session.post.return_value = mock_response
    assert ai_helper.ai_batch_metadata("prompt") is None


@patch("utils.ai_helper.ai_text", return_value="{bad json")
def test_ai_batch_metadata_invalid_json_returns_none(_mock) -> None:
    assert ai_helper.ai_batch_metadata("prompt") is None


@patch("utils.ai_helper.ai_text", return_value='["not", "a", "dict"]')
def test_ai_batch_metadata_non_dict_returns_none(_mock) -> None:
    assert ai_helper.ai_batch_metadata("prompt") is None


@patch("utils.ai_helper.sleep")
@patch("utils.ai_helper._session")
@patch("utils.ai_helper.os.environ")
def test_circuit_breaker_opens_after_5_consecutive_429s(mock_env, mock_session, mock_sleep) -> None:
    import requests

    mock_env.get.return_value = "key"
    mock_response = MagicMock()
    mock_response.status_code = 429
    http_429 = requests.exceptions.HTTPError("429", response=mock_response)
    mock_response.raise_for_status.side_effect = http_429
    mock_session.post.return_value = mock_response

    ai_helper._gemini_429_streak = ai_helper._GEMINI_429_CIRCUIT_THRESHOLD - ai_helper._MAX_RETRIES
    ai_helper._gemini_circuit_open = False
    result = ai_helper.ai_text("prompt")
    assert result == ""
    assert ai_helper._gemini_429_streak >= ai_helper._GEMINI_429_CIRCUIT_THRESHOLD
    assert ai_helper._gemini_circuit_open is True
    assert ai_helper._gemini_circuit_open_until > 0.0
