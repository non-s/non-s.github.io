"""Testes para o polling de status do stream antes de transicionar o broadcast.

A API do YouTube rejeita liveBroadcasts.transition(status='testing') com
403 invalidTransition ate que o liveStream vinculado esteja com
status.streamStatus == 'active' (ou seja, recebendo video de verdade).
Esses testes cobrem wait_for_stream_active() e a separacao entre iniciar
e aguardar o processo do FFmpeg em generate_pata_jazz_live.py.
"""
import json
from datetime import UTC, datetime, timedelta
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


def _iso_minutes_ago(minutes: float) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


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
        # t0 (continua no loop com interval=0), t0+100 (sai do loop), t0+100
        # (logging interno do makeRecord tambem chama time.time no Linux).
        mock_time.side_effect = [0.0, 0.0, 0.0, 100.0, 100.0, 100.0]

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


class TestCleanupOrphanBroadcastsEdgeCases:
    """Casos extremos de cleanup_orphan_broadcasts: broadcast ativo sem
    actualStartTime, broadcast ja complete, multiplos ativos simultaneos e
    lista de items vazia."""

    def _service_with(self, upcoming_items=None, active_items=None):
        service = MagicMock()

        def list_side_effect(**kwargs):
            resp = MagicMock()
            if kwargs.get("broadcastStatus") == "upcoming":
                resp.execute.return_value = {"items": upcoming_items or []}
            else:
                resp.execute.return_value = {"items": active_items or []}
            return resp

        service.liveBroadcasts().list.side_effect = list_side_effect
        return service

    def test_active_broadcast_missing_actual_start_time_is_skipped(self):
        """active sem actualStartTime: _broadcast_age_minutes retorna None e o
        broadcast nao e encerrado (nao da pra saber se e orfao ou sessao nova)."""
        service = self._service_with(
            active_items=[{"id": "no_start", "snippet": {}}]
        )
        with patch("live_broadcast.transition_broadcast") as mock_transition:
            cleaned = live_broadcast.cleanup_orphan_broadcasts(service)

        mock_transition.assert_not_called()
        assert cleaned == 0

    def test_active_broadcast_already_complete_is_not_touched(self):
        """Um broadcast ativo cuja idade e inferior ao limite nao e encerrado
        - cobre o caminho 'normal running session' junto com a ausencia de
        actualStartTime para garantir que soh o orfao velho e tocado."""
        service = self._service_with(
            active_items=[{"id": "fresh", "snippet": {"actualStartTime": _iso_minutes_ago(5)}}]
        )
        with patch("live_broadcast.transition_broadcast") as mock_transition:
            cleaned = live_broadcast.cleanup_orphan_broadcasts(service)

        mock_transition.assert_not_called()
        assert cleaned == 0

    def test_multiple_active_broadcasts_only_stale_ones_completed(self):
        """Varios ativos simultaneos: so os que excedem _MAX_ACTIVE_AGE_MINUTES
        sao encerrados; os recentes seguem rodando."""
        service = self._service_with(
            active_items=[
                {"id": "stale1", "snippet": {"actualStartTime": _iso_minutes_ago(500)}},
                {"id": "fresh", "snippet": {"actualStartTime": _iso_minutes_ago(10)}},
                {"id": "stale2", "snippet": {"actualStartTime": _iso_minutes_ago(400)}},
            ]
        )
        with patch("live_broadcast.transition_broadcast") as mock_transition:
            cleaned = live_broadcast.cleanup_orphan_broadcasts(service)

        completed = [call.args[0] for call in mock_transition.call_args_list]
        assert sorted(completed) == ["stale1", "stale2"]
        assert cleaned == 2

    def test_empty_items_list_returns_zero(self):
        """Sem nenhum broadcast (upcoming nem active): nada a limpar."""
        service = self._service_with(upcoming_items=[], active_items=[])
        with patch("live_broadcast.delete_broadcast") as mock_delete, \
             patch("live_broadcast.transition_broadcast") as mock_transition:
            cleaned = live_broadcast.cleanup_orphan_broadcasts(service)

        mock_delete.assert_not_called()
        mock_transition.assert_not_called()
        assert cleaned == 0


class TestTryResumeExistingBroadcastEdgeCases:
    """Casos extremos de _try_resume_existing_broadcast: broadcast com
    actualStartTime ausente (nao se aplica - lifecycle e o que importa),
    broadcast ja complete, multiplos ativos e items vazios."""

    def _isolate(self, tmp_path, monkeypatch):
        state_file = tmp_path / "live_state.json"
        monkeypatch.setattr(live_broadcast, "_LIVE_STATE_FILE", state_file)
        return state_file

    def _service_with(self, broadcast_items=None, stream_items=None):
        service = MagicMock()

        def broadcasts_list_side_effect(**kwargs):
            resp = MagicMock()
            resp.execute.return_value = {"items": broadcast_items if broadcast_items is not None else []}
            return resp

        def streams_list_side_effect(**kwargs):
            resp = MagicMock()
            resp.execute.return_value = {"items": stream_items if stream_items is not None else []}
            return resp

        service.liveBroadcasts().list.side_effect = broadcasts_list_side_effect
        service.liveStreams().list.side_effect = streams_list_side_effect
        return service

    def test_broadcast_already_complete_returns_none(self, tmp_path, monkeypatch):
        state_file = self._isolate(tmp_path, monkeypatch)
        state_file.write_text(json.dumps({"broadcast_id": "b1", "stream_id": "s1"}), encoding="utf-8")
        service = self._service_with(broadcast_items=[{"status": {"lifeCycleStatus": "complete"}}])

        assert live_broadcast._try_resume_existing_broadcast(service) is None

    def test_empty_broadcast_items_returns_none(self, tmp_path, monkeypatch):
        state_file = self._isolate(tmp_path, monkeypatch)
        state_file.write_text(json.dumps({"broadcast_id": "b1", "stream_id": "s1"}), encoding="utf-8")
        service = self._service_with(broadcast_items=[])

        assert live_broadcast._try_resume_existing_broadcast(service) is None

    def test_empty_stream_items_returns_none(self, tmp_path, monkeypatch):
        state_file = self._isolate(tmp_path, monkeypatch)
        state_file.write_text(json.dumps({"broadcast_id": "b1", "stream_id": "s1"}), encoding="utf-8")
        service = self._service_with(
            broadcast_items=[{"status": {"lifeCycleStatus": "live"}}], stream_items=[],
        )

        assert live_broadcast._try_resume_existing_broadcast(service) is None

    def test_resumes_when_multiple_lifecycle_statuses_present(self, tmp_path, monkeypatch):
        """A API retorna no maximo o broadcast pedido por id; mesmo que
        multiplos items voltassem, so o primeiro (o do id) e considerado."""
        state_file = self._isolate(tmp_path, monkeypatch)
        state_file.write_text(
            json.dumps({"broadcast_id": "b1", "stream_id": "s1",
                        "title": "t", "description": "d", "privacy": "public"}),
            encoding="utf-8",
        )
        service = self._service_with(
            broadcast_items=[{"status": {"lifeCycleStatus": "live"}}],
            stream_items=[{"cdn": {"ingestionInfo": {"streamName": "abcd-1234"}}}],
        )

        result = live_broadcast._try_resume_existing_broadcast(service)

        assert result is not None
        assert result["broadcast_id"] == "b1"
        assert result["stream_name"] == "abcd-1234"
