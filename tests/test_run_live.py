"""Testes para scripts/run_live.py.

Com enableMonitorStream=False e enableAutoStart=True, a API do YouTube
rejeita qualquer chamada manual a liveBroadcasts.transition para 'testing'
(403 invalidTransition) independente da ordem - so existe fase de testing
quando o monitor stream esta habilitado. Por isso run_live.py nao chama
transition('testing') nem transition('live'): apenas confirma que o stream
ficou ativo (wait_for_stream_active) e deixa o YouTube promover o broadcast
sozinho. So a transicao final para 'complete' e manual.

Se o FFmpeg cair antes da duracao total pedida (Broken pipe por
instabilidade de rede/CPU no runner gratuito), main() reconecta
automaticamente ao mesmo broadcast/stream em vez de encerrar a live.
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
    def test_does_not_transition_to_testing_only_complete_at_end(
        self, mock_create, mock_try_transition, mock_loop, mock_save,
        mock_start_ffmpeg, mock_wait_active, mock_wait_ffmpeg,
        mock_notify_start, mock_notify_end,
    ):
        code = run_live.main()

        assert code == 0
        mock_wait_active.assert_called_once_with("stream123", timeout=120)
        # Nenhuma transicao manual para 'testing' (sempre invalida nessa config);
        # so a transicao final para 'complete'.
        statuses = [call.args[1] for call in mock_try_transition.call_args_list]
        assert "testing" not in statuses
        assert statuses == ["complete"]

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
        assert "testing" not in statuses
        assert "complete" in statuses

    @patch("scripts.run_live.notify_live_end")
    @patch("scripts.run_live.notify_live_start")
    @patch("scripts.run_live._try_transition")
    @patch("scripts.run_live.wait_for_stream_active", return_value=True)
    @patch("scripts.run_live._start_ffmpeg_stream", return_value=MagicMock())
    @patch("scripts.run_live._save_live_meta")
    @patch("scripts.run_live._build_looping_input", return_value=(Path("loop.mp4"), Path("playlist.txt")))
    @patch("scripts.run_live.create_live_stream", return_value=_base_meta())
    @patch("scripts.run_live.time")
    def test_reconnects_after_unexpected_ffmpeg_exit(
        self, mock_time, mock_create, mock_loop, mock_save,
        mock_start_ffmpeg, mock_wait_active, mock_try_transition,
        mock_notify_start, mock_notify_end,
    ):
        """FFmpeg cai com codigo de erro antes da duracao total: reconecta em
        vez de desistir da live inteira."""
        # time.time(): start_time, depois duas leituras por iteracao do loop
        # (checagem de elapsed no topo + log no finally). Damos valores
        # crescentes o suficiente para permitir 1 reconexao e depois concluir.
        mock_time.time.side_effect = [0, 10, 10, 700, 700, 700]
        mock_time.sleep = MagicMock()

        with patch(
            "scripts.run_live._wait_ffmpeg_stream", side_effect=[1, 0]
        ) as mock_wait_ffmpeg:
            code = run_live.main()

        assert code == 0
        assert mock_wait_ffmpeg.call_count == 2
        assert mock_start_ffmpeg.call_count == 2
        mock_notify_start.assert_called_once()  # so notifica inicio uma vez
        mock_time.sleep.assert_called_with(run_live._RECONNECT_DELAY_SECONDS)
