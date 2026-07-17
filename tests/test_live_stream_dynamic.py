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


def test_pick_bgm_track_returns_none_when_library_empty(streamer, tmp_path, monkeypatch):
    monkeypatch.setattr(live_stream_dynamic, "BGM_DIR", tmp_path / "empty_bgm")
    (tmp_path / "empty_bgm").mkdir()

    assert streamer._pick_bgm_track() is None


def test_pick_bgm_track_returns_a_track_when_present(streamer, tmp_path, monkeypatch):
    bgm_dir = tmp_path / "bgm"
    bgm_dir.mkdir()
    (bgm_dir / "ytcc_1.mp3").write_bytes(b"x")
    (bgm_dir / "ytcc_2.mp3").write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "BGM_DIR", bgm_dir)

    picked = streamer._pick_bgm_track()

    assert picked in {bgm_dir / "ytcc_1.mp3", bgm_dir / "ytcc_2.mp3"}


def test_convert_to_ts_mixes_bgm_when_available(streamer, tmp_path, monkeypatch):
    bgm_dir = tmp_path / "bgm"
    bgm_dir.mkdir()
    bgm_path = bgm_dir / "ytcc_1.mp3"
    bgm_path.write_bytes(b"x")
    monkeypatch.setattr(live_stream_dynamic, "BGM_DIR", bgm_dir)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-ts")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(live_stream_dynamic.subprocess, "run", fake_run)

    mp4_path = tmp_path / "long_video_x.mp4"
    mp4_path.write_bytes(b"x")

    out_ts = streamer.convert_to_ts(mp4_path)

    assert out_ts.exists()
    cmd = calls[-1]
    assert "-stream_loop" in cmd
    assert str(bgm_path) in cmd
    assert "-map" in cmd
    assert "0:v" in cmd
    assert "1:a" in cmd


def test_convert_to_ts_streams_silent_when_no_bgm(streamer, tmp_path, monkeypatch):
    monkeypatch.setattr(live_stream_dynamic, "BGM_DIR", tmp_path / "no_bgm")
    (tmp_path / "no_bgm").mkdir()

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-ts")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(live_stream_dynamic.subprocess, "run", fake_run)

    mp4_path = tmp_path / "long_video_y.mp4"
    mp4_path.write_bytes(b"x")

    out_ts = streamer.convert_to_ts(mp4_path)

    assert out_ts.exists()
    cmd = calls[-1]
    assert "-an" not in cmd
    assert "anullsrc=r=44100:cl=stereo" in cmd
    assert "-stream_loop" not in cmd


def test_convert_to_ts_reuses_existing_ts_file(streamer, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(live_stream_dynamic.subprocess, "run", lambda cmd, **k: calls.append(cmd))

    mp4_path = tmp_path / "long_video_z.mp4"
    mp4_path.write_bytes(b"x")
    existing_ts = streamer.temp_dir / "long_video_z.ts"
    existing_ts.write_bytes(b"already-converted")

    out_ts = streamer.convert_to_ts(mp4_path)

    assert out_ts == existing_ts
    assert calls == []


def test_ensure_live_broadcast_reuses_active_broadcast(streamer):
    fake_youtube = MagicMock()
    fake_youtube.liveBroadcasts().list().execute.return_value = {
        "items": [{"id": "abc123", "status": {"lifeCycleStatus": "live"}}]
    }
    streamer.youtube = fake_youtube

    streamer.ensure_live_broadcast()

    assert streamer.broadcast_id == "abc123"
    fake_youtube.liveBroadcasts().insert.assert_not_called()


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
