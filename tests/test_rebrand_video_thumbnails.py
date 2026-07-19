"""Tests for scripts/rebrand_video_thumbnails.py."""

from __future__ import annotations

from PIL import Image

import scripts.rebrand_video_thumbnails as rvt


def test_hook_from_title_strips_brand_suffix_and_anime_lofi():
    assert rvt._hook_from_title("Rainy Night Anime Lofi — Amber Hours \U0001f327️") == "Rainy Night"


def test_hook_from_title_strips_one_hour_marker_for_mixes():
    assert rvt._hook_from_title("Sleepy Cat Anime Lofi (1 Hour) — Amber Hours \U0001f43e") == "Sleepy Cat"


def test_hook_from_title_leaves_phrases_that_dont_end_in_anime_lofi():
    assert rvt._hook_from_title("Purring Through the Night — Amber Hours \U0001f43e") == "Purring Through the Night"


def test_hook_from_title_handles_empty_input():
    assert rvt._hook_from_title("") == "Cozy"


def test_slug_timestamp_reads_the_embedded_epoch(tmp_path):
    assert rvt._slug_timestamp(tmp_path / "short-lofi-1784419627-1234.done") == 1784419627
    assert rvt._slug_timestamp(tmp_path / "mix-lofimix-1784419627-9999.done") == 1784419627


def test_slug_timestamp_returns_zero_for_unparseable_name(tmp_path):
    assert rvt._slug_timestamp(tmp_path / "not-a-slug.done") == 0


def test_extract_vertical_content_crops_a_pillarboxed_short_thumbnail(tmp_path):
    path = tmp_path / "thumb.jpg"
    Image.new("RGB", (1280, 720), (10, 20, 30)).save(path, quality=95)

    rvt._extract_vertical_content(path)

    with Image.open(path) as im:
        w, h = im.size
    assert h == 720
    assert abs(w / h - 9 / 16) < 0.01


def test_extract_vertical_content_leaves_a_native_vertical_image_alone(tmp_path):
    path = tmp_path / "thumb.jpg"
    Image.new("RGB", (1080, 1920), (10, 20, 30)).save(path, quality=95)

    rvt._extract_vertical_content(path)

    with Image.open(path) as im:
        assert im.size == (1080, 1920)
