from generate_shorts import build_short_metadata


def test_metadata_preserves_music_bed_variant(tmp_path):
    meta = build_short_metadata(
        {
            "title": "Cats purr for more than happiness",
            "category": "cats",
            "music_bed_variant": "light_bed",
            "yt_tags": ["cats", "science", "nature"],
        },
        tmp_path / "short.mp4",
        tmp_path / "thumb.jpg",
    )

    assert meta["music_bed_variant"] == "light_bed"
    assert meta["seo_lint"]["enabled"] is True
