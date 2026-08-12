import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.run_pata_jazz_live import _ingestion_url, create_live, stream_video


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

    stream_video(video, "rtmp://a.example/live/key", 0)

    command = run.call_args.args[0]
    assert "-stream_loop" in command
    assert "-t" not in command
    assert run.call_args.kwargs["timeout"] is None


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
