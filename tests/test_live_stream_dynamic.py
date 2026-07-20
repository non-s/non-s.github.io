from pathlib import Path
from unittest.mock import MagicMock

import pytest

import scripts.live_stream_dynamic as live_stream_dynamic


@pytest.fixture
def streamer(monkeypatch, tmp_path):
    monkeypatch.setattr(live_stream_dynamic.DynamicStreamer, "_get_youtube_client", lambda self: None)
    # Default to "no pinned clip" so existing tests exercise the BROLL_DIR
    # fallback; the real repo-committed pinned pool/clip would otherwise
    # always win regardless of BROLL_DIR monkeypatching below.
    monkeypatch.setattr(live_stream_dynamic, "PINNED_BROLL_DIR", tmp_path / "no_pinned_pool")
    monkeypatch.setattr(live_stream_dynamic, "PINNED_BROLL_CLIP", tmp_path / "no_pinned_clip.mp4")
    instance = live_stream_dynamic.DynamicStreamer("test-stream-key")
    instance.videos_dir = tmp_path / "_videos"
    instance.temp_dir = tmp_path / "_videos" / "temp_stream"
    instance.temp_dir.mkdir(parents=True, exist_ok=True)
    return instance


def test_pick_broll_clip_returns_none_when_library_empty(streamer, tmp_path, monkeypatch):
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", tmp_path / "empty_broll")
    (tmp_path / "empty_broll").mkdir()

    assert streamer._pick_broll_clip() is None


def test_pick_broll_clip_returns_a_clip_when_present(streamer, tmp_path, monkeypatch):
    broll_dir = tmp_path / "broll"
    broll_dir.mkdir()
    (broll_dir / "pixabay_1.mp4").write_bytes(b"x")
    (broll_dir / "pixabay_1.json").write_text('{"tags": "anime, girl, study, lofi"}')
    (broll_dir / "pixabay_2.mp4").write_bytes(b"x")
    (broll_dir / "pixabay_2.json").write_text('{"tags": "anime, rain, window"}')
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", broll_dir)

    picked = streamer._pick_broll_clip()

    assert picked in {broll_dir / "pixabay_1.mp4", broll_dir / "pixabay_2.mp4"}


def test_pick_broll_clip_skips_offbrand_clips_in_fallback_pool(streamer, tmp_path, monkeypatch):
    """Regression: without a pinned clip, the rotating BROLL_DIR fallback
    must not surface a clip lacking anime-style tag evidence."""
    broll_dir = tmp_path / "broll"
    broll_dir.mkdir()
    (broll_dir / "pixabay_1.mp4").write_bytes(b"x")
    (broll_dir / "pixabay_1.json").write_text('{"tags": "man, library, book, education, reading"}')
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", broll_dir)

    assert streamer._pick_broll_clip() is None


def test_pick_broll_clip_prefers_pinned_clip_when_present(streamer, tmp_path, monkeypatch):
    broll_dir = tmp_path / "broll"
    broll_dir.mkdir()
    (broll_dir / "pixabay_1.mp4").write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", broll_dir)
    pinned = tmp_path / "pinned_live_clip.mp4"
    pinned.write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "PINNED_BROLL_CLIP", pinned)

    assert streamer._pick_broll_clip() == pinned


def test_run_bails_out_without_starting_when_pinned_pool_and_broll_dir_both_empty(streamer, tmp_path, monkeypatch):
    """Regression: run()'s startup guard used to only check the legacy
    single-file PINNED_BROLL_CLIP, so migrating the committed clip into
    PINNED_BROLL_DIR (a real pool, see _pinned_broll_candidates()) made the
    guard always see "nothing available" and bail before ever calling
    ensure_live_broadcast() -- even though _pick_broll_clip() would have
    found the pool clip just fine. This is what actually happened in
    production: the relay looped exiting immediately for ~2 hours straight
    with the channel never going live, because PINNED_BROLL_DIR had a real
    clip in it that the guard never looked at."""
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", tmp_path / "empty_broll")
    (tmp_path / "empty_broll").mkdir()
    ensure_broadcast = MagicMock()
    monkeypatch.setattr(streamer, "ensure_live_broadcast", ensure_broadcast)

    streamer.run()

    ensure_broadcast.assert_not_called()


