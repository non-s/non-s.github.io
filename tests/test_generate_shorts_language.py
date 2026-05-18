"""Tests for LANGUAGE-axis behaviour in generate_shorts.py + upload_youtube.py.

We reload the modules in each test with a fresh LANGUAGE env so the
module-level path constants reflect the locale axis correctly.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

pytest.importorskip("PIL")


def _reload(name: str, language: str | None = None, monkeypatch=None):
    if language is None:
        monkeypatch.delenv("LANGUAGE", raising=False)
    else:
        monkeypatch.setenv("LANGUAGE", language)
    import sys
    if name in sys.modules:
        return importlib.reload(sys.modules[name])
    return importlib.import_module(name)


def test_default_language_uses_english_paths(monkeypatch):
    gs = _reload("generate_shorts", language=None, monkeypatch=monkeypatch)
    assert gs.LANGUAGE == "en"
    assert gs.VIDEOS_DIR == Path("_videos")
    assert gs.LOG_FILE == "generate_shorts.log"


def test_pt_br_switches_video_dir(monkeypatch):
    gs = _reload("generate_shorts", language="pt-BR", monkeypatch=monkeypatch)
    assert gs.LANGUAGE == "pt-BR"
    assert gs.VIDEOS_DIR == Path("_videos_pt-BR")
    assert gs.LOG_FILE == "generate_shorts_pt-BR.log"


def test_es_es_switches_video_dir(monkeypatch):
    gs = _reload("generate_shorts", language="es-ES", monkeypatch=monkeypatch)
    assert gs.VIDEOS_DIR == Path("_videos_es-ES")


def test_unsupported_language_raises(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "zz-ZZ")
    import sys
    if "generate_shorts" in sys.modules:
        del sys.modules["generate_shorts"]
    with pytest.raises(RuntimeError, match="LANGUAGE"):
        import generate_shorts  # noqa: F401


def test_upload_youtube_respects_language(monkeypatch):
    # upload_youtube transitively imports the google-auth crypto stack,
    # which crashes in sandboxes with a broken _cffi_backend (the
    # CI runner is fine). We probe with a forgiving try/except so the
    # test still gives signal where it can run.
    monkeypatch.setenv("LANGUAGE", "pt-BR")
    import sys
    if "upload_youtube" in sys.modules:
        del sys.modules["upload_youtube"]
    try:
        import upload_youtube
    except BaseException as exc:  # PanicException isn't a normal Exception
        pytest.skip(f"upload_youtube import blocked in sandbox: {exc}")
        return
    assert upload_youtube.VIDEOS_DIR == Path("_videos_pt-BR")
    assert upload_youtube.LOG_FILE == "upload_youtube_pt-BR.log"


def test_generate_short_translates_when_language_is_ptbr(monkeypatch, tmp_path):
    """The generate_short() flow calls translate_story when LANGUAGE != en."""
    gs = _reload("generate_shorts", language="pt-BR", monkeypatch=monkeypatch)

    translated = {
        "id": "abc", "slug": "test-slug", "date": "2026-05-18",
        "title": "Manchete em português",
        "seo_title": "Manchete em português",
        "hook": "O Fed cortou os juros.",
        "script": "O Fed cortou os juros. " * 20,
        "thumbnail_text": "JUROS CAÍRAM",
        "yt_description": "x", "yt_tags": ["fed"],
        "category": "business", "source": "Reuters",
        "language": "pt-BR", "voice_tag": "pt-BR",
        "image_url": "", "source_url": "",
    }
    from unittest.mock import patch
    # Mock every external call we'd otherwise need ffmpeg / edge-tts /
    # Pexels / Pixabay for. Without mocking add_music_bed the test
    # would actually hit Pixabay's CDN and leak a 4 MB MP3 into the
    # repo's _data/music_cache.
    with patch.object(gs, "translate_story", return_value=translated) as tx, \
         patch.object(gs, "acquire_broll_clips", return_value=[]), \
         patch.object(gs, "generate_captions", return_value=None), \
         patch.object(gs, "text_to_speech") as tts, \
         patch.object(gs, "add_music_bed", side_effect=lambda audio, story, tmp: audio), \
         patch.object(gs, "download_image", return_value=False), \
         patch.object(gs, "fetch_any_free_image", return_value=False), \
         patch.object(gs, "generate_ai_background", return_value=False):
        story = {
            "id": "abc", "slug": "test-slug", "date": "2026-05-18",
            "title": "English headline", "script": "x" * 200,
            "category": "business", "source": "Reuters",
            "image_url": "", "source_url": "",
        }
        # generate_short will fail on missing background; that's fine —
        # we just want to confirm translate_story was invoked.
        gs.generate_short(story, tmp_path)
    tx.assert_called_once_with(story, "pt-BR")
