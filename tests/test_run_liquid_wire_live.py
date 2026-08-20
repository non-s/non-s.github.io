from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.run_liquid_wire_live import (
    _ingestion_url,
    broadcast_resilient,
    create_live,
    prepare_live_asset,
    stream_video,
)


def test_ingestion_url_builds_rtmp_address() -> None:
    stream = {
        "cdn": {
            "ingestionInfo": {
                "ingestionAddress": "rtmp://a.rtmp.youtube.com",
                "streamName": "live_123_xyz",
            }
        }
    }
    assert _ingestion_url(stream) == "rtmp://a.rtmp.youtube.com/live_123_xyz"


def test_ingestion_url_strips_trailing_slash() -> None:
    stream = {
        "cdn": {
            "ingestionInfo": {
                "ingestionAddress": "rtmp://a.rtmp.youtube.com/",
                "streamName": "abc",
            }
        }
    }
    assert _ingestion_url(stream) == "rtmp://a.rtmp.youtube.com/abc"


def test_ingestion_url_raises_on_missing_fields() -> None:
    with pytest.raises(RuntimeError, match="RTMP"):
        _ingestion_url({"cdn": {"ingestionInfo": {"ingestionAddress": "", "streamName": ""}}})
    with pytest.raises(RuntimeError, match="RTMP"):
        _ingestion_url({})
    with pytest.raises(RuntimeError, match="RTMP"):
        _ingestion_url({"cdn": {}})


def test_ingestion_url_raises_when_only_address_present() -> None:
    stream = {"cdn": {"ingestionInfo": {"ingestionAddress": "rtmp://a.rtmp.youtube.com"}}}
    with pytest.raises(RuntimeError):
        _ingestion_url(stream)


class _Request:
    def __init__(self, value: dict) -> None:
        self._value = value

    def execute(self) -> dict:
        return self._value


class _LiveService:
    def __init__(self, broadcast_id: str = "b1", stream_id: str = "s1") -> None:
        self._broadcast_id = broadcast_id
        self._stream_id = stream_id
        self.bind_called = False

    def liveBroadcasts(self) -> _LiveService:
        return self

    def liveStreams(self) -> _LiveService:
        return self

    def insert(self, **kwargs) -> _Request:
        if "snippet,status,contentDetails" in kwargs.get("part", ""):
            return _Request({"id": self._broadcast_id})
        return _Request(
            {
                "id": self._stream_id,
                "cdn": {
                    "ingestionInfo": {
                        "ingestionAddress": "rtmp://a.rtmp.youtube.com",
                        "streamName": "stream_key_123",
                    }
                },
            }
        )

    def bind(self, **kwargs) -> _Request:
        self.bind_called = True
        return _Request({})

    def transition(self, **kwargs) -> _Request:
        return _Request({})


def test_create_live_returns_broadcast_id_and_rtmp_url() -> None:
    service = _LiveService()
    broadcast_id, rtmp_url = create_live(service, title="Test Live", privacy="public")
    assert broadcast_id == "b1"
    assert rtmp_url == "rtmp://a.rtmp.youtube.com/stream_key_123"
    assert service.bind_called is True


def test_create_live_raises_when_ids_missing() -> None:
    service = _LiveService(broadcast_id="", stream_id="")
    with pytest.raises(RuntimeError, match="broadcast and stream IDs"):
        create_live(service, title="Test Live", privacy="public")


def test_stream_video_raises_on_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "nonexistent.mp4"
    with pytest.raises(FileNotFoundError):
        stream_video(missing, "rtmp://example.com/live", 10)


