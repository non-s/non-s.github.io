"""Unit tests for utils/video_common.py."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

pytest.importorskip("PIL")
from utils.video_common import (  # noqa: E402
    get_font,
    draw_rounded_rect,
    wrap_text,
    download_image,
    _BOLD_FONTS,
    _REGULAR_FONTS,
)


def test_get_font_returns_a_font():
    font = get_font(24)
    assert font is not None
    # Either a truetype font (when system fonts available) or the bitmap fallback.
    assert hasattr(font, "getbbox") or hasattr(font, "getsize")


def test_get_font_falls_back_when_no_truetype(monkeypatch):
    # Force every candidate path to "not exist" → fallback path is taken.
    monkeypatch.setattr(
        "utils.video_common._BOLD_FONTS",
        ["/nope/missing-bold.ttf"],
    )
    monkeypatch.setattr(
        "utils.video_common._REGULAR_FONTS",
        ["/nope/missing-regular.ttf"],
    )
    font = get_font(24, bold=True)
    assert font is not None


def test_draw_rounded_rect_calls_underlying_pillow_method():
    draw = MagicMock()
    draw_rounded_rect(draw, (0, 0, 10, 10), radius=4, fill=(1, 2, 3))
    assert draw.rounded_rectangle.called
    call_args = draw.rounded_rectangle.call_args
    assert call_args.args[0] == [0, 0, 10, 10]
    assert call_args.kwargs["radius"] == 4
    assert call_args.kwargs["fill"] == (1, 2, 3)


def test_wrap_text_breaks_on_max_width():
    """Simulate `textbbox` so wrap_text breaks when accumulated width exceeds the limit."""
    draw = MagicMock()
    # Each character contributes width 10, plus 10 per space.
    def fake_bbox(xy, text, font=None):
        return (0, 0, len(text) * 10, 20)
    draw.textbbox.side_effect = fake_bbox

    lines = wrap_text(draw, "alpha beta gamma delta", font=None, max_width=110)
    # 110 ≈ "alpha beta" (10 chars) → fits; adding " gamma" overflows.
    assert lines == ["alpha beta", "gamma delta"]


def test_wrap_text_handles_empty_string():
    draw = MagicMock()
    draw.textbbox.return_value = (0, 0, 0, 0)
    assert wrap_text(draw, "", font=None, max_width=100) == []


def test_download_image_writes_file_on_success(tmp_path):
    dest = tmp_path / "out.jpg"
    fake_resp = MagicMock(status_code=200, content=b"\xff\xd8" + b"x" * 5000)
    with patch("utils.video_common.requests.get", return_value=fake_resp):
        ok = download_image("https://example.com/x.jpg", dest, timeout=5)
    assert ok is True
    assert dest.read_bytes().startswith(b"\xff\xd8")


def test_download_image_rejects_small_response(tmp_path):
    dest = tmp_path / "out.jpg"
    # Body too small (<2KB) → should refuse to write.
    fake_resp = MagicMock(status_code=200, content=b"x" * 500)
    with patch("utils.video_common.requests.get", return_value=fake_resp):
        ok = download_image("https://example.com/x.jpg", dest)
    assert ok is False
    assert not dest.exists()


def test_download_image_handles_network_error(tmp_path):
    dest = tmp_path / "out.jpg"
    with patch("utils.video_common.requests.get", side_effect=RuntimeError("nope")):
        ok = download_image("https://example.com/x.jpg", dest)
    assert ok is False
    assert not dest.exists()


def test_download_image_handles_4xx(tmp_path):
    dest = tmp_path / "out.jpg"
    fake_resp = MagicMock(status_code=404, content=b"x" * 5000)
    with patch("utils.video_common.requests.get", return_value=fake_resp):
        ok = download_image("https://example.com/x.jpg", dest)
    assert ok is False
    assert not dest.exists()
