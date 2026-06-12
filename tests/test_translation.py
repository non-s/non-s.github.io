"""Tests for utils/translation.py — no live AI calls."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest


def _english_story() -> dict:
    return {
        "id": "abc123",
        "seo_title": "Octopus camouflage happens in seconds",
        "hook": "This octopus can disappear against a reef in seconds.",
        "script": "This octopus can disappear against a reef in seconds. "
        "Its skin cells shift colour while tiny muscles alter "
        "texture. Here's how the disguise works.",
        "thumbnail_text": "INVISIBLE IN SECONDS",
        "yt_description": "This octopus changes colour and texture in seconds. " "Source: Pexels\n#Shorts #AnimalFacts",
        "yt_tags": ["octopus", "camouflage", "cephalopod", "animal facts"],
        "category": "ocean",
    }


def _ptbr_json_response() -> str:
    return json.dumps(
        {
            "seo_title": "Polvo muda de cor em segundos",
            "hook": "Este polvo desaparece no recife em segundos.",
            "script": "Este polvo desaparece no recife em segundos. "
            "As células da pele mudam de cor e pequenos músculos "
            "alteram a textura. Veja como funciona.",
            "thumbnail_text": "INVISÍVEL EM SEGUNDOS",
            "yt_description": "Este polvo muda de cor e textura em segundos. " "Fonte: Pexels\n#Shorts #Animais",
            "lead": "Polvo muda de cor e textura em segundos.",
        }
    )


def test_translate_story_pt_br_happy_path():
    from utils import translation

    with patch("utils.translation.ai_text", return_value=_ptbr_json_response()):
        out = translation.translate_story(_english_story(), "pt-BR")
    assert out is not None
    assert out["seo_title"].startswith("Polvo muda")
    assert out["hook"].startswith("Este polvo")
    assert out["thumbnail_text"] == "INVISÍVEL EM SEGUNDOS"
    # English-only metadata preserved.
    assert out["yt_tags"] == ["octopus", "camouflage", "cephalopod", "animal facts"]
    assert out["category"] == "ocean"
    # Locale metadata stamped.
    assert out["language"] == "pt-BR"
    assert out["voice_tag"] == "pt-BR"
    assert out["lang_hashtag"] == "BR"


def test_translate_story_original_dict_not_mutated():
    from utils import translation

    src = _english_story()
    original_title = src["seo_title"]
    with patch("utils.translation.ai_text", return_value=_ptbr_json_response()):
        translation.translate_story(src, "pt-BR")
    assert src["seo_title"] == original_title  # untouched


def test_translate_story_rejects_unsupported_lang():
    from utils import translation

    assert translation.translate_story(_english_story(), "ja-JP") is None


def test_translate_story_returns_none_on_empty_ai():
    from utils import translation

    with patch("utils.translation.ai_text", return_value=""):
        out = translation.translate_story(_english_story(), "pt-BR")
    assert out is None


def test_translate_story_handles_malformed_json():
    from utils import translation

    with patch("utils.translation.ai_text", return_value="not json at all"):
        out = translation.translate_story(_english_story(), "pt-BR")
    assert out is None


def test_translate_story_strips_code_fences():
    from utils import translation

    fenced = "```json\n" + _ptbr_json_response() + "\n```"
    with patch("utils.translation.ai_text", return_value=fenced):
        out = translation.translate_story(_english_story(), "pt-BR")
    assert out is not None
    assert out["hook"].startswith("Este polvo")


def test_translate_story_skips_when_no_translatable_fields():
    from utils import translation

    empty_story = {"id": "x", "category": "ocean", "yt_tags": ["a"]}
    out = translation.translate_story(empty_story, "pt-BR")
    assert out is None


def test_translate_stories_batch_filters_failures():
    from utils import translation

    stories = [_english_story(), _english_story()]
    responses = iter([_ptbr_json_response(), ""])  # second one fails

    def fake(*a, **kw):
        return next(responses)

    with patch("utils.translation.ai_text", side_effect=fake):
        out = translation.translate_stories(stories, "pt-BR")
    assert len(out) == 1


def test_pt_br_es_fr_codes_are_supported():
    from utils.translation import SUPPORTED_LANGUAGES

    assert "pt-BR" in SUPPORTED_LANGUAGES
    assert "es-ES" in SUPPORTED_LANGUAGES
    assert "es-MX" in SUPPORTED_LANGUAGES
    assert "fr-FR" in SUPPORTED_LANGUAGES