def test_run_proceeds_past_the_guard_when_only_the_pinned_pool_has_a_clip(streamer, tmp_path, monkeypatch):
    """Mirror of the regression above: a pool-only clip (no legacy
    PINNED_BROLL_CLIP, no BROLL_DIR fallback) must be enough for run() to
    get past the startup guard and reach ensure_live_broadcast()."""
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", tmp_path / "empty_broll")
    (tmp_path / "empty_broll").mkdir()
    pool = tmp_path / "pinned_pool"
    pool.mkdir()
    (pool / "rain_window_01.mp4").write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "PINNED_BROLL_DIR", pool)
    monkeypatch.setattr(streamer, "ensure_live_broadcast", MagicMock())
    monkeypatch.setattr(live_stream_dynamic.threading, "Thread", MagicMock())
    # run()'s main loop is an infinite `while True` around a real ffmpeg
    # subprocess -- not something to execute in a unit test. build_stream_command()
    # returning None short-circuits that inner loop back to the guard check
    # we actually care about, so raise once we're sure the guard let us in.
    monkeypatch.setattr(streamer, "build_stream_command", MagicMock(side_effect=RuntimeError("reached main loop")))

    with pytest.raises(RuntimeError, match="reached main loop"):
        streamer.run()

    streamer.ensure_live_broadcast.assert_called_once()


def test_select_pinned_broll_clip_returns_none_with_no_pool_and_no_legacy_clip(tmp_path, monkeypatch):
    monkeypatch.setattr(live_stream_dynamic, "PINNED_BROLL_DIR", tmp_path / "no_pool")
    monkeypatch.setattr(live_stream_dynamic, "PINNED_BROLL_CLIP", tmp_path / "no_legacy.mp4")

    assert live_stream_dynamic._select_pinned_broll_clip() is None


def test_select_pinned_broll_clip_falls_back_to_legacy_clip_when_pool_absent(tmp_path, monkeypatch):
    legacy = tmp_path / "pinned_live_clip.mp4"
    legacy.write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "PINNED_BROLL_DIR", tmp_path / "no_pool")
    monkeypatch.setattr(live_stream_dynamic, "PINNED_BROLL_CLIP", legacy)

    assert live_stream_dynamic._select_pinned_broll_clip() == legacy


def test_select_pinned_broll_clip_returns_the_only_pool_clip_unrotated(tmp_path, monkeypatch):
    pool = tmp_path / "pool"
    pool.mkdir()
    only_clip = pool / "rain_01.mp4"
    only_clip.write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "PINNED_BROLL_DIR", pool)

    assert live_stream_dynamic._select_pinned_broll_clip() == only_clip


def test_select_pinned_broll_clip_rotates_weekly_across_a_curated_pool(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    pool = tmp_path / "pool"
    pool.mkdir()
    clip_a = pool / "rain_01.mp4"
    clip_b = pool / "rain_02.mp4"
    clip_a.write_bytes(b"x")
    clip_b.write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "PINNED_BROLL_DIR", pool)
    monkeypatch.setattr(live_stream_dynamic, "_PINNED_ROTATION_PERIOD_DAYS", 7)

    week_one = live_stream_dynamic._select_pinned_broll_clip(datetime(2026, 7, 1, tzinfo=timezone.utc))
    week_two = live_stream_dynamic._select_pinned_broll_clip(datetime(2026, 7, 8, tzinfo=timezone.utc))
    same_week = live_stream_dynamic._select_pinned_broll_clip(datetime(2026, 7, 2, tzinfo=timezone.utc))

    assert week_one in {clip_a, clip_b}
    assert week_one == same_week  # still within the same 7-day period
    assert week_two != week_one  # a full period later, rotated to the other clip


def test_build_bgm_playlist_returns_none_when_library_empty(streamer, tmp_path, monkeypatch):
    monkeypatch.setattr(live_stream_dynamic, "BGM_DIR", tmp_path / "empty_bgm")
    (tmp_path / "empty_bgm").mkdir()

    assert streamer._build_bgm_playlist() is None


