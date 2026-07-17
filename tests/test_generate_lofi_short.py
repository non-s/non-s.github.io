import json
from pathlib import Path
from unittest.mock import MagicMock

import generate_lofi_short as lofi


def _touch(path, size=1024):
    path.write_bytes(b"x" * size)
    return path


def test_pick_file_returns_none_when_directory_empty(tmp_path):
    assert lofi._pick_file(tmp_path, "pexels_*.mp4") is None


def test_pick_file_returns_a_match(tmp_path):
    _touch(tmp_path / "pexels_1.mp4")
    _touch(tmp_path / "pexels_2.mp4")
    picked = lofi._pick_file(tmp_path, "pexels_*.mp4")
    assert picked in {tmp_path / "pexels_1.mp4", tmp_path / "pexels_2.mp4"}


def test_load_sidecar_returns_empty_dict_when_missing(tmp_path):
    assert lofi._load_sidecar(tmp_path / "missing.mp4") == {}


def test_load_sidecar_reads_matching_json(tmp_path):
    video = _touch(tmp_path / "pexels_1.mp4")
    (tmp_path / "pexels_1.json").write_text(json.dumps({"title": "rain window"}), encoding="utf-8")
    assert lofi._load_sidecar(video) == {"title": "rain window"}


def test_mood_label_title_cases_first_two_words():
    assert lofi._mood_label("rain window cozy") == "Rain Window"


def test_mood_label_falls_back_when_empty():
    assert lofi._mood_label("") == "Cozy"


def test_build_metadata_includes_attribution_and_upload_contract_fields(tmp_path):
    video_path = tmp_path / "short-lofi-1.mp4"
    broll_meta = {
        "query": "fireplace night cozy",
        "photographer": "Some Photographer",
        "pexels_video_id": "123",
        "license": "Pexels License (free for commercial use)",
        "license_evidence": "https://www.pexels.com/video/123",
    }
    bgm_meta = {
        "track_name": "Horizons",
        "artist_name": "Train Room",
        "license_ccurl": "http://creativecommons.org/licenses/by/3.0/",
        "track_id": "99",
    }
    meta = lofi._build_metadata(broll_meta, bgm_meta, 42.0, video_path, story_id="lofi-1700000000-1234")

    assert meta["video"] == str(video_path)
    assert meta["pre_publish_audit"]["approved"] is True
    assert "Fireplace Night" in meta["title"]
    assert "Horizons" in meta["description"]
    assert "Train Room" in meta["description"]
    assert "Some Photographer" in meta["description"]
    assert meta["pexels_video_id"] == "123"
    assert meta["source_license_evidence"] == "https://www.pexels.com/video/123"
    assert meta["category"] == "lofi"
    assert meta["series"] == "Lofi Beats"
    assert meta["story_id"] == "lofi-1700000000-1234"
    assert "fireplace night" in [tag.lower() for tag in meta["tags"]]


def test_build_metadata_title_always_matches_one_of_the_templates(tmp_path):
    video_path = tmp_path / "short-lofi-1.mp4"
    broll_meta = {"query": "snow falling window cozy"}
    seen_titles = {lofi._build_metadata(broll_meta, {}, 30.0, video_path)["title"] for _ in range(30)}
    expected = {template.format(mood="Snow Falling") for template in lofi.TITLE_TEMPLATES}
    assert seen_titles <= expected
    assert len(seen_titles) > 1  # the random sample actually exercises more than one template


def test_build_metadata_tolerates_missing_attribution(tmp_path):
    video_path = tmp_path / "short-lofi-2.mp4"
    meta = lofi._build_metadata({}, {}, 30.0, video_path)
    assert meta["title"]
    assert meta["pre_publish_audit"]["approved"] is True


