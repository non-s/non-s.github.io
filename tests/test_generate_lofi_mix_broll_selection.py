import json

import generate_lofi_mix as lofi_mix


def _touch(path, size=1024):
    path.write_bytes(b"x" * size)
    return path


def test_pick_broll_file_returns_none_when_directory_empty(tmp_path):
    assert lofi_mix._pick_broll_file(tmp_path, "pixabay_*.mp4") is None


def test_pick_broll_file_skips_clips_without_anime_style_tags(tmp_path):
    """Regression: the daily mix must not pick an off-brand clip either,
    for the same reason generate_lofi_short.py can't (see
    utils.broll.is_on_brand_broll_clip)."""
    _touch(tmp_path / "pixabay_1.mp4")
    (tmp_path / "pixabay_1.json").write_text(
        json.dumps({"tags": "man, library, book, education, reading"}), encoding="utf-8"
    )
    assert lofi_mix._pick_broll_file(tmp_path, "pixabay_*.mp4") is None


def test_pick_broll_file_returns_only_on_brand_clip(tmp_path):
    _touch(tmp_path / "pixabay_1.mp4")
    (tmp_path / "pixabay_1.json").write_text(
        json.dumps({"tags": "man, library, book, education, reading"}), encoding="utf-8"
    )
    _touch(tmp_path / "pixabay_2.mp4")
    (tmp_path / "pixabay_2.json").write_text(json.dumps({"tags": "anime, girl, study, lofi"}), encoding="utf-8")

    assert lofi_mix._pick_broll_file(tmp_path, "pixabay_*.mp4") == tmp_path / "pixabay_2.mp4"