def test_build_bgm_playlist_concatenates_every_track(streamer, tmp_path, monkeypatch):
    bgm_dir = tmp_path / "bgm"
    bgm_dir.mkdir()
    for i in range(3):
        (bgm_dir / f"jamendo_{i}.mp3").write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "BGM_DIR", bgm_dir)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-playlist")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(live_stream_dynamic.subprocess, "run", fake_run)

    playlist_path = streamer._build_bgm_playlist()

    assert playlist_path is not None
    assert playlist_path.read_bytes() == b"fake-playlist"
    concat_list = (streamer.temp_dir / "playlist_concat.txt").read_text()
    for i in range(3):
        assert f"jamendo_{i}.mp3" in concat_list


def test_build_bgm_playlist_reuses_existing_playlist(streamer, tmp_path, monkeypatch):
    bgm_dir = tmp_path / "bgm"
    bgm_dir.mkdir()
    (bgm_dir / "jamendo_1.mp3").write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "BGM_DIR", bgm_dir)
    existing_playlist = streamer.temp_dir / "playlist.mp3"
    existing_playlist.write_bytes(b"already-built")

    calls = []
    monkeypatch.setattr(live_stream_dynamic.subprocess, "run", lambda cmd, **k: calls.append(cmd))

    playlist_path = streamer._build_bgm_playlist()

    assert playlist_path == existing_playlist
    assert calls == []


def test_prepare_seamless_loop_clip_returns_raw_clip_for_short_clips(streamer, tmp_path, monkeypatch):
    clip_path = tmp_path / "pixabay_1.mp4"
    clip_path.write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "_media_duration_s", lambda path: 2.0)

    calls = []
    monkeypatch.setattr(live_stream_dynamic.subprocess, "run", lambda cmd, **k: calls.append(cmd))

    out = streamer._prepare_seamless_loop_clip(clip_path)

    assert out == clip_path
    assert calls == []


def test_prepare_seamless_loop_clip_returns_raw_clip_when_duration_unknown(streamer, tmp_path, monkeypatch):
    clip_path = tmp_path / "pixabay_1.mp4"
    clip_path.write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "_media_duration_s", lambda path: 0.0)

    calls = []
    monkeypatch.setattr(live_stream_dynamic.subprocess, "run", lambda cmd, **k: calls.append(cmd))

    out = streamer._prepare_seamless_loop_clip(clip_path)

    assert out == clip_path
    assert calls == []


def test_prepare_seamless_loop_clip_bakes_crossfade_for_normal_clips(streamer, tmp_path, monkeypatch):
    clip_path = tmp_path / "pixabay_1.mp4"
    clip_path.write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "_media_duration_s", lambda path: 20.0)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-seamless-clip")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(live_stream_dynamic.subprocess, "run", fake_run)

    out = streamer._prepare_seamless_loop_clip(clip_path)

    assert out == streamer.temp_dir / "seamless_pixabay_1.mp4"
    assert out.read_bytes() == b"fake-seamless-clip"
    cmd = calls[-1]
    assert "-filter_complex" in cmd
    assert "xfade" in cmd[cmd.index("-filter_complex") + 1]
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"


def test_prepare_seamless_loop_clip_reuses_existing_bake(streamer, tmp_path, monkeypatch):
    clip_path = tmp_path / "pixabay_1.mp4"
    clip_path.write_bytes(b"x")
    existing = streamer.temp_dir / "seamless_pixabay_1.mp4"
    existing.write_bytes(b"already-baked")

    calls = []
    monkeypatch.setattr(live_stream_dynamic.subprocess, "run", lambda cmd, **k: calls.append(cmd))

    out = streamer._prepare_seamless_loop_clip(clip_path)

    assert out == existing
    assert calls == []


def test_prepare_seamless_loop_clip_falls_back_to_raw_on_ffmpeg_failure(streamer, tmp_path, monkeypatch):
    clip_path = tmp_path / "pixabay_1.mp4"
    clip_path.write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "_media_duration_s", lambda path: 20.0)

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    monkeypatch.setattr(live_stream_dynamic.subprocess, "run", fake_run)

    out = streamer._prepare_seamless_loop_clip(clip_path)

    assert out == clip_path


def test_build_stream_command_returns_none_without_broll_clip(streamer, tmp_path, monkeypatch):
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", tmp_path / "empty_broll")
    (tmp_path / "empty_broll").mkdir()

    assert streamer.build_stream_command() is None


