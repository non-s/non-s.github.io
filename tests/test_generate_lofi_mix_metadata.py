"""Tests for generate_lofi_mix.py's _build_metadata()."""

import generate_lofi_mix as lofi_mix


def test_build_metadata_series_is_named_per_mood_bucket_and_format(tmp_path):
    """Regression: series used to be one static "Lofi Mixes" label shared
    by every video regardless of mood -- see SERIES_SUFFIX's comment. It
    should now be a fixed, recognizable name per (mood bucket, format)."""
    video_path = tmp_path / "mix-lofi-1.mp4"
    broll_meta = {"query": "anime rain window thunderstorm"}

    meta = lofi_mix._build_metadata(broll_meta, [], 3600.0, video_path, slug="lofi-1700000000-1234")

    assert meta["series"] == "Rainy Night Lofi Mix"
    assert meta["category"] == "lofi"


def test_build_metadata_series_differs_from_the_shorts_suffix(tmp_path):
    """Same mood bucket, but the mix side of the series must stay a
    distinct playlist from generate_lofi_short.py's "Shorts" series."""
    video_path = tmp_path / "mix-lofi-2.mp4"
    broll_meta = {"query": "anime cat sleeping cozy"}

    meta = lofi_mix._build_metadata(broll_meta, [], 3600.0, video_path, slug="lofi-1700000000-5678")

    assert meta["series"].endswith(" Mix")
    assert not meta["series"].endswith(" Shorts")
