"""Tests for utils/free_images.py — no live HTTP."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from utils import free_images


JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
PADDING = b"x" * 6000  # > _MIN_BYTES (5 KB) so the magic-byte check passes


def _fake_response(body: bytes, status: int = 200, content_type: str = "image/jpeg"):
    r = MagicMock()
    r.status_code = status
    r.content = body
    r.text = body.decode("utf-8", errors="replace")
    r.headers = {"Content-Type": content_type}
    return r


def test_looks_like_image_accepts_known_formats():
    assert free_images._looks_like_image(JPEG_MAGIC + PADDING)
    assert free_images._looks_like_image(PNG_MAGIC + PADDING)


def test_looks_like_image_rejects_tiny_body():
    assert not free_images._looks_like_image(JPEG_MAGIC + b"x")


def test_looks_like_image_rejects_html():
    assert not free_images._looks_like_image(b"<!doctype html><html>" + PADDING)


def test_download_writes_valid_image(tmp_path):
    dest = tmp_path / "out.jpg"
    body = JPEG_MAGIC + PADDING
    with patch("utils.free_images.requests.get", return_value=_fake_response(body)):
        assert free_images._download("https://e.test/x.jpg", dest)
    assert dest.exists()
    assert dest.read_bytes().startswith(JPEG_MAGIC)


def test_download_rejects_non_image_content_type(tmp_path):
    dest = tmp_path / "out.jpg"
    body = JPEG_MAGIC + PADDING
    bad = _fake_response(body, content_type="text/html")
    with patch("utils.free_images.requests.get", return_value=bad):
        assert not free_images._download("https://e.test/x.jpg", dest)
    assert not dest.exists()


def test_download_rejects_404(tmp_path):
    dest = tmp_path / "out.jpg"
    bad = _fake_response(b"", status=404, content_type="image/jpeg")
    with patch("utils.free_images.requests.get", return_value=bad):
        assert not free_images._download("https://e.test/x.jpg", dest)


def test_download_rejects_ssrf_shaped_urls(tmp_path):
    dest = tmp_path / "out.jpg"
    # No http(s) scheme → refused before any network call.
    with patch("utils.free_images.requests.get") as get:
        assert not free_images._download("file:///etc/passwd", dest)
        get.assert_not_called()


def test_og_image_extracts_meta_tag(tmp_path):
    dest = tmp_path / "out.jpg"
    html_body = b"""
        <html><head>
        <meta property="og:image" content="https://cdn.example.com/hero.jpg" />
        </head></html>
    """
    html_resp = MagicMock(status_code=200, text=html_body.decode())
    img_body = JPEG_MAGIC + PADDING

    def fake_get(url, **kwargs):
        if url == "https://news.example.com/article":
            return html_resp
        if url == "https://cdn.example.com/hero.jpg":
            return _fake_response(img_body)
        return _fake_response(b"", status=404)

    with patch("utils.free_images.requests.get", side_effect=fake_get):
        assert free_images.fetch_og_image("https://news.example.com/article", dest)
    assert dest.read_bytes().startswith(JPEG_MAGIC)


def test_og_image_resolves_relative_paths(tmp_path):
    dest = tmp_path / "out.jpg"
    html_body = """
        <html><head>
        <meta property="og:image" content="/hero.jpg" />
        </head></html>
    """
    html_resp = MagicMock(status_code=200, text=html_body)
    img_body = JPEG_MAGIC + PADDING
    seen_urls: list[str] = []

    def fake_get(url, **kwargs):
        seen_urls.append(url)
        if url.endswith("/article"):
            return html_resp
        return _fake_response(img_body)

    with patch("utils.free_images.requests.get", side_effect=fake_get):
        assert free_images.fetch_og_image("https://news.example.com/article", dest)
    assert "https://news.example.com/hero.jpg" in seen_urls


def test_og_image_returns_false_without_meta(tmp_path):
    dest = tmp_path / "out.jpg"
    html_resp = MagicMock(status_code=200, text="<html><head></head></html>")
    with patch("utils.free_images.requests.get", return_value=html_resp):
        assert not free_images.fetch_og_image("https://e.test/x", dest)


def test_og_image_returns_false_for_invalid_url(tmp_path):
    dest = tmp_path / "out.jpg"
    with patch("utils.free_images.requests.get") as get:
        assert not free_images.fetch_og_image("ftp://nope/", dest)
        get.assert_not_called()


def test_wikipedia_image_success(tmp_path):
    dest = tmp_path / "out.jpg"

    def fake_get(url, **kwargs):
        if "rest.php/v1/search/title" in url:
            return _fake_response_json({"pages": [{"key": "Jerome_Powell", "title": "Jerome Powell"}]})
        if "/page/summary/Jerome_Powell" in url:
            return _fake_response_json({
                "originalimage": {"source": "https://upload.wikimedia.org/p.jpg"},
            })
        if "upload.wikimedia.org" in url:
            return _fake_response(JPEG_MAGIC + PADDING)
        return _fake_response(b"", status=404)

    with patch.object(free_images, "_session") as factory:
        s = MagicMock()
        s.get.side_effect = fake_get
        factory.return_value = s
        with patch("utils.free_images.requests.get", side_effect=fake_get):
            ok = free_images.fetch_wikipedia_image("Jerome Powell", dest)
    assert ok
    assert dest.read_bytes().startswith(JPEG_MAGIC)


def _fake_response_json(payload, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    return r


def test_openverse_image_success(tmp_path):
    dest = tmp_path / "out.jpg"

    def fake_get_session(url, **kwargs):
        return _fake_response_json({
            "results": [
                {"url": "https://e.test/cc1.jpg", "thumbnail": "https://e.test/cc1-t.jpg"},
            ],
        })

    def fake_get_global(url, **kwargs):
        return _fake_response(JPEG_MAGIC + PADDING)

    with patch.object(free_images, "_session") as factory:
        s = MagicMock()
        s.get.side_effect = fake_get_session
        factory.return_value = s
        with patch("utils.free_images.requests.get", side_effect=fake_get_global):
            ok = free_images.fetch_openverse_image("solar panels", dest)
    assert ok


def test_fetch_any_free_image_short_circuits_on_first_hit(tmp_path):
    dest = tmp_path / "out.jpg"
    with patch.object(free_images, "fetch_og_image", return_value=True) as og:
        with patch.object(free_images, "fetch_wikipedia_image") as wiki:
            with patch.object(free_images, "fetch_openverse_image") as ov:
                assert free_images.fetch_any_free_image(
                    "https://e.test/article", "q", dest,
                )
                og.assert_called_once()
                wiki.assert_not_called()
                ov.assert_not_called()


def test_fetch_any_free_image_falls_through(tmp_path):
    dest = tmp_path / "out.jpg"
    with patch.object(free_images, "fetch_og_image", return_value=False):
        with patch.object(free_images, "fetch_wikipedia_image", return_value=False):
            with patch.object(free_images, "fetch_openverse_image", return_value=True) as ov:
                assert free_images.fetch_any_free_image(
                    "https://e.test/article", "subject", dest,
                )
                ov.assert_called_once()


def test_fetch_any_free_image_all_fail(tmp_path):
    dest = tmp_path / "out.jpg"
    with patch.object(free_images, "fetch_og_image", return_value=False):
        with patch.object(free_images, "fetch_wikipedia_image", return_value=False):
            with patch.object(free_images, "fetch_openverse_image", return_value=False):
                assert not free_images.fetch_any_free_image(
                    "https://e.test/article", "subject", dest,
                )
