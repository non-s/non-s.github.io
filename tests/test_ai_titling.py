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


def test_generate_animal_short_copy_returns_none_when_no_provider_configured(monkeypatch):
    monkeypatch.setattr(ai_titling, "ai_text", lambda *a, **k: "")

    result = ai_titling.generate_animal_short_copy(
        scene="cat", duration_s=45.0, fallback_title="Gatinho Fofo -- Pata Jazz"
    )

    assert result is None


def test_generate_animal_short_copy_parses_a_valid_response(monkeypatch):
    payload = json.dumps(
        {
            "title": "Gatinho Fazendo Arte -- Pata Jazz",
            "description": "Um gatinho fofo com jazz por cima. \U0001f43e",
            "hashtags": ["#GatoFofo", "Jazz", "pet "],
        }
    )
    monkeypatch.setattr(ai_titling, "ai_text", lambda *a, **k: payload)

    result = ai_titling.generate_animal_short_copy(
        scene="cat", duration_s=45.0, fallback_title="Gatinho Fofo -- Pata Jazz"
    )

    assert result["title"] == "Gatinho Fazendo Arte -- Pata Jazz"
    assert "jazz por cima" in result["description"]
    assert result["hashtags"] == ["gatofofo", "jazz", "pet"]


def test_generate_animal_short_copy_returns_none_on_invalid_json(monkeypatch):
    monkeypatch.setattr(ai_titling, "ai_text", lambda *a, **k: "not json at all")

    result = ai_titling.generate_animal_short_copy(scene="dog", duration_s=30.0, fallback_title="Cachorro -- Pata Jazz")

    assert result is None


def test_generate_animal_short_copy_returns_none_when_a_required_field_is_missing(monkeypatch):
    monkeypatch.setattr(ai_titling, "ai_text", lambda *a, **k: json.dumps({"title": "Only a title"}))

    result = ai_titling.generate_animal_short_copy(scene="dog", duration_s=30.0, fallback_title="Cachorro -- Pata Jazz")

    assert result is None


def test_generate_animal_short_copy_calls_ai_text_with_json_mode_and_pata_jazz_system(monkeypatch):
    captured = {}

    def fake_ai_text(prompt, system="", json_mode=False, **kwargs):
        captured["prompt"] = prompt
        captured["system"] = system
        captured["json_mode"] = json_mode
        return json.dumps({"title": "T -- Pata Jazz", "description": "D", "hashtags": ["gato"]})

    monkeypatch.setattr(ai_titling, "ai_text", fake_ai_text)

    ai_titling.generate_animal_short_copy(
        scene="bunny",
        duration_s=40.0,
        fallback_title="Coelhinho -- Pata Jazz",
        music_credit='Jazz: "Late Night Swing" por Someone',
    )

    assert captured["json_mode"] is True
    assert "bunny" in captured["prompt"]
    assert "Late Night Swing" in captured["prompt"]
    assert "Pata Jazz" in captured["system"]
    assert "Amber Hours" not in captured["system"]


def test_generate_baby_noise_copy_returns_none_when_no_provider_configured(monkeypatch):
    monkeypatch.setattr(ai_titling, "ai_text", lambda *a, **k: "")

    result = ai_titling.generate_baby_noise_copy(
        scene="white noise", color="white", duration_s=10800.0, fallback_title="Ruído Branco -- Amber Hours"
    )

    assert result is None


def test_generate_baby_noise_copy_parses_a_valid_response(monkeypatch):
    payload = json.dumps(
        {
            "title": "Ruído Marrom para o Bebê Dormir -- Amber Hours",
            "description": "Um som grave e constante para acalmar seu bebê a noite toda.",
            "hashtags": ["#RuidoMarrom", "Bebe", "dormir "],
        }
    )
    monkeypatch.setattr(ai_titling, "ai_text", lambda *a, **k: payload)

    result = ai_titling.generate_baby_noise_copy(
        scene="brown noise", color="brown", duration_s=10800.0, fallback_title="Ruído Marrom -- Amber Hours"
    )

    assert result["title"] == "Ruído Marrom para o Bebê Dormir -- Amber Hours"
    assert "acalmar seu bebê" in result["description"]
    assert result["hashtags"] == ["ruidomarrom", "bebe", "dormir"]


def test_generate_baby_noise_copy_returns_none_on_invalid_json(monkeypatch):
    monkeypatch.setattr(ai_titling, "ai_text", lambda *a, **k: "not json at all")

    result = ai_titling.generate_baby_noise_copy(
        scene="focus", color="pink", duration_s=3600.0, fallback_title="Ruído Rosa -- Amber Hours"
    )

    assert result is None