def test_compose_short_builds_looping_ffmpeg_command(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-mp4")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(lofi.subprocess, "run", fake_run)

    broll_path = tmp_path / "pexels_1.mp4"
    bgm_path = tmp_path / "ytcc_1.mp3"
    output_path = tmp_path / "short-lofi-3.mp4"

    ok = lofi._compose_short(broll_path, bgm_path, output_path, 45.0)

    assert ok is True
    cmd = calls[-1]
    assert "-stream_loop" in cmd
    assert str(broll_path) in cmd
    assert str(bgm_path) in cmd
    assert "-t" in cmd
    assert cmd[cmd.index("-t") + 1] == "45.000"


def test_compose_short_returns_false_on_ffmpeg_failure(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    monkeypatch.setattr(lofi.subprocess, "run", fake_run)

    ok = lofi._compose_short(tmp_path / "b.mp4", tmp_path / "a.mp3", tmp_path / "out.mp4", 30.0)
    assert ok is False


def test_extract_thumbnail_writes_frame_on_success(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"fake-jpg")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(lofi.subprocess, "run", fake_run)

    thumb_path = tmp_path / "short-lofi-1_thumb.jpg"
    assert lofi._extract_thumbnail(tmp_path / "short-lofi-1.mp4", thumb_path) is True
    assert thumb_path.read_bytes() == b"fake-jpg"


def test_extract_thumbnail_returns_false_on_ffmpeg_failure(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    monkeypatch.setattr(lofi.subprocess, "run", fake_run)

    ok = lofi._extract_thumbnail(tmp_path / "short-lofi-1.mp4", tmp_path / "thumb.jpg")
    assert ok is False


def test_extract_thumbnail_returns_false_when_ffmpeg_missing(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("ffmpeg not found")

    monkeypatch.setattr(lofi.subprocess, "run", fake_run)

    ok = lofi._extract_thumbnail(tmp_path / "short-lofi-1.mp4", tmp_path / "thumb.jpg")
    assert ok is False


def test_main_returns_error_when_no_broll_available(tmp_path, monkeypatch):
    monkeypatch.setattr(lofi, "VIDEOS_DIR", tmp_path / "_videos")
    monkeypatch.setattr(lofi, "BROLL_DIR", tmp_path / "empty_broll")
    monkeypatch.setattr(lofi, "BGM_DIR", tmp_path / "empty_bgm")
    (tmp_path / "empty_broll").mkdir()
    (tmp_path / "empty_bgm").mkdir()

    assert lofi.main() == 1


def test_main_returns_error_when_no_bgm_available(tmp_path, monkeypatch):
    broll_dir = tmp_path / "broll"
    broll_dir.mkdir()
    _touch(broll_dir / "pexels_1.mp4")
    monkeypatch.setattr(lofi, "VIDEOS_DIR", tmp_path / "_videos")
    monkeypatch.setattr(lofi, "BROLL_DIR", broll_dir)
    monkeypatch.setattr(lofi, "BGM_DIR", tmp_path / "empty_bgm")
    (tmp_path / "empty_bgm").mkdir()

    assert lofi.main() == 1


def test_main_writes_video_and_metadata_pair_on_success(tmp_path, monkeypatch):
    broll_dir = tmp_path / "broll"
    bgm_dir = tmp_path / "bgm"
    videos_dir = tmp_path / "_videos"
    broll_dir.mkdir()
    bgm_dir.mkdir()
    _touch(broll_dir / "pexels_1.mp4")
    (broll_dir / "pexels_1.json").write_text(
        json.dumps({"query": "rain window cozy", "photographer": "Ana", "pexels_video_id": "1"}), encoding="utf-8"
    )
    _touch(bgm_dir / "ytcc_1.mp3")
    (bgm_dir / "ytcc_1.json").write_text(
        json.dumps({"track_name": "Rainy Study", "artist_name": "Someone", "track_id": "1"}), encoding="utf-8"
    )

    monkeypatch.setattr(lofi, "VIDEOS_DIR", videos_dir)
    monkeypatch.setattr(lofi, "BROLL_DIR", broll_dir)
    monkeypatch.setattr(lofi, "BGM_DIR", bgm_dir)

    def fake_compose(broll_path, bgm_path, output_path, duration_s):
        output_path.write_bytes(b"fake-mp4")
        return True

    monkeypatch.setattr(lofi, "_compose_short", fake_compose)

    def fake_thumbnail(video_path, thumb_path, timestamp_s=2.0):
        thumb_path.write_bytes(b"fake-jpg")
        return True

    monkeypatch.setattr(lofi, "_extract_thumbnail", fake_thumbnail)

    assert lofi.main() == 0

    videos = list(videos_dir.glob("short-*.mp4"))
    assert len(videos) == 1
    meta_path = videos[0].with_suffix(".json")
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert meta["video"] == str(videos[0])
    assert meta["pre_publish_audit"]["approved"] is True
    assert meta["thumbnail"] == str(videos_dir / f"{videos[0].stem}_thumb.jpg")
    assert Path(meta["thumbnail"]).exists()


def test_main_omits_thumbnail_field_when_extraction_fails(tmp_path, monkeypatch):
    broll_dir = tmp_path / "broll"
    bgm_dir = tmp_path / "bgm"
    videos_dir = tmp_path / "_videos"
    broll_dir.mkdir()
    bgm_dir.mkdir()
    _touch(broll_dir / "pexels_1.mp4")
    _touch(bgm_dir / "ytcc_1.mp3")

    monkeypatch.setattr(lofi, "VIDEOS_DIR", videos_dir)
    monkeypatch.setattr(lofi, "BROLL_DIR", broll_dir)
    monkeypatch.setattr(lofi, "BGM_DIR", bgm_dir)
    monkeypatch.setattr(lofi, "_compose_short", lambda broll, bgm, out, dur: out.write_bytes(b"x") or True)
    monkeypatch.setattr(lofi, "_extract_thumbnail", lambda *a, **k: False)

    assert lofi.main() == 0

    meta_path = next(videos_dir.glob("short-*.json"))
    meta = json.loads(meta_path.read_text())
    assert "thumbnail" not in meta


def test_main_returns_error_when_composition_fails(tmp_path, monkeypatch):
    broll_dir = tmp_path / "broll"
    bgm_dir = tmp_path / "bgm"
    broll_dir.mkdir()
    bgm_dir.mkdir()
    _touch(broll_dir / "pexels_1.mp4")
    _touch(bgm_dir / "ytcc_1.mp3")

    monkeypatch.setattr(lofi, "VIDEOS_DIR", tmp_path / "_videos")
    monkeypatch.setattr(lofi, "BROLL_DIR", broll_dir)
    monkeypatch.setattr(lofi, "BGM_DIR", bgm_dir)
    monkeypatch.setattr(lofi, "_compose_short", lambda *a, **k: False)

    assert lofi.main() == 1
