"""tests/test_font_config.py — cobertura para utils/font_config.py."""

from __future__ import annotations

import pytest

from utils import font_config


@pytest.fixture(autouse=True)
def _ensure_bundled_font(tmp_path, monkeypatch):
    """Cria um arquivo de fonte falso para simular a fonte empacotada."""
    fake_root = tmp_path
    fake_font = fake_root / "_assets" / "fonts" / "Roboto-Bold.ttf"
    fake_font.parent.mkdir(parents=True, exist_ok=True)
    fake_font.write_text("fake font", encoding="utf-8")
    monkeypatch.setattr(font_config, "BUNDLED_FONT", fake_font)
    yield


def test_bundled_font_path():
    assert font_config.bundled_font_path() == font_config.BUNDLED_FONT


def test_resolve_font_prefers_bundled():
    assert font_config._resolve_font() == font_config.BUNDLED_FONT.resolve()


def test_font_path_ffmpeg_safe(tmp_path):
    path = font_config.font_path(ffmpeg_safe=True)
    assert "Roboto-Bold.ttf" in path
    # Se estiver em Windows, o drive ':' deve estar escapado.
    if len(path) >= 2 and path[1] == ":":
        assert path[0].isalpha()
        assert path[2] == "/"


def test_pil_font_path():
    path = font_config.pil_font_path()
    assert "Roboto-Bold.ttf" in path


def test_resolve_font_fallback(tmp_path, monkeypatch):
    """Se a fonte empacotada nao existir, usa a primeira fonte fallback encontrada."""
    fake_fallback = tmp_path / "fallback.ttf"
    fake_fallback.write_text("fallback", encoding="utf-8")
    monkeypatch.setattr(font_config, "BUNDLED_FONT", tmp_path / "missing.ttf")
    monkeypatch.setattr(font_config, "_FALLBACK_FONTS", [str(fake_fallback)])
    assert font_config._resolve_font() == fake_fallback.resolve()


def test_resolve_font_missing_raises(tmp_path, monkeypatch):
    """RuntimeError quando nenhuma fonte e encontrada."""
    monkeypatch.setattr(font_config, "BUNDLED_FONT", tmp_path / "missing.ttf")
    monkeypatch.setattr(font_config, "_FALLBACK_FONTS", [])
    with pytest.raises(RuntimeError):
        font_config._resolve_font()


def test_ffmpeg_escape_drive_colon():
    assert font_config._ffmpeg_escape_drive_colon("C:/foo/bar.ttf") == "C\\:/foo/bar.ttf"
    assert font_config._ffmpeg_escape_drive_colon("/foo/bar.ttf") == "/foo/bar.ttf"
