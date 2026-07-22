"""Tests for generate_classical_ambience.py."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import generate_classical_ambience as classical


def test_pick_mood_returns_a_known_hook_mood():
    from utils.classical_branding import HOOK_BY_MOOD

    mood = classical._pick_mood()
    assert mood.lower() in HOOK_BY_MOOD


def test_pick_track_returns_none_when_library_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(classical, "CLASSICAL_DIR", tmp_path)
    assert classical._pick_track() is None


def test_pick_track_picks_the_least_recently_used_file(tmp_path, monkeypatch):
    monkeypatch.setattr(classical, "CLASSICAL_DIR", tmp_path)
    old = tmp_path / "jamendo_old.mp3"
    new = tmp_path / "jamendo_new.mp3"
    old.write_bytes(b"x")
    time.sleep(0.01)
    new.write_bytes(b"x")
    # Force old's mtime well before new's, regardless of filesystem timestamp resolution.
    import os

    os.utime(old, (time.time() - 100, time.time() - 100))

    picked = classical._pick_track()

    assert picked == old


def test_pick_track_touches_the_chosen_file_so_it_is_not_repeated_immediately(tmp_path, monkeypatch):
    monkeypatch.setattr(classical, "CLASSICAL_DIR", tmp_path)
    a = tmp_path / "jamendo_a.mp3"
    b = tmp_path / "jamendo_b.mp3"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    import os

    os.utime(a, (time.time() - 100, time.time() - 100))
    os.utime(b, (time.time() - 50, time.time() - 50))

    first_pick = classical._pick_track()
    second_pick = classical._pick_track()

    assert first_pick == a
    assert second_pick == b  # a was touched (mtime bumped to "now"), so b is now the least-recently-used


def test_prepare_seamless_loop_clip_returns_raw_clip_for_short_source(tmp_path, monkeypatch):
    monkeypatch.setattr(classical, "_media_duration_s", lambda path: 0.0)
    clip_path = tmp_path / "pinned_classical_ambience.mp4"

    out = classical._prepare_seamless_loop_clip(clip_path)

    assert out == clip_path


def test_prepare_seamless_loop_clip_bakes_a_crossfade_for_a_longer_clip(tmp_path, monkeypatch):
    monkeypatch.setattr(classical, "TEMP_DIR", tmp_path)
    monkeypatch.setattr(classical, "_media_duration_s", lambda path: 60.0)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-mp4")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(classical.subprocess, "run", fake_run)
    clip_path = tmp_path / "pinned_classical_ambience.mp4"

    out = classical._prepare_seamless_loop_clip(clip_path)

    assert out == tmp_path / "seamless_pinned_classical_ambience.mp4"
    assert "xfade" in calls[-1][calls[-1].index("-filter_complex") + 1]


def test_bake_filtered_segment_builds_expected_ffmpeg_command(tmp_path, monkeypatch):
    monkeypatch.setattr(classical, "TEMP_DIR", tmp_path)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-mp4")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(classical.subprocess, "run", fake_run)

    out = classical._bake_filtered_segment(tmp_path / "pinned_classical_ambience.mp4")

    assert out is not None
    assert out.exists()
    cmd = calls[-1]
    assert "-vf" in cmd
    assert "-an" in cmd


def test_bake_filtered_segment_returns_none_on_ffmpeg_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(classical, "TEMP_DIR", tmp_path)

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    monkeypatch.setattr(classical.subprocess, "run", fake_run)

    assert classical._bake_filtered_segment(tmp_path / "clip.mp4") is None


def test_compose_classical_builds_a_one_pass_ffmpeg_command_with_the_track_duration(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-mp4")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(classical.subprocess, "run", fake_run)

    ok = classical._compose_classical(tmp_path / "segment.mp4", tmp_path / "track.mp3", tmp_path / "out.mp4", 245.678)

    assert ok is True
    cmd = calls[0]
    assert "-t" in cmd
    assert cmd[cmd.index("-t") + 1] == "245.678"
    # The track itself is not looped -- only the video input gets -stream_loop.
    assert cmd.count("-stream_loop") == 1


def test_compose_classical_returns_false_on_ffmpeg_failure(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    monkeypatch.setattr(classical.subprocess, "run", fake_run)

    ok = classical._compose_classical(tmp_path / "s.mp4", tmp_path / "t.mp3", tmp_path / "out.mp4", 60.0)
    assert ok is False


def test_mandatory_attribution_line_includes_real_track_artist_and_license():
    line = classical._mandatory_attribution_line(
        {
            "track_name": "Goldberg Variations, Aria",
            "artist_name": "Kimiko Ishizaka",
            "license_ccurl": "http://creativecommons.org/licenses/by/3.0/",
        }
    )

    assert "Goldberg Variations, Aria" in line
    assert "Kimiko Ishizaka" in line
    assert "http://creativecommons.org/licenses/by/3.0/" in line
    assert "Creative Commons Attribution" in line


def test_mandatory_attribution_line_degrades_gracefully_on_missing_fields():
    line = classical._mandatory_attribution_line({})

    assert "Unknown track" in line
    assert "Unknown artist" in line
    assert "Creative Commons Attribution" in line


_TRACK_META = {
    "track_id": "999",
    "track_name": "Goldberg Variations, Aria",
    "artist_name": "Kimiko Ishizaka",
    "license_ccurl": "http://creativecommons.org/licenses/by/3.0/",
}


def test_build_metadata_includes_mandatory_attribution_on_template_fallback_path(tmp_path, monkeypatch):
    """The single most important test in this file per the channel
    owner's explicit spec: attribution must appear even when the AI call
    fails/is unconfigured and the template path is used."""
    monkeypatch.setattr(classical, "generate_classical_video_copy", lambda **kwargs: None)
    video_path = tmp_path / "classical-ambience-1.mp4"

    meta = classical._build_metadata("deep focus", 1800.0, video_path, slug="s-1", track_meta=_TRACK_META)

    assert "Goldberg Variations, Aria" in meta["description"]
    assert "Kimiko Ishizaka" in meta["description"]
    assert "http://creativecommons.org/licenses/by/3.0/" in meta["description"]


def test_build_metadata_includes_mandatory_attribution_on_ai_copy_path(tmp_path, monkeypatch):
    """Same guarantee, but with the AI path active -- the AI is asked to
    mention the piece naturally, but the exact attribution line is still
    appended in code afterward regardless of what the AI wrote, so this
    must hold even if the AI's own prose omits the license URL (which it
    has no reason to include verbatim on its own)."""
    ai_result = {
        "title": "Bach for Deep Focus -- Amber Hours Classical",
        "description": "A calm piece for deep focus, performed beautifully.",  # deliberately no credit/license text
        "hashtags": ["classical", "piano"],
    }
    monkeypatch.setattr(classical, "generate_classical_video_copy", lambda **kwargs: ai_result)
    video_path = tmp_path / "classical-ambience-2.mp4"

    meta = classical._build_metadata("deep focus", 1800.0, video_path, slug="s-2", track_meta=_TRACK_META)

    assert meta["title"] == ai_result["title"]
    assert "A calm piece for deep focus" in meta["description"]
    # The mandatory line is still appended even though the AI text above never mentioned it:
    assert "Goldberg Variations, Aria" in meta["description"]
    assert "Kimiko Ishizaka" in meta["description"]
    assert "http://creativecommons.org/licenses/by/3.0/" in meta["description"]


def test_build_metadata_uses_hours_label_for_long_tracks(tmp_path):
    video_path = tmp_path / "classical-ambience-3.mp4"
    meta = classical._build_metadata("sleep", 2.0 * 3600, video_path, slug="s-3", track_meta=_TRACK_META)
    assert "(2.0 Hours)" in meta["title"]


def test_build_metadata_uses_minutes_label_for_short_tracks(tmp_path):
    video_path = tmp_path / "classical-ambience-4.mp4"
    meta = classical._build_metadata("focus", 240.0, video_path, slug="s-4", track_meta=_TRACK_META)
    assert "(4 Min)" in meta["title"]


def test_build_metadata_carries_real_track_source_fields(tmp_path):
    video_path = tmp_path / "classical-ambience-5.mp4"
    meta = classical._build_metadata("focus", 300.0, video_path, slug="s-5", track_meta=_TRACK_META)

    assert meta["bgm_track_id"] == "999"
    assert meta["bgm_track_name"] == "Goldberg Variations, Aria"
    assert meta["bgm_artist_name"] == "Kimiko Ishizaka"
    assert meta["bgm_license_ccurl"] == "http://creativecommons.org/licenses/by/3.0/"
    assert meta["is_short"] is False
    assert meta["category"] == "classical_ambience"


def test_build_metadata_publish_slot_uses_the_classical_prefix(tmp_path):
    video_path = tmp_path / "classical-ambience-6.mp4"
    meta = classical._build_metadata("focus", 300.0, video_path, slug="s-6", track_meta=_TRACK_META)

    assert meta["publish_slot"].startswith("classical-")
    assert meta["publish_slot_key"].startswith("classical-")


def test_main_fails_cleanly_when_pinned_clip_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(classical, "PINNED_BROLL_CLIP", tmp_path / "missing.mp4")
    monkeypatch.setattr(classical, "VIDEOS_DIR", tmp_path / "_videos")
    monkeypatch.setattr(classical, "TEMP_DIR", tmp_path / "_videos" / "temp_classical")

    assert classical.main() == 1


def test_main_fails_cleanly_when_no_track_available(tmp_path, monkeypatch):
    pinned = tmp_path / "pinned_classical_ambience.mp4"
    pinned.write_bytes(b"x")
    monkeypatch.setattr(classical, "PINNED_BROLL_CLIP", pinned)
    monkeypatch.setattr(classical, "VIDEOS_DIR", tmp_path / "_videos")
    monkeypatch.setattr(classical, "TEMP_DIR", tmp_path / "_videos" / "temp_classical")
    monkeypatch.setattr(classical, "CLASSICAL_DIR", tmp_path / "empty_classical")

    assert classical.main() == 1


def test_main_fails_cleanly_when_track_duration_cannot_be_read(tmp_path, monkeypatch):
    pinned = tmp_path / "pinned_classical_ambience.mp4"
    pinned.write_bytes(b"x")
    classical_dir = tmp_path / "classical"
    classical_dir.mkdir()
    (classical_dir / "jamendo_1.mp3").write_bytes(b"x")
    monkeypatch.setattr(classical, "PINNED_BROLL_CLIP", pinned)
    monkeypatch.setattr(classical, "VIDEOS_DIR", tmp_path / "_videos")
    monkeypatch.setattr(classical, "TEMP_DIR", tmp_path / "_videos" / "temp_classical")
    monkeypatch.setattr(classical, "CLASSICAL_DIR", classical_dir)
    monkeypatch.setattr(classical, "_media_duration_s", lambda path: 0.0)

    assert classical.main() == 1
