"""Testes para scripts/run_live.py.

create_live_stream() usa enableMonitorStream=False + enableAutoStart=True,
o que faz a API do YouTube rejeitar qualquer transicao manual para
'testing' (403 invalidTransition) e promover o broadcast para 'live'
sozinha assim que o stream fica ativo. Esses testes garantem que o
orquestrador nao tenta mais essas transicoes manuais.
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
    @patch("scripts.run_live.transition_broadcast")
    @patch("scripts.run_live.create_live_stream", return_value=_base_meta())
    def test_never_transitions_to_testing_or_live(
        self, mock_create, mock_transition, mock_loop, mock_save,
        mock_start_ffmpeg, mock_wait_active, mock_wait_ffmpeg,
        mock_notify_start, mock_notify_end,
    ):
        code = run_live.main()

        assert code == 0
        mock_wait_active.assert_called_once_with("stream123", timeout=90)
        # Unica transicao manual deve ser 'complete' (enableAutoStart cuida do 'live').
        statuses = [call.args[1] for call in mock_transition.call_args_list]
        assert statuses == ["complete"]

    @patch("scripts.run_live.notify_live_end")
    @patch("scripts.run_live.notify_live_start")
    @patch("scripts.run_live._terminate_ffmpeg_stream")
    @patch("scripts.run_live.wait_for_stream_active", return_value=False)
    @patch("scripts.run_live._start_ffmpeg_stream", return_value=MagicMock())
    @patch("scripts.run_live._save_live_meta")
    @patch("scripts.run_live._build_looping_input", return_value=(Path("loop.mp4"), Path("playlist.txt")))
    @patch("scripts.run_live.transition_broadcast")
    @patch("scripts.run_live.create_live_stream", return_value=_base_meta())
    def test_aborts_and_terminates_ffmpeg_if_stream_never_active(
        self, mock_create, mock_transition, mock_loop, mock_save,
        mock_start_ffmpeg, mock_wait_active, mock_terminate,
        mock_notify_start, mock_notify_end,
    ):
        code = run_live.main()

        assert code == 1
        mock_terminate.assert_called_once()
        mock_notify_start.assert_not_called()
        statuses = [call.args[1] for call in mock_transition.call_args_list]
        assert statuses == ["complete"]
