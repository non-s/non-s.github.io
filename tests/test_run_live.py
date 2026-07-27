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
    @patch("scripts.run_live._wait_ffmpeg_stream", return_value=0)
    @patch("scripts.run_live.wait_for_stream_active", return_value=True)
    @patch("scripts.run_live._start_ffmpeg_stream", return_value=MagicMock())
    @patch("scripts.run_live._save_live_meta")
    @patch("scripts.run_live._build_looping_input", return_value=(Path("loop.mp4"), Path("playlist.txt")))
    @patch("scripts.run_live._try_transition")
    @patch("scripts.run_live.create_live_stream", return_value=_base_meta())
    @patch("scripts.run_live._register_signal_handlers")
    def test_does_not_transition_to_testing_only_complete_at_end(
        self, mock_register_signals, mock_create, mock_try_transition, mock_loop, mock_save,
        mock_start_ffmpeg, mock_wait_active, mock_wait_ffmpeg,
    ):
        code = run_live.main()

        assert code == 0
        mock_register_signals.assert_called_once()
        mock_wait_active.assert_called_once_with("stream123", timeout=120)
        # Nenhuma transicao manual para 'testing' (sempre invalida nessa config);
        # so a transicao final para 'complete'.
        statuses = [call.args[1] for call in mock_try_transition.call_args_list]
        assert "testing" not in statuses
        assert statuses == ["complete"]

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
    ):
        code = run_live.main()

        assert code == 1
        mock_terminate.assert_called_once()
        statuses = [call.args[1] for call in mock_try_transition.call_args_list]
        assert "testing" not in statuses
        assert "complete" in statuses

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
    ):
        """FFmpeg cai com codigo de erro antes da duracao total: reconecta em
        vez de desistir da live inteira."""
        # time.time(): start_time, depois por iteracao do loop: elapsed (topo),
        # segment_start, segment_seconds, e (se reconectar) elapsed_min do log.
        # Damos valores crescentes com segmentos >=15s (nao conta como falha
        # rapida) o suficiente para 1 reconexao e depois concluir.
        mock_time.time.side_effect = [0, 5, 5, 25, 25, 30, 30, 700, 700, 700]
        mock_time.sleep = MagicMock()

        with patch(
            "scripts.run_live._wait_ffmpeg_stream", side_effect=[1, 0]
        ) as mock_wait_ffmpeg:
            code = run_live.main()

        assert code == 0
        assert mock_wait_ffmpeg.call_count == 2
        assert mock_start_ffmpeg.call_count == 2
        mock_time.sleep.assert_called_with(run_live._RECONNECT_DELAY_SECONDS)


class TestEndBroadcast:
    """_end_broadcast: fallback de limpeza para nao deixar broadcast orfao.

    transition('complete') so e valido a partir de 'testing'/'live'. Se o
    stream nunca ficou ativo e a transicao falha, o broadcast provavelmente
    ainda esta em 'ready' - apagar evita deixa-lo preso no canal. Mas se o
    stream JA ficou ativo (foi ao vivo de verdade), nao faz sentido apagar
    so porque a transicao final falhou por algum motivo transiente.
    """

    @patch("scripts.run_live.delete_broadcast")
    @patch("scripts.run_live._try_transition", return_value=True)
    def test_no_fallback_when_transition_succeeds(self, mock_try_transition, mock_delete):
        run_live._end_broadcast("bcast123", went_active=False)
        mock_delete.assert_not_called()

    @patch("scripts.run_live.delete_broadcast")
    @patch("scripts.run_live._try_transition", return_value=False)
    def test_falls_back_to_delete_when_never_active(self, mock_try_transition, mock_delete):
        run_live._end_broadcast("bcast123", went_active=False)
        mock_delete.assert_called_once_with("bcast123")

    @patch("scripts.run_live.delete_broadcast")
    @patch("scripts.run_live._try_transition", return_value=False)
    def test_does_not_delete_a_broadcast_that_went_live(self, mock_try_transition, mock_delete):
        run_live._end_broadcast("bcast123", went_active=True)
        mock_delete.assert_not_called()

    @patch("scripts.run_live.delete_broadcast", side_effect=RuntimeError("api down"))
    @patch("scripts.run_live._try_transition", return_value=False)
    def test_swallows_delete_failure_too(self, mock_try_transition, mock_delete):
        """Nao deve propagar excecao mesmo se nem transicionar nem apagar
        funcionar - so loga, para nao quebrar o resto da limpeza no finally."""
        run_live._end_broadcast("bcast123", went_active=False)
        mock_delete.assert_called_once()
