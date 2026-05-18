"""Tests for utils/translation.py — no live AI calls."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest


def _english_story() -> dict:
    return {
        "id": "abc123",
        "seo_title":      "Fed cuts rates — and that breaks the inflation story",
        "hook":           "The Fed just cut rates by 50 basis points.",
        "script":         "The Fed just cut rates by 50 basis points. "
                          "Inflation isn't done yet. Markets called this 6 weeks "
                          "ago — Powell's just catching up. Here's why mortgage "
                          "rates won't follow.",
        "thumbnail_text": "RATES CUT",
        "yt_description": "The Fed just cut rates 50bps. Markets had priced this in. "
                          "Source: Reuters\n#Shorts #WorldNews",
        "yt_tags": ["fed", "powell", "rates", "world news"],
        "category": "business",
    }


def _ptbr_json_response() -> str:
    return json.dumps({
        "seo_title":      "Fed corta juros — e a história da inflação muda",
        "hook":           "O Fed acabou de cortar 50 pontos-base.",
        "script":         "O Fed acabou de cortar 50 pontos-base. "
                          "A inflação ainda não acabou. Os mercados já tinham "
                          "precificado isso há 6 semanas. Aqui está o porquê.",
        "thumbnail_text": "JUROS CAÍRAM",
        "yt_description": "O Fed cortou juros em 50pb. Os mercados já esperavam. "
                          "Fonte: Reuters\n#Shorts #Noticias",
        "lead":           "Fed corta juros, inflação ainda não acabou.",
    })


def test_translate_story_pt_br_happy_path():
    from utils import translation
    with patch("utils.translation.ai_text", return_value=_ptbr_json_response()):
        out = translation.translate_story(_english_story(), "pt-BR")
    assert out is not None
    assert out["seo_title"].startswith("Fed corta juros")
    assert out["hook"].startswith("O Fed")
    assert out["thumbnail_text"] == "JUROS CAÍRAM"
    # English-only metadata preserved.
    assert out["yt_tags"] == ["fed", "powell", "rates", "world news"]
    assert out["category"] == "business"
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
    assert out["hook"].startswith("O Fed")


def test_translate_story_skips_when_no_translatable_fields():
    from utils import translation
    empty_story = {"id": "x", "category": "world", "yt_tags": ["a"]}
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
