"""Testes para utils/live_chat.py (chat ao vivo do YouTube + cronometro)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils import live_chat
from utils.live_chat import (
    LiveChatWatcher,
    discover_chat_id,
    fetch_chat_messages,
    start_uptime_writer,
    stop_uptime_writer,
    write_uptime,
)


class TestFetchChatMessages:
    def test_returns_items_and_next_page_token(self):
        service = MagicMock()
        service.liveChatMessages().list().execute.return_value = {
            "items": [{"id": "m1"}, {"id": "m2"}],
            "nextPageToken": "token-abc",
        }

        items, next_token = fetch_chat_messages(service, "chat123")

        assert items == [{"id": "m1"}, {"id": "m2"}]
        assert next_token == "token-abc"
        _, kwargs = service.liveChatMessages().list.call_args
        assert kwargs["liveChatId"] == "chat123"
        assert kwargs["part"] == "snippet,authorDetails"

    def test_uses_page_token_when_provided(self):
        service = MagicMock()
        service.liveChatMessages().list().execute.return_value = {
            "items": [],
            "nextPageToken": "next",
        }

        _, next_token = fetch_chat_messages(service, "chat123", page_token="prev")

        _, kwargs = service.liveChatMessages().list.call_args
        assert kwargs["pageToken"] == "prev"
        assert next_token == "next"

    def test_empty_response_returns_empty_list_and_empty_token(self):
        service = MagicMock()
        service.liveChatMessages().list().execute.return_value = {}

        items, next_token = fetch_chat_messages(service, "chat123")

        assert items == []
        assert next_token == ""

    def test_missing_next_page_token_defaults_to_empty(self):
        service = MagicMock()
        service.liveChatMessages().list().execute.return_value = {"items": [{"id": "m1"}]}

        _, next_token = fetch_chat_messages(service, "chat123")

        assert next_token == ""


class TestParseCommand:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("!scene sleepy cat", ("scene", "sleepy cat")),
            ("!SCENE Sleepy Cat", ("scene", "Sleepy Cat")),
            ("!uptime", ("uptime", "")),
            ("!song", ("song", "")),
            ("!help", ("help", "")),
            ("  !uptime  ", ("uptime", "")),
            ("hello world", None),
            ("!", None),
            ("!scene    sleepy   cat", ("scene", "sleepy   cat")),
        ],
    )
    def test_parse_cases(self, text, expected):
        watcher = LiveChatWatcher.__new__(LiveChatWatcher)
        assert watcher.parse_command(text) == expected


class TestHandleCommand:
    def _make_watcher(self, tmp_path: Path, start_time: float = 0.0) -> LiveChatWatcher:
        return LiveChatWatcher(
            service=MagicMock(),
            chat_id="chat123",
            start_time=start_time,
            meta_dir=tmp_path,
        )

    def test_help_returns_known_commands(self, tmp_path):
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("help", "")
        assert reply is not None
        assert "!scene" in reply
        assert "!uptime" in reply
        assert "!song" in reply
        assert "!request" in reply
        assert "!stats" in reply
        assert "!next" in reply

    def test_uptime_formats_since_start(self, tmp_path):
        watcher = self._make_watcher(tmp_path, start_time=time.time() - 8015)  # 2h13m35s
        with patch("utils.live_chat.time.time", return_value=time.time()):
            # Usa o start_time real; resultado deve ter formato HH:MM:SS.
            reply = watcher.handle_command("uptime", "")
        assert reply is not None
        assert reply.startswith("Uptime: ")
        # "Uptime: HH:MM:SS" -> apos o primeiro ':', deve haver exatamente 2.
        assert reply.split(":", 1)[1].count(":") == 2

    def test_unknown_command_returns_none(self, tmp_path):
        watcher = self._make_watcher(tmp_path)
        assert watcher.handle_command("banana", "") is None

    def test_scene_without_argument_returns_usage(self, tmp_path):
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("scene", "")
        assert "Uso" in reply
        assert not (tmp_path / "live_next_scene.json").exists()

    def test_scene_invalid_returns_message_and_does_not_write(self, tmp_path):
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("scene", "dragon")
        assert "desconhecida" in reply.lower() or "invalida" in reply.lower()
        assert not (tmp_path / "live_next_scene.json").exists()

    def test_scene_valid_writes_next_scene_json(self, tmp_path):
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("scene", "sleepy cat")

        assert "sleepy cat" in reply
        next_scene_path = tmp_path / "live_next_scene.json"
        assert next_scene_path.exists()
        data = json.loads(next_scene_path.read_text(encoding="utf-8"))
        assert data["scene"] == "sleepy cat"
        assert "requested_at" in data

    def test_song_returns_track_from_metadata_file(self, tmp_path):
        (tmp_path / "live_current_track.json").write_text(
            json.dumps({"title": "Blue in Green", "artist": "Miles Davis"}),
            encoding="utf-8",
        )
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("song", "")
        assert "Miles Davis" in reply
        assert "Blue in Green" in reply

    def test_song_returns_default_when_no_track_file(self, tmp_path):
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("song", "")
        assert reply is not None
        assert "nao" in reply.lower() or "nao sei" in reply.lower()

    def test_song_handles_corrupted_track_file(self, tmp_path):
        (tmp_path / "live_current_track.json").write_text("not json", encoding="utf-8")
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("song", "")
        assert reply is not None


class TestRequestCommand:
    def _make_watcher(self, tmp_path: Path, start_time: float = 0.0) -> LiveChatWatcher:
        return LiveChatWatcher(
            service=MagicMock(),
            chat_id="chat123",
            start_time=start_time,
            meta_dir=tmp_path,
        )

    def test_request_without_argument_returns_usage(self, tmp_path):
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("request", "", author="viewer1")
        assert "Uso" in reply
        assert not (tmp_path / "live_scene_requests.json").exists()

    def test_request_invalid_returns_message_and_does_not_write(self, tmp_path):
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("request", "dragon", author="viewer1")
        assert "desconhecida" in reply.lower() or "invalida" in reply.lower()
        assert not (tmp_path / "live_scene_requests.json").exists()

    def test_request_valid_writes_scene_requests_json(self, tmp_path):
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("request", "sleepy cat", author="viewer1")

        assert "Pedido registrado" in reply
        assert "sleepy cat" in reply
        path = tmp_path / "live_scene_requests.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["scene"] == "sleepy cat"
        assert data[0]["requested_by"] == "viewer1"
        assert "requested_at" in data[0]

    def test_request_appends_to_existing_requests(self, tmp_path):
        path = tmp_path / "live_scene_requests.json"
        path.write_text(json.dumps([{
            "scene": "cat", "requested_by": "other", "requested_at": "2026-01-01"
        }]), encoding="utf-8")
        watcher = self._make_watcher(tmp_path)
        watcher.handle_command("request", "dog", author="viewer2")

        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) == 2
        assert data[1]["scene"] == "dog"
        assert data[1]["requested_by"] == "viewer2"

    def test_request_preserves_case_in_argument(self, tmp_path):
        """Comando deve lowercasing na cena (cenas sao lowercased no
        consumidor), mas preservar o author."""
        watcher = self._make_watcher(tmp_path)
        watcher.handle_command("request", "Sleepy Cat", author="Viewer1")
        data = json.loads((tmp_path / "live_scene_requests.json").read_text(encoding="utf-8"))
        assert data[0]["scene"] == "sleepy cat"
        assert data[0]["requested_by"] == "Viewer1"


class TestStatsCommand:
    def _make_watcher(self, tmp_path: Path) -> LiveChatWatcher:
        return LiveChatWatcher(
            service=MagicMock(), chat_id="chat123", start_time=0.0, meta_dir=tmp_path,
        )

    def test_stats_returns_total_views_from_analytics(self, tmp_path):
        (tmp_path / "analytics.json").write_text(
            json.dumps({"total_views": 12345}), encoding="utf-8"
        )
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("stats", "")
        assert reply == "Channel views: 12345"

    def test_stats_returns_unavailable_when_no_analytics(self, tmp_path):
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("stats", "")
        assert "indisponivel" in reply.lower()

    def test_stats_handles_corrupted_analytics(self, tmp_path):
        (tmp_path / "analytics.json").write_text("not json", encoding="utf-8")
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("stats", "")
        assert "indisponivel" in reply.lower()

    def test_stats_handles_missing_total_views(self, tmp_path):
        (tmp_path / "analytics.json").write_text(json.dumps({}), encoding="utf-8")
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("stats", "")
        assert reply == "Channel views: 0"


class TestNextCommand:
    def _make_watcher(self, tmp_path: Path) -> LiveChatWatcher:
        return LiveChatWatcher(
            service=MagicMock(), chat_id="chat123", start_time=0.0, meta_dir=tmp_path,
        )

    def test_next_returns_unknown_when_no_file(self, tmp_path):
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("next", "")
        assert reply == "Next clip: Unknown"

    def test_next_returns_scene_and_hook_when_present(self, tmp_path):
        (tmp_path / "live_next_clip.json").write_text(
            json.dumps({"scene": "sleepy cat", "hook": "Cozy Nap Time"}), encoding="utf-8"
        )
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("next", "")
        assert "Cozy Nap Time" in reply
        assert "sleepy cat" in reply

    def test_next_returns_scene_only_when_no_hook(self, tmp_path):
        (tmp_path / "live_next_clip.json").write_text(
            json.dumps({"scene": "sleepy cat"}), encoding="utf-8"
        )
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("next", "")
        assert reply == "Next clip: sleepy cat"

    def test_next_handles_corrupted_file(self, tmp_path):
        (tmp_path / "live_next_clip.json").write_text("not json", encoding="utf-8")
        watcher = self._make_watcher(tmp_path)
        reply = watcher.handle_command("next", "")
        assert reply == "Next clip: Unknown"


class TestOverlayAndHistory:
    def test_write_overlay_creates_file_and_history(self, tmp_path):
        watcher = LiveChatWatcher(
            service=MagicMock(), chat_id="c", start_time=0.0, meta_dir=tmp_path
        )
        watcher._write_overlay("Uptime: 00:00:05")

        assert (tmp_path / "live_chat_overlay.txt").read_text(encoding="utf-8") == "Uptime: 00:00:05"
        history = json.loads((tmp_path / "live_chat_replies.json").read_text(encoding="utf-8"))
        assert history[-1]["reply"] == "Uptime: 00:00:05"

    def test_maybe_clear_overlay_removes_after_ttl(self, tmp_path):
        watcher = LiveChatWatcher(
            service=MagicMock(), chat_id="c", start_time=0.0, meta_dir=tmp_path,
            poll_interval=999,
        )
        watcher._write_overlay("hello")
        # Simula passagem do TTL: força clear_at para o passado.
        watcher._overlay_clear_at = time.time() - 1
        watcher._maybe_clear_overlay()

        assert not (tmp_path / "live_chat_overlay.txt").exists()

    def test_stop_removes_overlay_file(self, tmp_path):
        watcher = LiveChatWatcher(
            service=MagicMock(), chat_id="c", start_time=0.0, meta_dir=tmp_path,
            poll_interval=999,
        )
        watcher._write_overlay("hi")
        watcher.stop(timeout=1.0)

        assert not (tmp_path / "live_chat_overlay.txt").exists()


class TestWatcherThread:
    def test_start_stop_clean(self, tmp_path):
        service = MagicMock()
        service.liveChatMessages().list().execute.return_value = {"items": []}
        watcher = LiveChatWatcher(
            service=service, chat_id="chat123", start_time=time.time(),
            meta_dir=tmp_path, poll_interval=0.05,
        )
        watcher.start()
        assert watcher._thread is not None
        assert watcher._thread.is_alive()

        watcher.stop(timeout=2.0)
        assert watcher._thread is None or not watcher._thread.is_alive()

    def test_double_start_does_not_spawn_second_thread(self, tmp_path):
        service = MagicMock()
        service.liveChatMessages().list().execute.return_value = {"items": []}
        watcher = LiveChatWatcher(
            service=service, chat_id="chat123", start_time=time.time(),
            meta_dir=tmp_path, poll_interval=0.05,
        )
        watcher.start()
        first = watcher._thread
        watcher.start()
        assert watcher._thread is first
        watcher.stop(timeout=2.0)

    def test_poll_processes_command_and_writes_overlay(self, tmp_path):
        service = MagicMock()
        service.liveChatMessages().list().execute.return_value = {
            "items": [
                {
                    "snippet": {"textMessageDetails": {"messageText": "!help"}},
                    "authorDetails": {"displayName": "viewer1"},
                }
            ],
            "nextPageToken": "t1",
        }
        watcher = LiveChatWatcher(
            service=service, chat_id="chat123", start_time=time.time(),
            meta_dir=tmp_path, poll_interval=999,
        )
        watcher._poll_once()

        overlay = (tmp_path / "live_chat_overlay.txt").read_text(encoding="utf-8")
        assert "!scene" in overlay


class TestDiscoverChatId:
    def test_returns_live_chat_id(self):
        service = MagicMock()
        service.liveBroadcasts().list().execute.return_value = {
            "items": [{"snippet": {"liveChatId": "Cg0KCxxxx"}}]
        }
        assert discover_chat_id(service, "bcast123") == "Cg0KCxxxx"

    def test_returns_none_when_no_items(self):
        service = MagicMock()
        service.liveBroadcasts().list().execute.return_value = {"items": []}
        assert discover_chat_id(service, "bcast123") is None

    def test_returns_none_when_missing_live_chat_id(self):
        service = MagicMock()
        service.liveBroadcasts().list().execute.return_value = {
            "items": [{"snippet": {}}]
        }
        assert discover_chat_id(service, "bcast123") is None

    def test_returns_none_on_exception(self):
        service = MagicMock()
        service.liveBroadcasts().list().execute.side_effect = RuntimeError("api down")
        assert discover_chat_id(service, "bcast123") is None


class TestLiveChatWatcherLoad:
    """Teste de carga: simula 1000 mensagens chegando em 60s (10 chamadas de
    100 msgs cada) e verifica que o watcher processa todas rapidamente (nao
    trava) e que o historico de respostas tem cap (nao cresce indefinidamente)."""

    def _make_watcher(self, tmp_path: Path) -> LiveChatWatcher:
        return LiveChatWatcher(
            service=MagicMock(), chat_id="chat123", start_time=0.0, meta_dir=tmp_path,
            poll_interval=999,
        )

    def test_processes_1000_messages_under_2s(self, tmp_path):
        from utils import live_chat as lc

        watcher = self._make_watcher(tmp_path)

        messages_per_call = 100
        calls = 10
        total = messages_per_call * calls
        call_index = {"i": 0}

        def _fake_items(_service, _chat_id, _page_token=""):
            i = call_index["i"]
            call_index["i"] += 1
            items = [
                {
                    "snippet": {"textMessageDetails": {"messageText": f"hello {i * messages_per_call + j}"}},
                    "authorDetails": {"displayName": f"viewer{j}"},
                }
                for j in range(messages_per_call)
            ]
            return items, "tok" if i < calls - 1 else ""

        start = time.time()
        with patch.object(lc, "fetch_chat_messages", side_effect=_fake_items):
            for _ in range(calls):
                watcher._poll_once()
        elapsed = time.time() - start

        assert call_index["i"] == calls
        assert elapsed < 2.0, f"watcher demorou {elapsed:.2f}s para processar {total} mensagens"
        assert watcher._page_token == ""

    def test_reply_history_has_cap(self, tmp_path):
        from utils import live_chat as lc

        watcher = self._make_watcher(tmp_path)
        cap = lc._MAX_REPLY_HISTORY
        # Simula mais respostas que o cap: o historico precisa parar de crescer.
        for i in range(cap * 3):
            watcher._append_reply_history(f"reply {i}")
        history = json.loads((tmp_path / "live_chat_replies.json").read_text(encoding="utf-8"))
        assert len(history) <= cap, f"historico cresceu alem do cap {cap}: {len(history)}"
        assert len(history) == cap

    def test_simulated_60s_via_mocked_time(self, tmp_path):
        from utils import live_chat as lc

        watcher = self._make_watcher(tmp_path)
        messages_per_call = 100
        calls = 10
        call_index = {"i": 0}
        fake_now = [0.0]

        def _fake_items(_service, _chat_id, _page_token=""):
            i = call_index["i"]
            call_index["i"] += 1
            fake_now[0] += 6.0  # 60s em 10 chamadas
            return [
                {
                    "snippet": {"textMessageDetails": {"messageText": "!uptime"}},
                    "authorDetails": {"displayName": "viewer"},
                }
                for _ in range(messages_per_call)
            ], ""

        with patch.object(lc, "fetch_chat_messages", side_effect=_fake_items), \
             patch.object(lc.time, "time", side_effect=lambda: fake_now[0]):
            for _ in range(calls):
                watcher._poll_once()

        assert call_index["i"] == calls
        assert fake_now[0] == 60.0


class TestUptimeWriter:
    def test_write_uptime_creates_file_with_live_prefix(self, tmp_path):
        path = tmp_path / "live_uptime.txt"
        write_uptime(time.time() - 65, path=path)
        text = path.read_text(encoding="utf-8")
        assert text.startswith("\U0001f534 LIVE ")
        assert text.count(":") == 2

    def test_start_stop_uptime_writer(self, tmp_path, monkeypatch):
        monkeypatch.setattr(live_chat, "data_dir", lambda: tmp_path)
        thread = start_uptime_writer(time.time())
        assert thread.is_alive()
        # Espera o loop escrever pelo menos uma vez.
        time.sleep(0.1)
        stop_uptime_writer(thread)
        assert not thread.is_alive()
        assert (tmp_path / "live_uptime.txt").exists()
