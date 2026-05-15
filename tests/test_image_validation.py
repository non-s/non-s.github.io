"""Tests for image-validation helpers in post_bluesky.py and fetch_news.py."""
from unittest.mock import patch, MagicMock


def _resp(status=200, ctype="image/jpeg", length="8192"):
    r = MagicMock()
    r.status_code = status
    r.headers = {"Content-Type": ctype, "Content-Length": length}
    return r


def test_bluesky_image_usable_accepts_jpeg():
    from post_bluesky import _image_url_usable
    with patch("post_bluesky.requests.head", return_value=_resp(200, "image/jpeg", "9000")):
        assert _image_url_usable("https://e.test/x.jpg") is True


def test_bluesky_image_usable_rejects_too_small():
    from post_bluesky import _image_url_usable
    with patch("post_bluesky.requests.head", return_value=_resp(200, "image/jpeg", "512")):
        assert _image_url_usable("https://e.test/x.jpg") is False


def test_bluesky_image_usable_rejects_404():
    from post_bluesky import _image_url_usable
    with patch("post_bluesky.requests.head", return_value=_resp(404)):
        assert _image_url_usable("https://e.test/missing.jpg") is False


def test_bluesky_image_usable_rejects_html_content():
    from post_bluesky import _image_url_usable
    with patch("post_bluesky.requests.head", return_value=_resp(200, "text/html", "9000")):
        assert _image_url_usable("https://e.test/oops") is False


def test_bluesky_image_usable_rejects_empty():
    from post_bluesky import _image_url_usable
    assert _image_url_usable("") is False
    assert _image_url_usable(None) is False  # type: ignore[arg-type]


def test_bluesky_image_usable_falls_back_on_head_block():
    from post_bluesky import _image_url_usable
    head_resp = _resp(405)
    get_resp = _resp(200, "image/png", "20000")
    get_resp.close = MagicMock()
    with patch("post_bluesky.requests.head", return_value=head_resp), \
         patch("post_bluesky.requests.get", return_value=get_resp):
        assert _image_url_usable("https://e.test/blocked") is True


def test_bluesky_image_usable_normalises_relative_path():
    from post_bluesky import _image_url_usable
    captured = {}
    def fake_head(url, **kw):
        captured["url"] = url
        return _resp(200, "image/jpeg", "8192")
    with patch("post_bluesky.requests.head", side_effect=fake_head):
        assert _image_url_usable("/assets/images/posts/x.webp") is True
    assert captured["url"].endswith("/assets/images/posts/x.webp")
    assert captured["url"].startswith("http")
