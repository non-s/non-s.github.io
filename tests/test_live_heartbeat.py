"""Testes para o heartbeat de stream (task 4.4) em scripts/run_live.py.

A thread daemon chama wait_for_stream_active a cada 15min para confirmar
que o stream continua ativo no YouTube; se voltar False, seta um Event
que o loop principal checa para forcar reconexao.
"""
import threading
from unittest.mock import patch

import scripts.run_live as run_live


class TestStartStreamHeartbeat:
    def test_starts_daemon_thread(self):
        stop = threading.Event()
        with patch("scripts.run_live.wait_for_stream_active", return_value=True):
            thread = run_live._start_stream_heartbeat(
                "stream123", threading.Event(), stop_event=stop, interval_seconds=0.01
            )
        try:
            assert thread.daemon is True
            assert thread.name == "stream-heartbeat"
        finally:
            stop.set()
            thread.join(timeout=2)

    def test_calls_wait_for_stream_active_each_cycle(self):
        stop = threading.Event()
        flag = threading.Event()
        with patch("scripts.run_live.wait_for_stream_active", return_value=True) as mock_wait:
            thread = run_live._start_stream_heartbeat(
                "stream123", flag, stop_event=stop, interval_seconds=0.01
            )
            import time as _time
            _time.sleep(0.05)
            stop.set()
            thread.join(timeout=2)

        assert mock_wait.call_count >= 2
        mock_wait.assert_called_with("stream123", timeout=run_live._HEARTBEAT_STREAM_TIMEOUT)

    def test_sets_flag_when_stream_inactive(self):
        stop = threading.Event()
        flag = threading.Event()
        with patch("scripts.run_live.wait_for_stream_active", return_value=False):
            thread = run_live._start_stream_heartbeat(
                "stream123", flag, stop_event=stop, interval_seconds=0.01
            )
            import time as _time
            _time.sleep(0.05)
            stop.set()
            thread.join(timeout=2)

        assert flag.is_set() is True

    def test_does_not_set_flag_when_active(self):
        stop = threading.Event()
        flag = threading.Event()
        with patch("scripts.run_live.wait_for_stream_active", return_value=True):
            thread = run_live._start_stream_heartbeat(
                "stream123", flag, stop_event=stop, interval_seconds=0.01
            )
            import time as _time
            _time.sleep(0.05)
            stop.set()
            thread.join(timeout=2)

        assert flag.is_set() is False

    def test_exception_in_wait_does_not_set_flag(self):
        stop = threading.Event()
        flag = threading.Event()
        with patch("scripts.run_live.wait_for_stream_active", side_effect=RuntimeError("api down")):
            thread = run_live._start_stream_heartbeat(
                "stream123", flag, stop_event=stop, interval_seconds=0.01
            )
            import time as _time
            _time.sleep(0.05)
            stop.set()
            thread.join(timeout=2)

        assert flag.is_set() is False

    def test_uses_15_minute_interval_by_default(self):
        assert run_live._HEARTBEAT_INTERVAL_SECONDS == 15 * 60
        assert run_live._HEARTBEAT_STREAM_TIMEOUT == 30

    def test_stop_event_terminates_thread_gracefully(self):
        stop = threading.Event()
        with patch("scripts.run_live.wait_for_stream_active", return_value=True):
            thread = run_live._start_stream_heartbeat(
                "stream123", threading.Event(), stop_event=stop, interval_seconds=60
            )
        stop.set()
        thread.join(timeout=2)
        assert not thread.is_alive()
