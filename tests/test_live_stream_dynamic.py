from pathlib import Path
from unittest.mock import MagicMock

import pytest

import scripts.live_stream_dynamic as live_stream_dynamic


@pytest.fixture
def streamer(monkeypatch, tmp_path):
    monkeypatch.setattr(live_stream_dynamic.DynamicStreamer, "_get_youtube_client", lambda self: None)
    instance = live_stream_dynamic.DynamicStreamer("test-stream-key")
    instance.videos_dir = tmp_path / "_videos"
    instance.temp_dir = tmp_path / "_videos" / "temp_stream"
    instance.temp_dir.mkdir(parents=True, exist_ok=True)
    return instance


def test_pick_broll_clip_returns_none_without_pinned_clip(streamer, tmp_path, monkeypatch):
    monkeypatch.setattr(live_stream_dynamic, "STORM_PINNED_BROLL_CLIP", tmp_path / "missing.mp4")
    monkeypatch.setattr(live_stream_dynamic, "STORM_REAL_PINNED_CLIP", tmp_path / "missing_real_clip.mp4")

    assert streamer._pick_broll_clip() is None


def test_pick_broll_clip_returns_the_pinned_storm_clip(streamer, tmp_path, monkeypatch):
    storm_clip = tmp_path / "pinned_storm_clip.mp4"
    storm_clip.write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "STORM_PINNED_BROLL_CLIP", storm_clip)
    monkeypatch.setattr(live_stream_dynamic, "STORM_REAL_PINNED_CLIP", tmp_path / "missing_real_clip.mp4")

    assert streamer._pick_broll_clip() == storm_clip


def test_pick_broll_clip_prefers_the_real_clip_over_the_illustrated_one(streamer, tmp_path, monkeypatch):
    real_clip = tmp_path / "pinned_storm_live.mp4"
    real_clip.write_bytes(b"x")
    illustrated_clip = tmp_path / "pinned_storm_clip.mp4"
    illustrated_clip.write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "STORM_REAL_PINNED_CLIP", real_clip)
    monkeypatch.setattr(live_stream_dynamic, "STORM_PINNED_BROLL_CLIP", illustrated_clip)

    assert streamer._pick_broll_clip() == real_clip


def test_run_bails_out_without_starting_when_no_pinned_clip(streamer, tmp_path, monkeypatch):
    monkeypatch.setattr(live_stream_dynamic, "STORM_PINNED_BROLL_CLIP", tmp_path / "missing.mp4")
    monkeypatch.setattr(live_stream_dynamic, "STORM_REAL_PINNED_CLIP", tmp_path / "missing_real_clip.mp4")
    ensure_broadcast = MagicMock()
    monkeypatch.setattr(streamer, "ensure_live_broadcast", ensure_broadcast)

    streamer.run()

    ensure_broadcast.assert_not_called()


def test_run_proceeds_past_the_guard_when_pinned_clip_exists(streamer, tmp_path, monkeypatch):
    storm_clip = tmp_path / "pinned_storm_clip.mp4"
    storm_clip.write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "STORM_PINNED_BROLL_CLIP", storm_clip)
    monkeypatch.setattr(live_stream_dynamic, "STORM_REAL_PINNED_CLIP", tmp_path / "missing_real_clip.mp4")
    monkeypatch.setattr(streamer, "ensure_live_broadcast", MagicMock())
    monkeypatch.setattr(live_stream_dynamic.threading, "Thread", MagicMock())
    # run()'s main loop is an infinite `while True` around a real ffmpeg
    # subprocess -- not something to execute in a unit test. build_stream_command()
    # raising short-circuits that inner loop back to the guard check we
    # actually care about, so raise once we're sure the guard let us in.
    monkeypatch.setattr(streamer, "build_stream_command", MagicMock(side_effect=RuntimeError("reached main loop")))

    with pytest.raises(RuntimeError, match="reached main loop"):
        streamer.run()

    streamer.ensure_live_broadcast.assert_called_once()


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


def test_build_stream_command_returns_none_without_pinned_clip(streamer, tmp_path, monkeypatch):
    monkeypatch.setattr(live_stream_dynamic, "STORM_PINNED_BROLL_CLIP", tmp_path / "missing.mp4")
    monkeypatch.setattr(live_stream_dynamic, "STORM_REAL_PINNED_CLIP", tmp_path / "missing_real_clip.mp4")

    assert streamer.build_stream_command() is None


