from pathlib import Path
from unittest.mock import MagicMock

import pytest

import scripts.live_stream_classical as live_stream_classical


@pytest.fixture
def streamer(monkeypatch, tmp_path):
    monkeypatch.setattr(live_stream_classical.ClassicalStreamer, "_get_youtube_client", lambda self: None)
    monkeypatch.setattr(live_stream_classical, "generate_classical_video_copy", lambda **kwargs: None)
    instance = live_stream_classical.ClassicalStreamer("test-stream-key")
    instance.videos_dir = tmp_path / "_videos"
    instance.temp_dir = tmp_path / "_videos" / "temp_stream_classical"
    instance.temp_dir.mkdir(parents=True, exist_ok=True)
    return instance


def test_broadcast_copy_falls_back_to_template_when_no_ai(streamer):
    assert streamer.broadcast_title == live_stream_classical._FALLBACK_BROADCAST_TITLE
    assert streamer.broadcast_description == live_stream_classical._FALLBACK_BROADCAST_DESCRIPTION


def test_broadcast_copy_uses_ai_result_and_appends_generic_jamendo_credit(monkeypatch, tmp_path):
    ai_result = {"title": "Classical Radio -- Amber Hours Classical", "description": "Real classical music, live."}
    monkeypatch.setattr(live_stream_classical.ClassicalStreamer, "_get_youtube_client", lambda self: None)
    monkeypatch.setattr(live_stream_classical, "generate_classical_video_copy", lambda **kwargs: ai_result)

    instance = live_stream_classical.ClassicalStreamer("test-stream-key")

    assert instance.broadcast_title == ai_result["title"]
    assert "Real classical music, live." in instance.broadcast_description
    assert "Jamendo" in instance.broadcast_description
    assert "Creative Commons Attribution" in instance.broadcast_description


def test_build_playlist_returns_none_when_library_empty(streamer, tmp_path, monkeypatch):
    monkeypatch.setattr(live_stream_classical, "CLASSICAL_DIR", tmp_path / "empty")

    assert streamer._build_playlist() is None


def test_build_playlist_concatenates_every_synced_track(streamer, tmp_path, monkeypatch):
    classical_dir = tmp_path / "classical"
    classical_dir.mkdir()
    (classical_dir / "jamendo_1.mp3").write_bytes(b"x")
    (classical_dir / "jamendo_2.mp3").write_bytes(b"x")
    monkeypatch.setattr(live_stream_classical, "CLASSICAL_DIR", classical_dir)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-mp3")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(live_stream_classical.subprocess, "run", fake_run)

    playlist = streamer._build_playlist()

    assert playlist is not None
    assert playlist.exists()
    concat_list = (streamer.temp_dir / "classical_playlist_concat.txt").read_text(encoding="utf-8")
    assert "jamendo_1.mp3" in concat_list
    assert "jamendo_2.mp3" in concat_list


def test_build_stream_command_returns_none_without_pinned_clip(streamer, tmp_path, monkeypatch):
    monkeypatch.setattr(live_stream_classical, "PINNED_BROLL_CLIP", tmp_path / "missing.mp4")

    assert streamer.build_stream_command() is None


def test_build_stream_command_returns_none_without_any_synced_tracks(streamer, tmp_path, monkeypatch):
    pinned = tmp_path / "pinned_classical_ambience.mp4"
    pinned.write_bytes(b"x")
    monkeypatch.setattr(live_stream_classical, "PINNED_BROLL_CLIP", pinned)
    monkeypatch.setattr(live_stream_classical, "CLASSICAL_DIR", tmp_path / "empty")

    assert streamer.build_stream_command() is None


def test_build_stream_command_streams_to_rtmp_with_real_stream_key(streamer, tmp_path, monkeypatch):
    pinned = tmp_path / "pinned_classical_ambience.mp4"
    pinned.write_bytes(b"x")
    monkeypatch.setattr(live_stream_classical, "PINNED_BROLL_CLIP", pinned)
    monkeypatch.setattr(streamer, "_prepare_seamless_loop_clip", lambda clip: clip)
    monkeypatch.setattr(streamer, "_build_playlist", lambda: tmp_path / "playlist.mp3")
    streamer.stream_key = "real-secret-key"

    cmd = streamer.build_stream_command()

    assert cmd is not None
    assert "rtmp://a.rtmp.youtube.com/live2/real-secret-key" in cmd
    assert cmd.count("-stream_loop") == 2  # video AND the playlist both loop forever