def test_build_stream_command_loops_clip_and_playlist_with_no_bake_duration(streamer, tmp_path, monkeypatch):
    broll_dir = tmp_path / "broll"
    broll_dir.mkdir()
    clip_path = broll_dir / "pixabay_1.mp4"
    clip_path.write_bytes(b"x")
    (broll_dir / "pixabay_1.json").write_text('{"tags": "anime, girl, study, lofi"}')
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", broll_dir)
    monkeypatch.setattr(streamer, "_prepare_seamless_loop_clip", lambda clip: clip)
    monkeypatch.setattr(streamer, "_build_bgm_playlist", lambda: tmp_path / "playlist.mp3")

    cmd = streamer.build_stream_command()

    assert cmd is not None
    assert str(clip_path) in cmd
    assert str(tmp_path / "playlist.mp3") in cmd
    assert "-map" in cmd
    assert "0:v" in cmd
    assert "1:a" in cmd
    assert cmd.count("-stream_loop") == 2
    assert "-t" not in cmd
    assert "rtmp://a.rtmp.youtube.com/live2/test-stream-key" in cmd
    assert "format=yuv420p" in cmd[cmd.index("-vf") + 1]


def test_build_stream_command_falls_back_to_silent_audio_without_bgm(streamer, tmp_path, monkeypatch):
    broll_dir = tmp_path / "broll"
    broll_dir.mkdir()
    (broll_dir / "pixabay_1.mp4").write_bytes(b"x")
    (broll_dir / "pixabay_1.json").write_text('{"tags": "anime, girl, study, lofi"}')
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", broll_dir)
    monkeypatch.setattr(streamer, "_prepare_seamless_loop_clip", lambda clip: clip)
    monkeypatch.setattr(streamer, "_build_bgm_playlist", lambda: None)

    cmd = streamer.build_stream_command()

    assert cmd is not None
    assert "anullsrc=r=44100:cl=stereo" in cmd
    assert cmd.count("-stream_loop") == 1


def test_build_stream_command_writes_local_file_in_test_mode(streamer, tmp_path, monkeypatch):
    broll_dir = tmp_path / "broll"
    broll_dir.mkdir()
    (broll_dir / "pixabay_1.mp4").write_bytes(b"x")
    (broll_dir / "pixabay_1.json").write_text('{"tags": "anime, girl, study, lofi"}')
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", broll_dir)
    monkeypatch.setattr(streamer, "_prepare_seamless_loop_clip", lambda clip: clip)
    monkeypatch.setattr(streamer, "_build_bgm_playlist", lambda: None)
    streamer.stream_key = "test"

    cmd = streamer.build_stream_command()

    assert "test_output.flv" in cmd


def test_build_stream_command_streams_to_rtmp_with_real_stream_key(streamer, tmp_path, monkeypatch):
    broll_dir = tmp_path / "broll"
    broll_dir.mkdir()
    (broll_dir / "pixabay_1.mp4").write_bytes(b"x")
    (broll_dir / "pixabay_1.json").write_text('{"tags": "anime, girl, study, lofi"}')
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", broll_dir)
    monkeypatch.setattr(streamer, "_prepare_seamless_loop_clip", lambda clip: clip)
    monkeypatch.setattr(streamer, "_build_bgm_playlist", lambda: None)
    streamer.stream_key = "real-secret-key"

    cmd = streamer.build_stream_command()

    assert "rtmp://a.rtmp.youtube.com/live2/real-secret-key" in cmd


def test_ensure_live_broadcast_reuses_active_broadcast(streamer):
    fake_youtube = MagicMock()
    fake_youtube.liveBroadcasts().list().execute.return_value = {
        "items": [
            {
                "id": "abc123",
                "status": {"lifeCycleStatus": "live"},
                "snippet": {
                    "title": live_stream_dynamic.BROADCAST_TITLE,
                    "description": live_stream_dynamic.BROADCAST_DESCRIPTION,
                },
            }
        ]
    }
    streamer.youtube = fake_youtube

    streamer.ensure_live_broadcast()

    assert streamer.broadcast_id == "abc123"
    fake_youtube.liveBroadcasts().insert.assert_not_called()
    fake_youtube.liveBroadcasts().update.assert_not_called()