def test_build_stream_command_writes_local_file_in_test_mode(streamer, tmp_path, monkeypatch):
    storm_clip = tmp_path / "pinned_storm_clip.mp4"
    storm_clip.write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "STORM_PINNED_BROLL_CLIP", storm_clip)
    monkeypatch.setattr(live_stream_dynamic, "STORM_REAL_PINNED_CLIP", tmp_path / "missing_real_clip.mp4")
    monkeypatch.setattr(streamer, "_prepare_seamless_loop_clip", lambda clip: clip)
    monkeypatch.setattr(streamer, "_build_storm_audio_input", lambda: tmp_path / "rain.wav")
    streamer.stream_key = "test"

    cmd = streamer.build_stream_command()

    assert "test_output.flv" in cmd


def test_build_stream_command_streams_to_rtmp_with_real_stream_key(streamer, tmp_path, monkeypatch):
    storm_clip = tmp_path / "pinned_storm_clip.mp4"
    storm_clip.write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "STORM_PINNED_BROLL_CLIP", storm_clip)
    monkeypatch.setattr(live_stream_dynamic, "STORM_REAL_PINNED_CLIP", tmp_path / "missing_real_clip.mp4")
    monkeypatch.setattr(streamer, "_prepare_seamless_loop_clip", lambda clip: clip)
    monkeypatch.setattr(streamer, "_build_storm_audio_input", lambda: tmp_path / "rain.wav")
    streamer.stream_key = "real-secret-key"

    cmd = streamer.build_stream_command()

    assert "rtmp://a.rtmp.youtube.com/live2/real-secret-key" in cmd


def test_ensure_live_broadcast_reuses_active_broadcast(streamer):
    # A title that is neither blank nor in _LEGACY_BROADCAST_TITLES (the
    # fallback template itself is now IN that set, since a fallback-titled
    # broadcast should get upgraded to a fresh AI title -- see
    # test_rebrand_if_stale_replaces_the_fallback_template below) --
    # this one stands in for "already carrying a current, non-stale
    # title" (e.g. a previous run's own AI-generated title).
    fake_youtube = MagicMock()
    fake_youtube.liveBroadcasts().list().execute.return_value = {
        "items": [
            {
                "id": "abc123",
                "status": {"lifeCycleStatus": "live"},
                "snippet": {
                    "title": "Chuva Forte na Cabana da Floresta -- Amber Hours",
                    "description": "Some previously AI-generated description.",
                },
            }
        ]
    }
    streamer.youtube = fake_youtube

    streamer.ensure_live_broadcast()

    assert streamer.broadcast_id == "abc123"
    fake_youtube.liveBroadcasts().insert.assert_not_called()
    fake_youtube.liveBroadcasts().update.assert_not_called()


def test_rebrand_if_stale_replaces_the_fallback_template(streamer):
    """The fallback template title is itself treated as stale/upgradeable
    -- once real AI titling exists, a broadcast still carrying the
    fallback should get replaced by this run's self.broadcast_title on
    its next check-in, same as any other legacy title."""
    fake_youtube = MagicMock()
    fake_youtube.liveBroadcasts().list().execute.return_value = {
        "items": [
            {
                "id": "abc123",
                "status": {"lifeCycleStatus": "live"},
                "snippet": {
                    "title": live_stream_dynamic._FALLBACK_BROADCAST_TITLE,
                    "description": live_stream_dynamic._FALLBACK_BROADCAST_DESCRIPTION,
                },
            }
        ]
    }
    streamer.youtube = fake_youtube

    streamer.ensure_live_broadcast()

    update_call = fake_youtube.liveBroadcasts().update
    update_call.assert_called_once()
    assert update_call.call_args.kwargs["body"]["snippet"]["title"] == streamer.broadcast_title
    assert update_call.call_args.kwargs["body"]["snippet"]["description"] == streamer.broadcast_description


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
    assert update_call.kwargs["body"]["snippet"]["title"] == live_stream_dynamic._FALLBACK_BROADCAST_TITLE
    assert update_call.kwargs["body"]["snippet"]["description"] == live_stream_dynamic._FALLBACK_BROADCAST_DESCRIPTION
    assert update_call.kwargs["body"]["snippet"]["scheduledStartTime"] == "2026-07-15T00:00:00Z"