def test_build_stream_command_writes_local_file_in_test_mode(streamer, tmp_path, monkeypatch):
    pinned = tmp_path / "pinned_classical_ambience.mp4"
    pinned.write_bytes(b"x")
    monkeypatch.setattr(live_stream_classical, "PINNED_BROLL_CLIP", pinned)
    monkeypatch.setattr(streamer, "_prepare_seamless_loop_clip", lambda clip: clip)
    monkeypatch.setattr(streamer, "_build_playlist", lambda: tmp_path / "playlist.mp3")
    streamer.stream_key = "test"

    cmd = streamer.build_stream_command()

    assert "test_output_classical.flv" in cmd


def test_set_thumbnail_skips_silently_when_file_missing(streamer, monkeypatch, tmp_path):
    fake_youtube = MagicMock()
    streamer.youtube = fake_youtube
    monkeypatch.setattr(live_stream_classical, "THUMBNAIL_IMAGE", tmp_path / "missing.jpg")

    streamer._set_thumbnail("some-video-id")

    fake_youtube.thumbnails().set.assert_not_called()


def test_ensure_live_broadcast_creates_classical_branded_broadcast_when_none_active(streamer):
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
    assert body["snippet"]["title"] == live_stream_classical._FALLBACK_BROADCAST_TITLE
    assert "Amber Hours Classical" in body["snippet"]["title"]
    fake_youtube.liveBroadcasts().bind.assert_called()
    fake_youtube.thumbnails().set.assert_called_once()


def test_ensure_live_broadcast_reuses_active_broadcast_with_current_title(streamer):
    fake_youtube = MagicMock()
    fake_youtube.liveBroadcasts().list().execute.return_value = {
        "items": [
            {
                "id": "abc123",
                "status": {"lifeCycleStatus": "live"},
                "snippet": {
                    "title": "Some Previous AI-Generated Title -- Amber Hours Classical",
                    "description": "Some previous description.",
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
    fake_youtube = MagicMock()
    fake_youtube.liveBroadcasts().list().execute.return_value = {
        "items": [
            {
                "id": "abc123",
                "status": {"lifeCycleStatus": "live"},
                "snippet": {
                    "title": live_stream_classical._FALLBACK_BROADCAST_TITLE,
                    "description": live_stream_classical._FALLBACK_BROADCAST_DESCRIPTION,
                },
            }
        ]
    }
    streamer.youtube = fake_youtube

    streamer.ensure_live_broadcast()

    update_call = fake_youtube.liveBroadcasts().update
    update_call.assert_called_once()
    assert update_call.call_args.kwargs["body"]["snippet"]["title"] == streamer.broadcast_title


def test_ensure_live_broadcast_noop_without_youtube_client(streamer):
    streamer.youtube = None
    streamer.ensure_live_broadcast()
    assert streamer.broadcast_id is None


def test_run_bails_out_without_pinned_clip(streamer, tmp_path, monkeypatch):
    monkeypatch.setattr(live_stream_classical, "PINNED_BROLL_CLIP", tmp_path / "missing.mp4")
    ensure_broadcast = MagicMock()
    monkeypatch.setattr(streamer, "ensure_live_broadcast", ensure_broadcast)

    streamer.run()

    ensure_broadcast.assert_not_called()


def test_run_bails_out_without_any_synced_tracks(streamer, tmp_path, monkeypatch):
    pinned = tmp_path / "pinned_classical_ambience.mp4"
    pinned.write_bytes(b"x")
    monkeypatch.setattr(live_stream_classical, "PINNED_BROLL_CLIP", pinned)
    monkeypatch.setattr(live_stream_classical, "CLASSICAL_DIR", tmp_path / "empty")
    ensure_broadcast = MagicMock()
    monkeypatch.setattr(streamer, "ensure_live_broadcast", ensure_broadcast)

    streamer.run()

    ensure_broadcast.assert_not_called()


def test_run_proceeds_past_the_guard_when_clip_and_tracks_exist(streamer, tmp_path, monkeypatch):
    pinned = tmp_path / "pinned_classical_ambience.mp4"
    pinned.write_bytes(b"x")
    classical_dir = tmp_path / "classical"
    classical_dir.mkdir()
    (classical_dir / "jamendo_1.mp3").write_bytes(b"x")
    monkeypatch.setattr(live_stream_classical, "PINNED_BROLL_CLIP", pinned)
    monkeypatch.setattr(live_stream_classical, "CLASSICAL_DIR", classical_dir)
    monkeypatch.setattr(streamer, "ensure_live_broadcast", MagicMock())
    monkeypatch.setattr(live_stream_classical.threading, "Thread", MagicMock())
    monkeypatch.setattr(streamer, "build_stream_command", MagicMock(side_effect=RuntimeError("reached main loop")))

    with pytest.raises(RuntimeError, match="reached main loop"):
        streamer.run()
