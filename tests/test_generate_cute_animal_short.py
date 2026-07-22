"""Tests for generate_cute_animal_short.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import generate_cute_animal_short as animal_short


def test_pick_scene_returns_a_known_hook_scene():
    from utils.animal_branding import HOOK_BY_SCENE

    scene = animal_short._pick_scene()
    assert scene.lower() in HOOK_BY_SCENE


def test_build_metadata_uses_template_title_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(animal_short, "generate_animal_short_copy", lambda **kwargs: None)
    video_path = tmp_path / "animal-animalshort-1.mp4"

    meta = animal_short._build_metadata("cat", 45.0, video_path, slug="s-1", broll_meta={}, jazz_meta=None)

    assert meta["title"] == animal_short.branded_title("cat")
    assert meta["category"] == "cute_animals"
    assert meta["youtube_category_id"] == "15"


def test_build_metadata_includes_shorts_hashtag(tmp_path, monkeypatch):
    monkeypatch.setattr(animal_short, "generate_animal_short_copy", lambda **kwargs: None)
    video_path = tmp_path / "animal-animalshort-2.mp4"

    meta = animal_short._build_metadata("dog", 45.0, video_path, slug="s-2", broll_meta={}, jazz_meta=None)

    assert "#Shorts" in meta["description"]


def test_build_metadata_credits_jazz_only_when_a_track_was_used(tmp_path, monkeypatch):
    monkeypatch.setattr(animal_short, "generate_animal_short_copy", lambda **kwargs: None)
    jazz_meta = {"track_name": "Late Night Swing", "artist_name": "Someone", "license_ccurl": "http://example.com"}
    video_path = tmp_path / "animal-animalshort-3.mp4"

    with_jazz = animal_short._build_metadata("cat", 45.0, video_path, slug="s-3", broll_meta={}, jazz_meta=jazz_meta)
    without_jazz = animal_short._build_metadata("cat", 45.0, video_path, slug="s-4", broll_meta={}, jazz_meta=None)

    assert "Late Night Swing" in with_jazz["description"]
    assert with_jazz["bgm_track_id"] == ""  # no track_id key in this fixture
    assert "Late Night Swing" not in without_jazz["description"]


def test_build_metadata_carries_real_broll_source_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(animal_short, "generate_animal_short_copy", lambda **kwargs: None)
    broll_meta = {
        "source": "pixabay",
        "pixabay_video_id": "555",
        "license": "Pixabay Content License (free for commercial use, no attribution required)",
        "license_evidence": "https://pixabay.com/videos/id-555",
    }
    video_path = tmp_path / "animal-animalshort-5.mp4"

    meta = animal_short._build_metadata("cat", 45.0, video_path, slug="s-5", broll_meta=broll_meta, jazz_meta=None)

    assert meta["source"] == "pixabay"
    assert meta["source_clip_id"] == "555"
    assert meta["source_url"] == "https://pixabay.com/videos/id-555"
    assert meta["source_license"] == broll_meta["license"]


def test_build_metadata_uses_ai_copy_when_available(tmp_path, monkeypatch):
    ai_result = {
        "title": "Gato Fofo Demais -- Pata Jazz",
        "description": "Um gatinho fazendo arte.",
        "hashtags": ["gato", "fofura"],
    }
    monkeypatch.setattr(animal_short, "generate_animal_short_copy", lambda **kwargs: ai_result)
    video_path = tmp_path / "animal-animalshort-6.mp4"

    meta = animal_short._build_metadata("cat", 45.0, video_path, slug="s-6", broll_meta={}, jazz_meta=None)

    assert meta["title"] == ai_result["title"]
    assert "Um gatinho fazendo arte." in meta["description"]
    assert "pata jazz" in meta["tags"]
    assert "gato" in meta["tags"]


def test_prepare_seamless_loop_clip_returns_raw_clip_for_short_source(tmp_path, monkeypatch):
    import utils.ffmpeg_helpers as fh

    monkeypatch.setattr(fh, "media_duration_s", lambda path: 0.0)
    clip_path = tmp_path / "pixabay_1.mp4"

    out = animal_short._prepare_seamless_loop_clip(clip_path)

    assert out == clip_path


def test_prepare_seamless_loop_clip_bakes_a_crossfade_for_a_longer_clip(tmp_path, monkeypatch):
    monkeypatch.setattr(animal_short, "TEMP_DIR", tmp_path)
    import utils.ffmpeg_helpers as fh

    monkeypatch.setattr(fh, "media_duration_s", lambda path: 12.0)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-mp4")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(fh.subprocess, "run", fake_run)
    clip_path = tmp_path / "pixabay_1.mp4"

    out = animal_short._prepare_seamless_loop_clip(clip_path)

    assert out == tmp_path / "seamless_pixabay_1.mp4"
    assert "xfade" in calls[-1][calls[-1].index("-filter_complex") + 1]


def test_compose_short_with_jazz_track(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-mp4")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(animal_short.subprocess, "run", fake_run)

    broll_path = tmp_path / "pixabay_1.mp4"
    jazz_path = tmp_path / "jamendo_1.mp3"
    output_path = tmp_path / "animal-1.mp4"

    ok = animal_short._compose_short(broll_path, jazz_path, output_path, 45.0)

    assert ok is True
    cmd = calls[-1]
    assert str(jazz_path) in cmd
    assert cmd[cmd.index("-t") + 1] == "45.000"


def test_compose_short_without_jazz_track_uses_silent_audio(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-mp4")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(animal_short.subprocess, "run", fake_run)

    broll_path = tmp_path / "pixabay_1.mp4"
    output_path = tmp_path / "animal-2.mp4"

    ok = animal_short._compose_short(broll_path, None, output_path, 30.0)

    assert ok is True
    cmd = calls[-1]
    assert "anullsrc" in " ".join(cmd)


def test_compose_short_returns_false_on_ffmpeg_failure(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    monkeypatch.setattr(animal_short.subprocess, "run", fake_run)

    ok = animal_short._compose_short(tmp_path / "b.mp4", None, tmp_path / "out.mp4", 30.0)
    assert ok is False


def test_load_sidecar_returns_empty_dict_when_missing(tmp_path):
    assert animal_short._load_sidecar(tmp_path / "missing.mp4") == {}


def test_load_sidecar_reads_matching_json(tmp_path):
    video_path = tmp_path / "clip.mp4"
    video_path.with_suffix(".json").write_text('{"source": "pixabay"}', encoding="utf-8")

    assert animal_short._load_sidecar(video_path) == {"source": "pixabay"}


def test_pick_jazz_track_returns_none_when_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(animal_short, "JAZZ_DIR", tmp_path)
    assert animal_short._pick_jazz_track() is None


def test_pick_jazz_track_returns_a_track_when_present(tmp_path, monkeypatch):
    monkeypatch.setattr(animal_short, "JAZZ_DIR", tmp_path)
    track = tmp_path / "jamendo_1.mp3"
    track.write_bytes(b"x")

    assert animal_short._pick_jazz_track() == track


def test_extract_thumbnail_frame_returns_none_on_ffmpeg_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(animal_short, "TEMP_DIR", tmp_path)

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    monkeypatch.setattr(animal_short.subprocess, "run", fake_run)

    assert animal_short._extract_thumbnail_frame(tmp_path / "clip.mp4", seed=1) is None


def test_extract_thumbnail_frame_returns_path_on_success(tmp_path, monkeypatch):
    monkeypatch.setattr(animal_short, "TEMP_DIR", tmp_path)

    def fake_run(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"fake-jpg")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(animal_short.subprocess, "run", fake_run)

    out = animal_short._extract_thumbnail_frame(tmp_path / "clip.mp4", seed=42)

    assert out == tmp_path / "thumb_42.jpg"
    assert out.exists()


def test_main_returns_error_when_broll_pool_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(animal_short, "ANIMAL_BROLL_DIR", tmp_path)
    monkeypatch.setattr(animal_short, "VIDEOS_DIR", tmp_path / "_videos")
    monkeypatch.setattr(animal_short, "TEMP_DIR", tmp_path / "_videos" / "temp")

    assert animal_short.main() == 1
