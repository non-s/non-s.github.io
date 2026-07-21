"""Tests for utils/ai_titling.py."""

from __future__ import annotations

import json

from utils import ai_titling


def test_generate_video_copy_returns_none_when_no_provider_configured(monkeypatch):
    monkeypatch.setattr(ai_titling, "ai_text", lambda *a, **k: "")

    result = ai_titling.generate_video_copy(
        format_label="storm ambience",
        scene="deep sleep",
        duration_s=3600.0,
        fallback_title="Heavy Rain -- Amber Hours",
    )

    assert result is None


def test_generate_video_copy_parses_a_valid_response(monkeypatch):
    payload = json.dumps(
        {
            "title": "Deep Sleep Rain & Thunder -- Amber Hours",
            "description": "A calm rain session to help you fall asleep.\n\nEnjoy the quiet.",
            "hashtags": ["#RainSounds", "Sleep", "thunder "],
        }
    )
    monkeypatch.setattr(ai_titling, "ai_text", lambda *a, **k: payload)

    result = ai_titling.generate_video_copy(
        format_label="storm ambience",
        scene="deep sleep",
        duration_s=3600.0,
        fallback_title="Heavy Rain -- Amber Hours",
    )

    assert result["title"] == "Deep Sleep Rain & Thunder -- Amber Hours"
    assert "fall asleep" in result["description"]
    assert result["hashtags"] == ["rainsounds", "sleep", "thunder"]


def test_generate_video_copy_returns_none_on_invalid_json(monkeypatch):
    monkeypatch.setattr(ai_titling, "ai_text", lambda *a, **k: "not json at all")

    result = ai_titling.generate_video_copy(
        format_label="storm ambience", scene="focus", duration_s=1800.0, fallback_title="Rain -- Amber Hours"
    )

    assert result is None


def test_generate_video_copy_returns_none_when_a_required_field_is_missing(monkeypatch):
    monkeypatch.setattr(ai_titling, "ai_text", lambda *a, **k: json.dumps({"title": "Only a title"}))

    result = ai_titling.generate_video_copy(
        format_label="storm ambience", scene="focus", duration_s=1800.0, fallback_title="Rain -- Amber Hours"
    )

    assert result is None


def test_generate_video_copy_calls_ai_text_with_json_mode(monkeypatch):
    captured = {}

    def fake_ai_text(prompt, system="", json_mode=False, **kwargs):
        captured["prompt"] = prompt
        captured["system"] = system
        captured["json_mode"] = json_mode
        return json.dumps({"title": "T -- Amber Hours", "description": "D", "hashtags": ["rain"]})

    monkeypatch.setattr(ai_titling, "ai_text", fake_ai_text)

    ai_titling.generate_video_copy(
        format_label="storm short",
        scene="power nap",
        duration_s=45.0,
        fallback_title="Rain Nap -- Amber Hours",
        credits_lines=["Music: Test Track by Someone"],
    )

    assert captured["json_mode"] is True
    assert "power nap" in captured["prompt"]
    assert "Test Track" in captured["prompt"]
    assert "Amber Hours" in captured["system"]


def test_generate_video_copy_truncates_an_overlong_title(monkeypatch):
    long_title = "R" * 150
    monkeypatch.setattr(
        ai_titling,
        "ai_text",
        lambda *a, **k: json.dumps({"title": long_title, "description": "D", "hashtags": ["rain"]}),
    )

    result = ai_titling.generate_video_copy(
        format_label="storm ambience", scene="focus", duration_s=1800.0, fallback_title="Rain -- Amber Hours"
    )

    assert len(result["title"]) == 100
