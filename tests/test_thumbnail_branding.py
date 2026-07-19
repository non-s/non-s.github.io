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
    the frame is where the real footage should stay fully visible. Checked
    for every layout: whichever one a video happens to land on, the center
    of the frame must never get covered."""
    for layout in tb.SHORT_LAYOUTS:
        path = tmp_path / f"short_thumb_{layout}.jpg"
        Image.new("RGB", (1080, 1920), (80, 120, 160)).save(path, quality=95)

        tb.brand_short_thumbnail(path, "cat sleeping", layout=layout)

        with Image.open(path) as im:
            assert _close(im.getpixel((540, 960)), (80, 120, 160))


def test_brand_short_thumbnail_top_layout_puts_the_scrim_at_the_top_not_the_bottom(tmp_path):
    path = tmp_path / "short_thumb.jpg"
    Image.new("RGB", (1080, 1920), (80, 120, 160)).save(path, quality=95)

    tb.brand_short_thumbnail(path, "cat sleeping", layout="top")

    with Image.open(path) as im:
        # Top-left corner (under the wordmark/scrim) is branded, not the
        # plain fill color; y=1612 sits inside the *bottom* scrim band this
        # layout does NOT use, and above the skyline's max height, so it
        # must still read as the untouched fill color.
        assert not _close(im.getpixel((10, 10)), (80, 120, 160))
        assert _close(im.getpixel((10, 1612)), (80, 120, 160))


def test_brand_short_thumbnail_bottom_layout_puts_the_scrim_at_the_bottom(tmp_path):
    path = tmp_path / "short_thumb.jpg"
    Image.new("RGB", (1080, 1920), (80, 120, 160)).save(path, quality=95)

    tb.brand_short_thumbnail(path, "cat sleeping", layout="bottom")

    with Image.open(path) as im:
        assert _close(im.getpixel((10, 10)), (80, 120, 160))
        assert not _close(im.getpixel((10, 1612)), (80, 120, 160))


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
    still, not just the illustrated background -- checked for every layout,
    since the inset window's position must never move between them."""
    for layout in tb.MIX_LAYOUTS:
        path = tmp_path / f"mix_thumb_{layout}.jpg"
        Image.new("RGB", (1920, 1080), (90, 60, 40)).save(path, quality=95)

        tb.brand_mix_thumbnail(path, "cat sleeping", layout=layout)

        with Image.open(path) as im:
            assert _close(im.getpixel((960, 540)), (90, 60, 40))


def test_brand_mix_thumbnail_mirror_layout_moves_the_badge_to_the_right(tmp_path):
    path_classic = tmp_path / "mix_classic.jpg"
    path_mirror = tmp_path / "mix_mirror.jpg"
    Image.new("RGB", (1920, 1080), (90, 60, 40)).save(path_classic, quality=95)
    Image.new("RGB", (1920, 1080), (90, 60, 40)).save(path_mirror, quality=95)

    tb.brand_mix_thumbnail(path_classic, "cat sleeping", layout="classic")
    tb.brand_mix_thumbnail(path_mirror, "cat sleeping", layout="mirror")

    with Image.open(path_classic) as classic, Image.open(path_mirror) as mirror:
        # A point inside the bottom-left badge region: red-filled ((200,
        # 56, 58), R > 150) in "classic"; in "mirror" the badge moved to
        # the right so this point is illustrated background instead (both
        # the purple gradient and the skyline's NIGHT_BLUE keep R well
        # under 150).
        assert classic.getpixel((120, 900))[0] > 150
        assert mirror.getpixel((120, 900))[0] < 150