def test_generate_baby_noise_copy_returns_none_when_a_required_field_is_missing(monkeypatch):
    monkeypatch.setattr(ai_titling, "ai_text", lambda *a, **k: json.dumps({"title": "Only a title"}))

    result = ai_titling.generate_baby_noise_copy(
        scene="focus", color="pink", duration_s=3600.0, fallback_title="Ruído Rosa -- Amber Hours"
    )

    assert result is None


def test_generate_baby_noise_copy_calls_ai_text_with_json_mode_and_names_the_color(monkeypatch):
    captured = {}

    def fake_ai_text(prompt, system="", json_mode=False, **kwargs):
        captured["prompt"] = prompt
        captured["system"] = system
        captured["json_mode"] = json_mode
        return json.dumps({"title": "T -- Amber Hours", "description": "D", "hashtags": ["ruido"]})

    monkeypatch.setattr(ai_titling, "ai_text", fake_ai_text)

    ai_titling.generate_baby_noise_copy(
        scene="tinnitus", color="white", duration_s=3600.0, fallback_title="Ruído Branco -- Amber Hours"
    )

    assert captured["json_mode"] is True
    assert "tinnitus" in captured["prompt"]
    assert "white" in captured["prompt"]
    assert "Amber Hours" in captured["system"]


def test_generate_classical_video_copy_returns_none_when_no_provider_configured(monkeypatch):
    monkeypatch.setattr(ai_titling, "ai_text", lambda *a, **k: "")

    result = ai_titling.generate_classical_video_copy(
        mood="deep focus",
        duration_s=1800.0,
        track_name="Goldberg Variations, Aria",
        artist_name="Kimiko Ishizaka",
        fallback_title="Classical Piano for Deep Focus -- Amber Hours Classical",
    )

    assert result is None


def test_generate_classical_video_copy_parses_a_valid_response(monkeypatch):
    payload = json.dumps(
        {
            "title": "Bach's Goldberg Variations for Deep Focus -- Amber Hours Classical",
            "description": "Kimiko Ishizaka performs the Aria from Bach's Goldberg Variations. "
            "Perfect for reading, studying or a quiet evening.",
            "hashtags": ["#ClassicalMusic", "Piano", "focus "],
        }
    )
    monkeypatch.setattr(ai_titling, "ai_text", lambda *a, **k: payload)

    result = ai_titling.generate_classical_video_copy(
        mood="deep focus",
        duration_s=1800.0,
        track_name="Goldberg Variations, Aria",
        artist_name="Kimiko Ishizaka",
        fallback_title="Classical Piano for Deep Focus -- Amber Hours Classical",
    )

    assert result["title"] == "Bach's Goldberg Variations for Deep Focus -- Amber Hours Classical"
    assert "Kimiko Ishizaka" in result["description"]
    assert result["hashtags"] == ["classicalmusic", "piano", "focus"]


def test_generate_classical_video_copy_returns_none_on_invalid_json(monkeypatch):
    monkeypatch.setattr(ai_titling, "ai_text", lambda *a, **k: "not json at all")

    result = ai_titling.generate_classical_video_copy(
        mood="sleep",
        duration_s=1800.0,
        track_name="Nocturne",
        artist_name="Someone",
        fallback_title="Classical Music for Sleep -- Amber Hours Classical",
    )

    assert result is None


def test_generate_classical_video_copy_returns_none_when_a_required_field_is_missing(monkeypatch):
    monkeypatch.setattr(ai_titling, "ai_text", lambda *a, **k: json.dumps({"title": "Only a title"}))

    result = ai_titling.generate_classical_video_copy(
        mood="sleep",
        duration_s=1800.0,
        track_name="Nocturne",
        artist_name="Someone",
        fallback_title="Classical Music for Sleep -- Amber Hours Classical",
    )

    assert result is None


def test_generate_classical_video_copy_calls_ai_text_with_json_mode_and_english_system(monkeypatch):
    captured = {}

    def fake_ai_text(prompt, system="", json_mode=False, **kwargs):
        captured["prompt"] = prompt
        captured["system"] = system
        captured["json_mode"] = json_mode
        return json.dumps({"title": "T -- Amber Hours Classical", "description": "D", "hashtags": ["classical"]})

    monkeypatch.setattr(ai_titling, "ai_text", fake_ai_text)

    ai_titling.generate_classical_video_copy(
        mood="reading",
        duration_s=900.0,
        track_name="Clair de Lune",
        artist_name="Some Pianist",
        fallback_title="Classical Music for Reading -- Amber Hours Classical",
    )

    assert captured["json_mode"] is True
    assert "reading" in captured["prompt"]
    assert "Clair de Lune" in captured["prompt"]
    assert "Some Pianist" in captured["prompt"]
    assert "Amber Hours Classical" in captured["system"]
    assert "write in English" in captured["system"]