def test_ensure_live_broadcast_rebrands_the_old_lofi_broadcast(streamer):
    """Regression for the pivot away from lofi (growth pass, 2026-07-21):
    a broadcast still carrying the old anime-lofi title must get corrected
    to the current rain & thunder branding on its next check-in."""
    fake_youtube = MagicMock()
    fake_youtube.liveBroadcasts().list().execute.return_value = {
        "items": [
            {
                "id": "abc123",
                "status": {"lifeCycleStatus": "live"},
                "snippet": {
                    "title": "Rainy Night Anime Lofi — Amber Hours \U0001f319 [24/7 LIVE]",
                    "description": "Non-stop lofi beats, looping live -- cozy visuals and chill music.",
                    "scheduledStartTime": "2026-07-15T00:00:00Z",
                },
            }
        ]
    }
    streamer.youtube = fake_youtube

    streamer.ensure_live_broadcast()

    update_call = fake_youtube.liveBroadcasts().update.call_args
    assert update_call.kwargs["body"]["snippet"]["title"] == live_stream_dynamic._FALLBACK_BROADCAST_TITLE
    assert update_call.kwargs["body"]["snippet"]["description"] == live_stream_dynamic._FALLBACK_BROADCAST_DESCRIPTION


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
    assert update_call.kwargs["body"]["snippet"]["title"] == live_stream_dynamic._FALLBACK_BROADCAST_TITLE


def test_ensure_live_broadcast_creates_storm_branded_broadcast_when_none_active(streamer):
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
    assert body["snippet"]["title"] == live_stream_dynamic._FALLBACK_BROADCAST_TITLE
    assert "chuva" in body["snippet"]["title"].lower()
    assert "lofi" not in body["snippet"]["title"].lower()
    assert "animal" not in body["snippet"]["title"].lower()
    assert "nature" not in body["snippet"]["title"].lower()
    fake_youtube.liveBroadcasts().bind.assert_called()
    fake_youtube.thumbnails().set.assert_called_once()
    assert fake_youtube.thumbnails().set.call_args.kwargs["videoId"] == "new-broadcast-1"


def test_set_thumbnail_skips_silently_when_file_missing(streamer, monkeypatch, tmp_path):
    fake_youtube = MagicMock()
    streamer.youtube = fake_youtube
    monkeypatch.setattr(live_stream_dynamic, "ROOT", tmp_path)

    streamer._set_thumbnail("some-video-id")

    fake_youtube.thumbnails().set.assert_not_called()


def test_ensure_live_broadcast_noop_without_youtube_client(streamer):
    streamer.youtube = None
    streamer.ensure_live_broadcast()
    assert streamer.broadcast_id is None


def test_build_storm_audio_input_returns_a_rain_bed(streamer):
    rain_bed_path = streamer._build_storm_audio_input()

    assert rain_bed_path.exists()
    assert rain_bed_path.stat().st_size > 0


def test_build_storm_audio_input_reuses_an_existing_rain_bed(streamer):
    first_path = streamer._build_storm_audio_input()
    first_mtime = first_path.stat().st_mtime_ns

    second_path = streamer._build_storm_audio_input()

    assert second_path == first_path
    assert second_path.stat().st_mtime_ns == first_mtime


def test_build_stream_command_is_pure_rain_no_music_layer(streamer, tmp_path, monkeypatch):
    storm_clip = tmp_path / "pinned_storm_clip.mp4"
    storm_clip.write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "STORM_PINNED_BROLL_CLIP", storm_clip)
    monkeypatch.setattr(live_stream_dynamic, "STORM_REAL_PINNED_CLIP", tmp_path / "missing_real_clip.mp4")
    monkeypatch.setattr(streamer, "_prepare_seamless_loop_clip", lambda clip: clip)
    monkeypatch.setattr(streamer, "_build_storm_audio_input", lambda: tmp_path / "rain.wav")

    cmd = streamer.build_stream_command()

    assert cmd is not None
    assert "-filter_complex" not in cmd
    assert cmd.count("-stream_loop") == 2
