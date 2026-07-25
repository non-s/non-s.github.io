"""Testes para scripts/run_live.py.

run_live.py transiciona o broadcast para 'testing' antes de iniciar o
stream (necessario para o YouTube aceitar a conexao RTMP), e transiciona
para 'complete' ao final. enableAutoStart=True promove para 'live'
sozinho quando o stream fica ativo.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import scripts.run_live as run_live


def _base_meta():
    return {
        "broadcast_id": "bcast123",
        "stream_id": "stream123",
        "stream_name": "name",
        "ingestion_url": "rtmp://a.rtmp.youtube.com/live2/key",
        "title": "Pata Jazz Live",
        "description": "desc",
        "privacy": "public",
    }


class TestRunLiveMain:
    @patch("scripts.run_live.notify_live_end")
    @patch("scripts.run_live.notify_live_start")
    @patch("scripts.run_live._wait_ffmpeg_stream", return_value=0)
    @patch("scripts.run_live.wait_for_stream_active", return_value=True)
    @patch("scripts.run_live._start_ffmpeg_stream", return_value=MagicMock())
    @patch("scripts.run_live._save_live_meta")
    @patch("scripts.run_live._build_looping_input", return_value=(Path("loop.mp4"), Path("playlist.txt")))
    @patch("scripts.run_live._try_transition")
    @patch("scripts.run_live.create_live_stream", return_value=_base_meta())
    def test_transitions_testing_before_stream_then_complete_after(
        self, mock_create, mock_try_transition, mock_loop, mock_save,
        mock_start_ffmpeg, mock_wait_active, mock_wait_ffmpeg,
        mock_notify_start, mock_notify_end,
    ):
        code = run_live.main()

        assert code == 0
        mock_wait_active.assert_called_once_with("stream123", timeout=120)
        # Transicoes: 'testing' antes do stream, 'complete' ao final.
        statuses = [call.args[1] for call in mock_try_transition.call_args_list]
        assert "testing" in statuses
        assert "complete" in statuses

    @patch("scripts.run_live.notify_live_end")
    @patch("scripts.run_live.notify_live_start")
    @patch("scripts.run_live._terminate_ffmpeg_stream")
    @patch("scripts.run_live.wait_for_stream_active", return_value=False)
    @patch("scripts.run_live._start_ffmpeg_stream", return_value=MagicMock())
    @patch("scripts.run_live._save_live_meta")
    @patch("scripts.run_live._build_looping_input", return_value=(Path("loop.mp4"), Path("playlist.txt")))
    @patch("scripts.run_live._try_transition")
    @patch("scripts.run_live.create_live_stream", return_value=_base_meta())
    def test_aborts_and_terminates_ffmpeg_if_stream_never_active(
        self, mock_create, mock_try_transition, mock_loop, mock_save,
        mock_start_ffmpeg, mock_wait_active, mock_terminate,
        mock_notify_start, mock_notify_end,
    ):
        code = run_live.main()

        assert code == 1
        mock_terminate.assert_called_once()
        mock_notify_start.assert_not_called()
        statuses = [call.args[1] for call in mock_try_transition.call_args_list]
        assert "testing" in statuses
        assert "complete" in statuses
