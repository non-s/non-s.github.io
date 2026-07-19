"""Tests for utils/thumbnail_branding.py."""

from __future__ import annotations

from PIL import Image

from utils import thumbnail_branding as tb


def _close(a, b, tol=4):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def test_hook_words_strips_anime_lofi_suffix_for_known_mood():
    assert tb._hook_words("rain window") == "Rainy Night"


def test_hook_words_falls_back_to_raw_mood_for_unknown_mood():
    assert tb._hook_words("Snow Falling") == "Snow Falling"


def test_brand_short_thumbnail_preserves_size_and_overwrites_in_place(tmp_path):
    path = tmp_path / "short_thumb.jpg"
    Image.new("RGB", (1080, 1920), (80, 120, 160)).save(path, quality=90)
    original_bytes = path.read_bytes()

    tb.brand_short_thumbnail(path, "rain window")

    with Image.open(path) as im:
        assert im.size == (1080, 1920)
    assert path.read_bytes() != original_bytes


def test_brand_short_thumbnail_leaves_top_center_untouched(tmp_path):
    """The scrim/skyline/moon accents stay near the edges -- the middle of
    the frame is where the real footage should stay fully visible."""
    path = tmp_path / "short_thumb.jpg"
    Image.new("RGB", (1080, 1920), (80, 120, 160)).save(path, quality=95)

    tb.brand_short_thumbnail(path, "cat sleeping")

    with Image.open(path) as im:
        assert _close(im.getpixel((540, 960)), (80, 120, 160))


def test_brand_mix_thumbnail_preserves_size_and_overwrites_in_place(tmp_path):
    path = tmp_path / "mix_thumb.jpg"
    Image.new("RGB", (1920, 1080), (90, 60, 40)).save(path, quality=90)
    original_bytes = path.read_bytes()

    tb.brand_mix_thumbnail(path, "cat sleeping")

    with Image.open(path) as im:
        assert im.size == (1920, 1080)
    assert path.read_bytes() != original_bytes


def test_brand_mix_thumbnail_insets_the_real_frame_as_a_window(tmp_path):
    """The center of the canvas should still show the (cropped) real b-roll
    still, not just the illustrated background."""
    path = tmp_path / "mix_thumb.jpg"
    Image.new("RGB", (1920, 1080), (90, 60, 40)).save(path, quality=95)

    tb.brand_mix_thumbnail(path, "cat sleeping")

    with Image.open(path) as im:
        assert _close(im.getpixel((960, 540)), (90, 60, 40))
