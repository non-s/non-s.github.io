import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.run_pata_jazz_live import (
    _ingestion_url,
    create_live,
    find_reusable_live,
    get_or_create_live,
    stream_video,
)


def test_builds_rtmp_url_from_youtube_stream() -> None:
    stream = {"cdn": {"ingestionInfo": {"ingestionAddress": "rtmp://a.example/live/", "streamName": "key"}}}
    assert _ingestion_url(stream) == "rtmp://a.example/live/key"


def test_continuous_live_disables_auto_stop() -> None:
    service = MagicMock()
    service.liveBroadcasts.return_value.insert.return_value.execute.return_value = {"id": "broadcast"}
    service.liveStreams.return_value.insert.return_value.execute.return_value = {
        "id": "stream",
        "cdn": {"ingestionInfo": {"ingestionAddress": "rtmp://a.example/live", "streamName": "key"}},
    }

    create_live(service, title="Pata Jazz", privacy="public", continuous=True)

    body = service.liveBroadcasts.return_value.insert.call_args.kwargs["body"]
    assert body["contentDetails"]["enableAutoStop"] is False


@patch("scripts.run_pata_jazz_live.subprocess.run")
def test_continuous_stream_has_no_time_limit(run: MagicMock, tmp_path) -> None:
    video = tmp_path / "loop.mp4"
    video.touch()

    stream_video(video, "rtmp://a.example/live/key", 0, max_restarts=0)

    command = run.call_args.args[0]
    assert "-stream_loop" in command
    assert "-t" not in command
    assert run.call_args.kwargs["timeout"] is None


@patch("scripts.run_pata_jazz_live.time.sleep")
@patch("scripts.run_pata_jazz_live.subprocess.run")
def test_continuous_stream_restarts_after_ffmpeg_failure(run: MagicMock, sleep: MagicMock, tmp_path) -> None:
    video = tmp_path / "loop.mp4"
    video.touch()
    run.side_effect = [subprocess.CalledProcessError(1, ["ffmpeg"]), None]

    stream_video(video, "rtmp://a.example/live/key", 0, restart_delay_seconds=7, max_restarts=1)

    assert run.call_count == 2
    sleep.assert_called_once_with(7)


def test_finds_and_reuses_matching_live() -> None:
    service = MagicMock()
    service.liveBroadcasts.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "broadcast",
                "snippet": {"title": "Pata Jazz"},
                "status": {"privacyStatus": "unlisted", "lifeCycleStatus": "live"},
                "contentDetails": {"boundStreamId": "stream"},
            }
        ]
    }
    service.liveStreams.return_value.list.return_value.execute.return_value = {
        "items": [
            {"cdn": {"ingestionInfo": {"ingestionAddress": "rtmp://a.example/live", "streamName": "key"}}}
        ]
    }

    assert find_reusable_live(service, title="Pata Jazz", privacy="unlisted") == (
        "broadcast",
        "rtmp://a.example/live/key",
    )
    list_args = service.liveBroadcasts.return_value.list.call_args.kwargs
    assert list_args["mine"] is True
    assert "broadcastStatus" not in list_args


@patch("scripts.run_pata_jazz_live.create_live")
@patch("scripts.run_pata_jazz_live.find_reusable_live", return_value=("existing", "rtmp://existing"))
def test_continuous_mode_prefers_existing_live(find: MagicMock, create: MagicMock) -> None:
    service = MagicMock()

    result = get_or_create_live(service, title="Pata Jazz", privacy="unlisted", continuous=True)

    assert result == ("existing", "rtmp://existing")
    find.assert_called_once_with(service, title="Pata Jazz", privacy="unlisted")
    create.assert_not_called()


def test_script_dry_run_matches_workflow_invocation() -> None:
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_pata_jazz_live.py",
            "--video",
            "_videos/live-placeholder.mp4",
            "--duration-minutes",
            "0",
            "--privacy",
            "unlisted",
            "--dry-run",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
