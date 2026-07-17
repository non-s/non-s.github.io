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


def test_pick_broll_clip_returns_none_when_library_empty(streamer, tmp_path, monkeypatch):
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", tmp_path / "empty_broll")
    (tmp_path / "empty_broll").mkdir()

    assert streamer._pick_broll_clip() is None


def test_pick_broll_clip_returns_a_clip_when_present(streamer, tmp_path, monkeypatch):
    broll_dir = tmp_path / "broll"
    broll_dir.mkdir()
    (broll_dir / "pixabay_1.mp4").write_bytes(b"x")
    (broll_dir / "pixabay_2.mp4").write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", broll_dir)

    picked = streamer._pick_broll_clip()

    assert picked in {broll_dir / "pixabay_1.mp4", broll_dir / "pixabay_2.mp4"}


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


def test_build_loop_segment_returns_none_without_broll_clip(streamer, tmp_path, monkeypatch):
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", tmp_path / "empty_broll")
    (tmp_path / "empty_broll").mkdir()

    assert streamer.build_loop_segment() is None


def test_build_loop_segment_mixes_full_playlist_when_available(streamer, tmp_path, monkeypatch):
    broll_dir = tmp_path / "broll"
    broll_dir.mkdir()
    clip_path = broll_dir / "pixabay_1.mp4"
    clip_path.write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", broll_dir)
    monkeypatch.setattr(streamer, "_build_bgm_playlist", lambda: tmp_path / "playlist.mp3")
    monkeypatch.setattr(live_stream_dynamic, "_audio_duration_s", lambda path: 900.0)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-ts")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(live_stream_dynamic.subprocess, "run", fake_run)

    out_ts = streamer.build_loop_segment()

    assert out_ts is not None and out_ts.exists()
    cmd = calls[-1]
    assert str(clip_path) in cmd
    assert str(tmp_path / "playlist.mp3") in cmd
    assert "-map" in cmd
    assert "0:v" in cmd
    assert "1:a" in cmd
    assert cmd[cmd.index("-t") + 1] == "900.000"
    assert cmd.count("-stream_loop") == 2


def test_build_loop_segment_falls_back_to_silent_audio_without_bgm(streamer, tmp_path, monkeypatch):
    broll_dir = tmp_path / "broll"
    broll_dir.mkdir()
    (broll_dir / "pixabay_1.mp4").write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", broll_dir)
    monkeypatch.setattr(streamer, "_build_bgm_playlist", lambda: None)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-ts")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(live_stream_dynamic.subprocess, "run", fake_run)

    out_ts = streamer.build_loop_segment()

    assert out_ts is not None
    cmd = calls[-1]
    assert "anullsrc=r=44100:cl=stereo" in cmd
    assert cmd.count("-stream_loop") == 1


def test_build_loop_segment_reuses_existing_segment(streamer, tmp_path, monkeypatch):
    broll_dir = tmp_path / "broll"
    broll_dir.mkdir()
    (broll_dir / "pixabay_1.mp4").write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", broll_dir)
    existing_ts = streamer.temp_dir / "loop_segment.ts"
    existing_ts.write_bytes(b"already-built")

    calls = []
    monkeypatch.setattr(live_stream_dynamic.subprocess, "run", lambda cmd, **k: calls.append(cmd))

    out_ts = streamer.build_loop_segment()

    assert out_ts == existing_ts
    assert calls == []


def test_build_loop_segment_returns_none_on_ffmpeg_failure(streamer, tmp_path, monkeypatch):
    broll_dir = tmp_path / "broll"
    broll_dir.mkdir()
    (broll_dir / "pixabay_1.mp4").write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "BROLL_DIR", broll_dir)
    monkeypatch.setattr(streamer, "_build_bgm_playlist", lambda: None)

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "boom"
        return result

    monkeypatch.setattr(live_stream_dynamic.subprocess, "run", fake_run)

    assert streamer.build_loop_segment() is None


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