def test_ensure_live_broadcast_rebrands_stale_active_broadcast(streamer):
    fake_youtube = MagicMock()
    fake_youtube.liveBroadcasts().list().execute.return_value = {
        "items": [
            {
                "id": "abc123",
                "status": {"lifeCycleStatus": "live"},
                "snippet": {
                    "title": "\U0001f534 24/7 Wild Nature & Animal Secrets | Ao Vivo | En Vivo",
                    "description": "Non-stop nature documentaries, wildlife facts and Earth science, looping live.",
                    "scheduledStartTime": "2026-07-15T00:00:00Z",
                },
            }
        ]
    }
    streamer.youtube = fake_youtube

    streamer.ensure_live_broadcast()

    assert streamer.broadcast_id == "abc123"
    fake_youtube.liveBroadcasts().insert.assert_not_called()
    update_call = fake_youtube.liveBroadcasts().update.call_args
    assert update_call.kwargs["body"]["id"] == "abc123"
    assert update_call.kwargs["body"]["snippet"]["title"] == live_stream_dynamic.BROADCAST_TITLE
    assert update_call.kwargs["body"]["snippet"]["description"] == live_stream_dynamic.BROADCAST_DESCRIPTION
    assert update_call.kwargs["body"]["snippet"]["scheduledStartTime"] == "2026-07-15T00:00:00Z"


def test_ensure_live_broadcast_leaves_a_manually_retitled_broadcast_alone(streamer):
    """A channel owner retitling the live from YouTube Studio must not get
    reverted on the next check-in -- only known-legacy titles (or a blank
    one) count as stale. See _rebrand_if_stale()'s docstring."""
    fake_youtube = MagicMock()
    fake_youtube.liveBroadcasts().list().execute.return_value = {
        "items": [
            {
                "id": "abc123",
                "status": {"lifeCycleStatus": "live"},
                "snippet": {
                    "title": "Rainy Night Study Session ☀️",
                    "description": "whatever the owner typed here",
                },
            }
        ]
    }
    streamer.youtube = fake_youtube

    streamer.ensure_live_broadcast()

    assert streamer.broadcast_id == "abc123"
    fake_youtube.liveBroadcasts().insert.assert_not_called()
    fake_youtube.liveBroadcasts().update.assert_not_called()


def test_ensure_live_broadcast_rebrands_a_blank_title(streamer):
    fake_youtube = MagicMock()
    fake_youtube.liveBroadcasts().list().execute.return_value = {
        "items": [
            {
                "id": "abc123",
                "status": {"lifeCycleStatus": "live"},
                "snippet": {"title": "", "description": ""},
            }
        ]
    }
    streamer.youtube = fake_youtube

    streamer.ensure_live_broadcast()

    update_call = fake_youtube.liveBroadcasts().update.call_args
    assert update_call.kwargs["body"]["snippet"]["title"] == live_stream_dynamic.BROADCAST_TITLE


def test_ensure_live_broadcast_creates_lofi_branded_broadcast_when_none_active(streamer):
    fake_youtube = MagicMock()
    fake_youtube.liveBroadcasts().list().execute.return_value = {"items": []}
    fake_youtube.liveStreams().list().execute.return_value = {
        "items": [{"id": "stream-1", "cdn": {"ingestionInfo": {"streamName": "test-stream-key"}}}]
    }
    fake_youtube.liveBroadcasts().insert().execute.return_value = {"id": "new-broadcast-1"}
    streamer.youtube = fake_youtube

    streamer.ensure_live_broadcast()

    assert streamer.broadcast_id == "new-broadcast-1"
    insert_call = fake_youtube.liveBroadcasts().insert.call_args
    body = insert_call.kwargs["body"]
    assert body["snippet"]["title"] == live_stream_dynamic.BROADCAST_TITLE
    assert "lofi" in body["snippet"]["title"].lower()
    assert "animal" not in body["snippet"]["title"].lower()
    assert "nature" not in body["snippet"]["title"].lower()
    fake_youtube.liveBroadcasts().bind.assert_called()


def test_ensure_live_broadcast_noop_without_youtube_client(streamer):
    streamer.youtube = None
    streamer.ensure_live_broadcast()
    assert streamer.broadcast_id is None
