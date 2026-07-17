from pathlib import Path
from unittest.mock import MagicMock

import generate_lofi_long_video as lofi_long
from utils.broll import BrollClip


def _clip(clip_id="1", **overrides) -> BrollClip:
    clip = BrollClip(
        source="pixabay",
        url=f"https://pixabay.com/videos/id-{clip_id}/",
        download_url=f"https://cdn.pixabay.com/video/{clip_id}/large.mp4",
        width=1920,
        height=1080,
        duration_s=12.0,
        title="girl",
        license="Pixabay Content License (free for commercial use, no attribution required)",
        license_evidence=f"https://pixabay.com/videos/id-{clip_id}/",
        source_metadata={"pixabay_video_id": clip_id, "pixabay_query": "anime lofi girl study"},
    )
    for key, value in overrides.items():
        setattr(clip, key, value)
    return clip


def test_fetch_unique_clips_deduplicates_by_download_url(monkeypatch):
    same_clip = _clip(clip_id="1")

    def fake_fetch(query, per_page=6):
        return [same_clip]

    monkeypatch.setattr(lofi_long, "fetch_pixabay", fake_fetch)

    clips = lofi_long._fetch_unique_clips(4)

    assert len(clips) == 1


def test_fetch_unique_clips_stops_at_want_n(monkeypatch):
    def fake_fetch(query, per_page=6):
        return [_clip(clip_id=f"{query}-{i}") for i in range(2)]

    monkeypatch.setattr(lofi_long, "fetch_pixabay", fake_fetch)

    clips = lofi_long._fetch_unique_clips(3)

    assert len(clips) == 3


def test_build_segment_runs_ffmpeg_with_expected_flags(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-segment")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(lofi_long.subprocess, "run", fake_run)

    clip_path = tmp_path / "raw_0.mp4"
    out_path = tmp_path / "segment_0.mp4"
    ok = lofi_long._build_segment(clip_path, out_path, 75.0)

    assert ok is True
    cmd = calls[-1]
    assert "-an" in cmd
    assert "-t" in cmd
    assert cmd[cmd.index("-t") + 1] == "75.000"
    assert str(clip_path) in cmd


def test_build_segment_returns_false_on_ffmpeg_failure(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    monkeypatch.setattr(lofi_long.subprocess, "run", fake_run)

    ok = lofi_long._build_segment(tmp_path / "raw.mp4", tmp_path / "out.mp4", 75.0)
    assert ok is False


def test_concat_segments_writes_concat_list_and_runs_ffmpeg(tmp_path, monkeypatch):
    monkeypatch.setattr(lofi_long, "TEMP_DIR", tmp_path)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-concat")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(lofi_long.subprocess, "run", fake_run)

    seg1 = tmp_path / "segment_0.mp4"
    seg2 = tmp_path / "segment_1.mp4"
    seg1.write_bytes(b"x")
    seg2.write_bytes(b"x")
    out_path = tmp_path / "long_video_test.mp4"

    ok = lofi_long._concat_segments([seg1, seg2], out_path)

    assert ok is True
    concat_list = (tmp_path / "concat.txt").read_text()
    assert seg1.name in concat_list
    assert seg2.name in concat_list


def test_main_returns_error_when_no_clips_available(tmp_path, monkeypatch):
    monkeypatch.setattr(lofi_long, "VIDEOS_DIR", tmp_path / "_videos")
    monkeypatch.setattr(lofi_long, "TEMP_DIR", tmp_path / "_videos" / "long_video_temp")
    monkeypatch.setattr(lofi_long, "_fetch_unique_clips", lambda want_n: [])

    assert lofi_long.main() == 1


def test_main_builds_and_concatenates_segments_on_success(tmp_path, monkeypatch):
    videos_dir = tmp_path / "_videos"
    monkeypatch.setattr(lofi_long, "VIDEOS_DIR", videos_dir)
    monkeypatch.setattr(lofi_long, "TEMP_DIR", videos_dir / "long_video_temp")
    monkeypatch.setattr(lofi_long, "_fetch_unique_clips", lambda want_n: [_clip("1"), _clip("2")])
    monkeypatch.setattr(lofi_long, "download_clip", lambda clip, dest: dest.write_bytes(b"x") or True)
    monkeypatch.setattr(
        lofi_long, "_build_segment", lambda clip_path, out_path, duration: out_path.write_bytes(b"x") or True
    )
    monkeypatch.setattr(
        lofi_long, "_concat_segments", lambda segment_paths, out_path: out_path.write_bytes(b"final") or True
    )

    assert lofi_long.main() == 0

    videos = list(videos_dir.glob("long_video_*.mp4"))
    assert len(videos) == 1
    assert videos[0].read_bytes() == b"final"


def test_main_returns_error_when_all_segments_fail(tmp_path, monkeypatch):
    videos_dir = tmp_path / "_videos"
    monkeypatch.setattr(lofi_long, "VIDEOS_DIR", videos_dir)
    monkeypatch.setattr(lofi_long, "TEMP_DIR", videos_dir / "long_video_temp")
    monkeypatch.setattr(lofi_long, "_fetch_unique_clips", lambda want_n: [_clip("1")])
    monkeypatch.setattr(lofi_long, "download_clip", lambda clip, dest: dest.write_bytes(b"x") or True)
    monkeypatch.setattr(lofi_long, "_build_segment", lambda clip_path, out_path, duration: False)

    assert lofi_long.main() == 1