def test_stream_video_invokes_ffmpeg(tmp_path: Path) -> None:
    video = tmp_path / "test.mp4"
    video.write_bytes(b"fake video content")

    with patch("scripts.run_liquid_wire_live.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        stream_video(video, "rtmp://example.com/live", 5)

    assert mock_run.called
    cmd = mock_run.call_args.args[0]
    assert cmd[0] == "ffmpeg"
    assert "-re" in cmd
    assert "-stream_loop" in cmd
    assert cmd[cmd.index("-c") + 1] == "copy"
    assert "-f" in cmd
    assert "flv" in cmd
    assert "rtmp://example.com/live" == cmd[-1]


def test_prepare_live_asset_encodes_once_to_bounded_delivery_format(tmp_path: Path) -> None:
    video = tmp_path / "source.mp4"
    output = tmp_path / "delivery.mp4"
    video.write_bytes(b"source")

    def completed(command, **kwargs):
        output.write_bytes(b"x" * 2048)
        return MagicMock(returncode=0)

    with patch("scripts.run_liquid_wire_live.subprocess.run", side_effect=completed) as run:
        assert prepare_live_asset(video, output) == output
    command = run.call_args.args[0]
    assert command[command.index("-b:v") + 1] == "6000k"
    assert command[command.index("-g") + 1] == "60"


def test_stream_video_can_inject_one_controlled_disconnect(tmp_path: Path) -> None:
    video = tmp_path / "source.mp4"
    video.write_bytes(b"video")
    process = MagicMock()
    process.wait.side_effect = [__import__("subprocess").TimeoutExpired(["ffmpeg"], 2), 0]
    process.returncode = -9
    with patch("scripts.run_liquid_wire_live.subprocess.Popen", return_value=process):
        with pytest.raises(__import__("subprocess").CalledProcessError) as error:
            stream_video(video, "rtmp://example/live", 5, chaos_after_seconds=2)
    assert error.value.returncode == 86
    process.kill.assert_called_once()


def test_main_validates_duration_range() -> None:
    import scripts.run_liquid_wire_live as live

    # duration-minutes=3 is below the 5-minute minimum; argparse should exit.
    with patch("sys.argv", ["run_liquid_wire_live.py", "--video", "x.mp4", "--duration-minutes", "3"]):
        with pytest.raises(SystemExit):
            live.main()


def test_resilient_broadcast_immediately_replaces_broken_rtmp(tmp_path: Path) -> None:
    video = tmp_path / "source.mp4"
    video.write_bytes(b"video")
    failure = __import__("subprocess").CalledProcessError(1, ["ffmpeg"])
    with (
        patch("scripts.run_liquid_wire_live.create_live", side_effect=[("b1", "rtmp://one"), ("b2", "rtmp://two")]),
        patch("scripts.run_liquid_wire_live.stream_video", side_effect=[failure, None]) as stream,
        patch("scripts.run_liquid_wire_live.time.monotonic", side_effect=[0.0, 61.0, 62.0, 63.0]),
    ):
        ids = broadcast_resilient(_LiveService(), video, 30, "public", max_restarts=2)
    assert ids == ["b1", "b2"]
    assert stream.call_count == 2
    assert stream.call_args_list[1].args[-1] == 28


def test_resilient_broadcast_records_recovery_latency_and_chaos_evidence(tmp_path: Path) -> None:
    video = tmp_path / "source.mp4"
    journal = tmp_path / "live_continuity.json"
    video.write_bytes(b"video")
    failure = __import__("subprocess").CalledProcessError(86, ["ffmpeg"])
    with (
        patch("scripts.run_liquid_wire_live.create_live", side_effect=[("b1", "rtmp://one"), ("b2", "rtmp://two")]),
        patch("scripts.run_liquid_wire_live.stream_video", side_effect=[failure, None]) as stream,
        patch("scripts.run_liquid_wire_live.time.monotonic", side_effect=[10.0, 12.0, 12.4, 13.0]),
    ):
        ids = broadcast_resilient(
            _LiveService(), video, 10, "unlisted", max_restarts=2,
            chaos_after_seconds=2, journal_path=journal, preparation_seconds=7.25,
        )
    payload = __import__("json").loads(journal.read_text())
    assert ids == ["b1", "b2"]
    assert payload["completed"] is True
    assert payload["source_preparation_seconds"] == 7.25
    assert payload["attempts"][0]["outcome"] == "disconnected"
    assert payload["attempts"][1]["recovery_latency_seconds"] == .4
    assert stream.call_args_list[0].kwargs["chaos_after_seconds"] == 2
    assert stream.call_args_list[1].kwargs["chaos_after_seconds"] == 0


def test_resilient_broadcast_recovers_from_temporary_creation_failure(tmp_path: Path) -> None:
    video = tmp_path / "source.mp4"
    journal = tmp_path / "live_continuity.json"
    video.write_bytes(b"video")
    with (
        patch("scripts.run_liquid_wire_live.create_live", side_effect=[RuntimeError("api"), ("b2", "rtmp://two")]),
        patch("scripts.run_liquid_wire_live.stream_video") as stream,
        patch("scripts.run_liquid_wire_live.time.sleep"),
        patch("scripts.run_liquid_wire_live.time.monotonic", side_effect=[1.0, 1.5, 2.0]),
    ):
        ids = broadcast_resilient(
            _LiveService(), video, 10, "unlisted", max_restarts=2, journal_path=journal,
        )
    payload = __import__("json").loads(journal.read_text())
    assert ids == ["b2"]
    assert payload["attempts"][0]["outcome"] == "creation_failed"
    assert payload["attempts"][1]["outcome"] == "completed"
    stream.assert_called_once()
