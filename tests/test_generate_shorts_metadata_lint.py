from generate_shorts import build_short_metadata


def test_build_short_metadata_includes_seo_lint(tmp_path):
    meta = build_short_metadata(
        {
            "title": "Sharks sense tiny electric fields",
            "category": "sharks",
            "yt_description": "A clear science Short.",
            "yt_tags": ["sharks", "science", "nature"],
        },
        tmp_path / "short.mp4",
        tmp_path / "thumb.jpg",
    )

    assert "seo_lint" in meta
    assert meta["seo_lint"]["score"] > 0
