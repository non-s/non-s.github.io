"""Testes para o polling de status do stream antes de transicionar o broadcast.

A API do YouTube rejeita liveBroadcasts.transition(status='testing') com
403 invalidTransition ate que o liveStream vinculado esteja com
status.streamStatus == 'active' (ou seja, recebendo video de verdade).
Esses testes cobrem wait_for_stream_active() e a separacao entre iniciar
e aguardar o processo do FFmpeg em generate_pata_jazz_live.py.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import generate_pata_jazz_live as live
import live_broadcast


def _fake_popen(*_args, **_kwargs):
    proc = MagicMock()
    proc.poll.side_effect = [None, 0]
    proc.communicate.return_value = ("", "")
    proc.returncode = 0
    return proc


class TestWaitForStreamActive:
    @patch("live_broadcast.time.sleep", return_value=None)
    @patch("live_broadcast.get_youtube_service")
    def test_returns_true_once_stream_becomes_active(self, mock_service, _mock_sleep):
        service = MagicMock()
        mock_service.return_value = service
        responses = [
            {"items": [{"status": {"streamStatus": "ready"}}]},
            {"items": [{"status": {"streamStatus": "active"}}]},
        ]
        service.liveStreams.return_value.list.return_value.execute.side_effect = responses

        assert live_broadcast.wait_for_stream_active("stream123", timeout=10, interval=0) is True

    @patch("live_broadcast.time.sleep", return_value=None)
    @patch("live_broadcast.time.time")
    @patch("live_broadcast.get_youtube_service")
    def test_times_out_if_never_active(self, mock_service, mock_time, _mock_sleep):
        service = MagicMock()
        mock_service.return_value = service
        service.liveStreams.return_value.list.return_value.execute.return_value = {
            "items": [{"status": {"streamStatus": "ready"}}]
        }
        # time.time retorna t0 para o deadline, depois t0 (entra no loop),
        # t0+100 (sai do loop) - sem depender de relogio real.
        mock_time.side_effect = [0.0, 0.0, 100.0]

        assert live_broadcast.wait_for_stream_active("stream123", timeout=10, interval=0) is False


class TestFfmpegStreamStartWaitSplit:
    @patch("generate_pata_jazz_live.time.sleep", return_value=None)
    @patch("generate_pata_jazz_live.subprocess.Popen")
    def test_start_then_wait_matches_combined_helper(self, mock_popen, _mock_sleep):
        mock_popen.side_effect = _fake_popen
        proc = live._start_ffmpeg_stream(Path("loop.mp4"), "rtmp://example/live2/key", duration_minutes=0)
        code = live._wait_ffmpeg_stream(proc)
        assert code == 0
        mock_popen.assert_called_once()
