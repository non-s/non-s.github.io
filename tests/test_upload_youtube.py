"""Testes para upload_youtube.py::upload_video.

upload_video() nao tinha nenhum teste dedicado ate agora, apesar de ser o
caminho de upload usado todo dia pelos crons de shorts e horizontal. Cobre
principalmente o padrao de duas chamadas a add_video_to_playlist (kind e
mood) - o fix da auditoria desta sessao (playlists por mood nunca eram
populadas porque so kind era passado).
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import upload_youtube


@pytest.fixture(autouse=True)
def _isolate_video_tags_file(tmp_path, monkeypatch):
    """upload_video() agora grava scene/hook/mood por video_id em
    _VIDEO_TAGS_FILE (ver _record_video_tags) - sem isolar isso todo teste
    desse modulo que chama upload_video() escreveria no _data/video_tags.json
    real do repo."""
    monkeypatch.setattr(upload_youtube, "_VIDEO_TAGS_FILE", tmp_path / "video_tags.json")


def _write_video_with_meta(output_dir: Path, meta: dict, stem: str = "pata_jazz_short_20260101") -> None:
    video_path = output_dir / f"{stem}.mp4"
    video_path.write_bytes(b"fake video bytes")
    # thumbnail/caption default to "" -> Path("") == Path(".") which
    # .exists() == True (cwd sempre existe), tentando abrir um diretorio
    # como arquivo. Aponta pra um caminho que garantidamente nao existe.
    meta.setdefault("thumbnail", str(output_dir / "no-such-thumbnail.png"))
    meta.setdefault("caption", str(output_dir / "no-such-caption.srt"))
    (output_dir / f"{stem}.json").write_text(json.dumps(meta), encoding="utf-8")


class TestCleanupOrphanBroadcasts:
    """cleanup_orphan_broadcasts(): varre e limpa broadcasts presos de uma
    run anterior que crashou sem rodar o finally de run_live.py."""

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

    def _iso_minutes_ago(self, minutes: float) -> str:
        from datetime import UTC, datetime, timedelta
        return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()

    def test_deletes_stale_ready_broadcast(self):
        service = self._service_with(
            upcoming_items=[{"id": "old_ready", "snippet": {"scheduledStartTime": self._iso_minutes_ago(60)}}]
        )
        with patch("upload_youtube.delete_broadcast") as mock_delete:
            cleaned = upload_youtube.cleanup_orphan_broadcasts(service)

        mock_delete.assert_called_once_with("old_ready")
        assert cleaned == 1

    def test_keeps_recent_ready_broadcast(self):
        service = self._service_with(
            upcoming_items=[{"id": "fresh_ready", "snippet": {"scheduledStartTime": self._iso_minutes_ago(2)}}]
        )
        with patch("upload_youtube.delete_broadcast") as mock_delete:
            cleaned = upload_youtube.cleanup_orphan_broadcasts(service)

        mock_delete.assert_not_called()
        assert cleaned == 0

    def test_completes_stale_active_broadcast(self):
        service = self._service_with(
            active_items=[{"id": "stuck_live", "snippet": {"actualStartTime": self._iso_minutes_ago(500)}}]
        )
        with patch("upload_youtube.transition_broadcast") as mock_transition:
            cleaned = upload_youtube.cleanup_orphan_broadcasts(service)

        mock_transition.assert_called_once_with("stuck_live", "complete")
        assert cleaned == 1

    def test_keeps_normal_running_session(self):
        service = self._service_with(
            active_items=[{"id": "normal_live", "snippet": {"actualStartTime": self._iso_minutes_ago(100)}}]
        )
        with patch("upload_youtube.transition_broadcast") as mock_transition:
            cleaned = upload_youtube.cleanup_orphan_broadcasts(service)

        mock_transition.assert_not_called()
        assert cleaned == 0

    def test_never_raises_even_if_api_call_fails(self):
        service = MagicMock()
        service.liveBroadcasts().list.side_effect = RuntimeError("api down")

        cleaned = upload_youtube.cleanup_orphan_broadcasts(service)

        assert cleaned == 0

    def test_missing_timestamp_is_skipped_not_crashed(self):
        service = self._service_with(upcoming_items=[{"id": "no_ts", "snippet": {}}])
        with patch("upload_youtube.delete_broadcast") as mock_delete:
            cleaned = upload_youtube.cleanup_orphan_broadcasts(service)

        mock_delete.assert_not_called()
        assert cleaned == 0


class TestGenerateLiveTitle:
    """_generate_live_title() rejeita titulo suspeito vindo da IA."""

    @patch("upload_youtube.ai_text")
    def test_uses_ai_title_when_safe(self, mock_ai_text):
        mock_ai_text.return_value = "Calming Jazz for Sleepy Cats"
        assert upload_youtube._generate_live_title() == "Calming Jazz for Sleepy Cats"

    @patch("upload_youtube.ai_text")
    def test_falls_back_when_ai_title_suspicious(self, mock_ai_text):
        mock_ai_text.return_value = "Click here: https://scam.example.com"
        title = upload_youtube._generate_live_title()
        assert "https://" not in title
        assert "Pata Jazz" in title

    @patch("upload_youtube.ai_text")
    def test_falls_back_when_ai_returns_empty(self, mock_ai_text):
        mock_ai_text.return_value = ""
        title = upload_youtube._generate_live_title()
        assert "Pata Jazz" in title


class TestMetaPath:
    """meta.get(key, "") vira Path("") == Path(".") quando a chave esta
    ausente/vazia, e '.'.exists() e sempre True (cwd sempre existe) -
    _meta_path evita esse caminho, retornando None em vez de um Path que
    aponta silenciosamente para o diretorio de trabalho atual."""

    def test_returns_none_for_missing_key(self):
        assert upload_youtube._meta_path({}, "thumbnail") is None

    def test_returns_none_for_empty_string(self):
        assert upload_youtube._meta_path({"thumbnail": ""}, "thumbnail") is None

    def test_returns_path_for_real_value(self):
        result = upload_youtube._meta_path({"thumbnail": "/tmp/x.png"}, "thumbnail")
        assert result == Path("/tmp/x.png")


class TestUploadVideoSurvivesOptionalStepFailures:
    """Thumbnail/legenda sao passos opcionais - se falharem (mesmo esgotando
    retries), upload_video() precisa continuar e retornar o video_id, ja
    que o video em si ja foi publicado com sucesso antes desses passos.

    Regressao real observada em producao (run 30155769151, main): thumbnail
    esgotou retries, _retry_youtube_call levantou RuntimeError (nao
    HttpError/MediaUploadSizeError), o except do bloco de thumbnail nao
    pegava RuntimeError, e isso derrubava upload_video() inteiro - pulando
    legenda e playlist e fazendo o job aparecer como "failure" no GitHub
    Actions apesar do video ja estar publico no canal.
    """

    def _setup(self, tmp_path, monkeypatch, **extra_meta):
        monkeypatch.setattr(upload_youtube, "OUTPUT_DIR", tmp_path)
        # video de teste e so bytes fake (nao um .mp4 de verdade), entao
        # ffprobe nao acha duracao - mocka pra passar do sanity check.
        monkeypatch.setattr(upload_youtube.ffmpeg_helpers, "get_video_duration", lambda path: 30.0)
        thumb_path = tmp_path / "thumb.png"
        thumb_path.write_bytes(b"fake png")
        caption_path = tmp_path / "cap.srt"
        caption_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")
        meta = {
            "title": "Gatinho Fofo", "description": "desc", "scene": "cat",
            "kind": "short", "mood": "relax",
            "thumbnail": str(thumb_path), "caption": str(caption_path),
        }
        meta.update(extra_meta)
        _write_video_with_meta(tmp_path, meta)
        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid-ok"}
        return service

    def test_runtime_error_from_thumbnail_retry_exhaustion_does_not_crash(self, tmp_path, monkeypatch):
        service = self._setup(tmp_path, monkeypatch)

        def fake_retry(func, *a, **kw):
            # Simula _retry_youtube_call esgotando tentativas: a chamada de
            # thumbnail (identificada pelo mock em service.thumbnails())
            # levanta RuntimeError; as outras (insert, caption, etc) passam.
            if "thumbnails" in str(func):
                raise RuntimeError("YouTube API: maximo de tentativas excedido sem resposta.")
            return func(*a, **kw)

        with patch("upload_youtube.get_youtube_service", return_value=service), \
             patch("upload_youtube._retry_youtube_call", side_effect=fake_retry), \
             patch("utils.playlist_manager.add_video_to_playlist") as mock_add:
            video_id = upload_youtube.upload_video(prefix="pata_jazz_")

        assert video_id == "vid-ok"
        # Execucao continuou apos a falha do thumbnail: playlist ainda foi chamada.
        assert mock_add.call_count == 2

    def test_runtime_error_from_caption_retry_exhaustion_does_not_crash(self, tmp_path, monkeypatch):
        service = self._setup(tmp_path, monkeypatch)

        def fake_retry(func, *a, **kw):
            if "captions" in str(func):
                raise RuntimeError("YouTube API: maximo de tentativas excedido sem resposta.")
            return func(*a, **kw)

        with patch("upload_youtube.get_youtube_service", return_value=service), \
             patch("upload_youtube._retry_youtube_call", side_effect=fake_retry), \
             patch("utils.playlist_manager.add_video_to_playlist") as mock_add:
            video_id = upload_youtube.upload_video(prefix="pata_jazz_")

        assert video_id == "vid-ok"
        assert mock_add.call_count == 2


class TestUploadVideoPlaylists:
    def test_adds_to_both_kind_and_mood_playlists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(upload_youtube, "OUTPUT_DIR", tmp_path)
        monkeypatch.setattr(upload_youtube.ffmpeg_helpers, "get_video_duration", lambda path: 30.0)
        _write_video_with_meta(tmp_path, {
            "title": "Gatinho Fofo",
            "description": "desc",
            "scene": "cat",
            "kind": "short",
            "mood": "relax",
        })

        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid123"}

        with patch("upload_youtube.get_youtube_service", return_value=service), \
             patch("utils.playlist_manager.add_video_to_playlist") as mock_add:
            video_id = upload_youtube.upload_video(prefix="pata_jazz_")

        assert video_id == "vid123"
        assert mock_add.call_count == 2
        calls = mock_add.call_args_list
        assert calls[0].kwargs.get("kind") == "short"
        assert calls[1].kwargs.get("mood") == "relax"

    def test_skips_mood_playlist_when_mood_missing(self, tmp_path, monkeypatch):
        """Sem meta['mood'], so a chamada por kind deve acontecer (nao passar
        mood='' para add_video_to_playlist, que trataria como sem alvo)."""
        monkeypatch.setattr(upload_youtube, "OUTPUT_DIR", tmp_path)
        monkeypatch.setattr(upload_youtube.ffmpeg_helpers, "get_video_duration", lambda path: 30.0)
        _write_video_with_meta(tmp_path, {
            "title": "Gatinho Fofo",
            "description": "desc",
            "scene": "cat",
            "kind": "short",
        })

        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid456"}

        with patch("upload_youtube.get_youtube_service", return_value=service), \
             patch("utils.playlist_manager.add_video_to_playlist") as mock_add:
            upload_youtube.upload_video(prefix="pata_jazz_")

        assert mock_add.call_count == 1
        assert mock_add.call_args.kwargs.get("kind") == "short"

    def test_playlist_failure_does_not_fail_upload(self, tmp_path, monkeypatch):
        """Falha ao adicionar a playlist e so um warning - upload_video ainda
        retorna o video_id normalmente."""
        monkeypatch.setattr(upload_youtube, "OUTPUT_DIR", tmp_path)
        monkeypatch.setattr(upload_youtube.ffmpeg_helpers, "get_video_duration", lambda path: 30.0)
        _write_video_with_meta(tmp_path, {
            "title": "Gatinho Fofo", "description": "desc", "scene": "cat", "kind": "short", "mood": "relax",
        })

        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid789"}

        with patch("upload_youtube.get_youtube_service", return_value=service), \
             patch("utils.playlist_manager.add_video_to_playlist", side_effect=RuntimeError("api down")):
            video_id = upload_youtube.upload_video(prefix="pata_jazz_")

        assert video_id == "vid789"

    def test_returns_none_when_no_video_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(upload_youtube, "OUTPUT_DIR", tmp_path)
        assert upload_youtube.upload_video(prefix="pata_jazz_") is None


class TestRecordVideoTags:
    """_record_video_tags(): mapeamento video_id -> scene/hook/mood que
    collect_analytics.py cruza com views reais para o feedback loop de
    scene_for_mood (utils/content_strategy.py)."""

    def test_writes_scene_hook_mood_kind(self, tmp_path, monkeypatch):
        tags_file = tmp_path / "video_tags.json"
        monkeypatch.setattr(upload_youtube, "_VIDEO_TAGS_FILE", tags_file)

        upload_youtube._record_video_tags(
            "vid1", {"scene": "cat", "hook": "Cute Cat", "mood": "fofura", "kind": "short"}
        )

        data = json.loads(tags_file.read_text(encoding="utf-8"))
        assert data["vid1"]["scene"] == "cat"
        assert data["vid1"]["hook"] == "Cute Cat"
        assert data["vid1"]["mood"] == "fofura"
        assert data["vid1"]["kind"] == "short"
        assert "uploaded_at" in data["vid1"]

    def test_skips_when_scene_missing(self, tmp_path, monkeypatch):
        tags_file = tmp_path / "video_tags.json"
        monkeypatch.setattr(upload_youtube, "_VIDEO_TAGS_FILE", tags_file)

        upload_youtube._record_video_tags("vid1", {"hook": "Cute Cat"})

        assert not tags_file.exists()

    def test_merges_with_existing_entries(self, tmp_path, monkeypatch):
        tags_file = tmp_path / "video_tags.json"
        tags_file.write_text(json.dumps({"old_vid": {"scene": "dog"}}), encoding="utf-8")
        monkeypatch.setattr(upload_youtube, "_VIDEO_TAGS_FILE", tags_file)

        upload_youtube._record_video_tags("vid1", {"scene": "cat"})

        data = json.loads(tags_file.read_text(encoding="utf-8"))
        assert set(data.keys()) == {"old_vid", "vid1"}

    def test_caps_at_max_video_tags(self, tmp_path, monkeypatch):
        tags_file = tmp_path / "video_tags.json"
        monkeypatch.setattr(upload_youtube, "_VIDEO_TAGS_FILE", tags_file)
        monkeypatch.setattr(upload_youtube, "_MAX_VIDEO_TAGS", 3)

        for i in range(3):
            upload_youtube._record_video_tags(f"vid{i}", {"scene": "cat"})
        upload_youtube._record_video_tags("vid_new", {"scene": "cat"})

        data = json.loads(tags_file.read_text(encoding="utf-8"))
        assert len(data) == 3
        assert "vid0" not in data  # o mais antigo foi descartado
        assert "vid_new" in data

    def test_upload_video_persists_tags_end_to_end(self, tmp_path, monkeypatch):
        tags_file = tmp_path / "video_tags.json"
        monkeypatch.setattr(upload_youtube, "_VIDEO_TAGS_FILE", tags_file)
        monkeypatch.setattr(upload_youtube, "OUTPUT_DIR", tmp_path)
        monkeypatch.setattr(upload_youtube.ffmpeg_helpers, "get_video_duration", lambda path: 30.0)
        _write_video_with_meta(tmp_path, {
            "title": "Gatinho Fofo", "description": "desc", "scene": "cat", "kind": "short", "mood": "relax",
        })

        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid_e2e", "status": {"privacyStatus": "public"}}

        with patch("upload_youtube.get_youtube_service", return_value=service), \
             patch("utils.playlist_manager.add_video_to_playlist"):
            video_id = upload_youtube.upload_video(prefix="pata_jazz_")

        assert video_id == "vid_e2e"
        data = json.loads(tags_file.read_text(encoding="utf-8"))
        assert data["vid_e2e"]["scene"] == "cat"
        assert data["vid_e2e"]["mood"] == "relax"


class TestRecordLiveViewerSnapshot:
    """record_live_viewer_snapshot(): amostra concurrentViewers de uma live
    em andamento, chamada uma vez por segmento de FFmpeg por run_live.py."""

    def _isolate(self, tmp_path, monkeypatch):
        history_file = tmp_path / "live_viewer_history.json"
        monkeypatch.setattr(upload_youtube, "LIVE_VIEWER_HISTORY_FILE", history_file)
        return history_file

    def test_saves_viewer_count_snapshot(self, tmp_path, monkeypatch):
        history_file = self._isolate(tmp_path, monkeypatch)
        service = MagicMock()
        service.videos().list().execute.return_value = {
            "items": [{"liveStreamingDetails": {"concurrentViewers": "42"}}]
        }

        with patch("upload_youtube.get_youtube_service", return_value=service):
            upload_youtube.record_live_viewer_snapshot("bcast123")

        history = json.loads(history_file.read_text(encoding="utf-8"))
        assert len(history) == 1
        assert history[0]["video_id"] == "bcast123"
        assert history[0]["concurrent_viewers"] == 42

    def test_appends_to_existing_history(self, tmp_path, monkeypatch):
        history_file = self._isolate(tmp_path, monkeypatch)
        history_file.write_text(json.dumps([{"video_id": "old", "concurrent_viewers": 5}]), encoding="utf-8")
        service = MagicMock()
        service.videos().list().execute.return_value = {
            "items": [{"liveStreamingDetails": {"concurrentViewers": "10"}}]
        }

        with patch("upload_youtube.get_youtube_service", return_value=service):
            upload_youtube.record_live_viewer_snapshot("bcast123")

        history = json.loads(history_file.read_text(encoding="utf-8"))
        assert len(history) == 2

    def test_caps_at_max_snapshots(self, tmp_path, monkeypatch):
        history_file = self._isolate(tmp_path, monkeypatch)
        monkeypatch.setattr(upload_youtube, "_MAX_VIEWER_SNAPSHOTS", 3)
        history_file.write_text(
            json.dumps([{"video_id": f"old{i}", "concurrent_viewers": i} for i in range(3)]), encoding="utf-8"
        )
        service = MagicMock()
        service.videos().list().execute.return_value = {
            "items": [{"liveStreamingDetails": {"concurrentViewers": "99"}}]
        }

        with patch("upload_youtube.get_youtube_service", return_value=service):
            upload_youtube.record_live_viewer_snapshot("bcast_new")

        history = json.loads(history_file.read_text(encoding="utf-8"))
        assert len(history) == 3
        assert history[-1]["video_id"] == "bcast_new"

    def test_no_items_does_not_write(self, tmp_path, monkeypatch):
        history_file = self._isolate(tmp_path, monkeypatch)
        service = MagicMock()
        service.videos().list().execute.return_value = {"items": []}

        with patch("upload_youtube.get_youtube_service", return_value=service):
            upload_youtube.record_live_viewer_snapshot("bcast123")

        assert not history_file.exists()

    def test_missing_concurrent_viewers_does_not_write(self, tmp_path, monkeypatch):
        history_file = self._isolate(tmp_path, monkeypatch)
        service = MagicMock()
        service.videos().list().execute.return_value = {"items": [{"liveStreamingDetails": {}}]}

        with patch("upload_youtube.get_youtube_service", return_value=service):
            upload_youtube.record_live_viewer_snapshot("bcast123")

        assert not history_file.exists()

    def test_service_error_does_not_raise(self, tmp_path, monkeypatch):
        self._isolate(tmp_path, monkeypatch)
        with patch("upload_youtube.get_youtube_service", side_effect=RuntimeError("no creds")):
            upload_youtube.record_live_viewer_snapshot("bcast123")  # nao deve levantar


class TestTryResumeExistingBroadcast:
    """_try_resume_existing_broadcast(): reaproveita o broadcast/stream da
    sessao anterior (salvo em live_state.json) em vez de criar um novo -
    sem isso, cada sessao do GitHub Actions criava um link de live diferente
    mesmo quando o encadeamento entre sessoes tinha gap real de poucos
    minutos, quebrando a impressao de "1 live que nunca para". Qualquer
    situacao ambigua (arquivo ausente, broadcast/stream nao encontrado,
    lifecycle terminal, erro de API) deve cair no fallback seguro (None ->
    create_live_stream cria um broadcast novo, igual ao comportamento antes
    desta funcao existir)."""

    def _isolate(self, tmp_path, monkeypatch):
        state_file = tmp_path / "live_state.json"
        monkeypatch.setattr(upload_youtube, "_LIVE_STATE_FILE", state_file)
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

    def test_returns_none_when_no_state_file(self, tmp_path, monkeypatch):
        self._isolate(tmp_path, monkeypatch)
        service = MagicMock()
        assert upload_youtube._try_resume_existing_broadcast(service) is None

    def test_returns_none_when_state_file_corrupted(self, tmp_path, monkeypatch):
        state_file = self._isolate(tmp_path, monkeypatch)
        state_file.write_text("not json", encoding="utf-8")
        service = MagicMock()
        assert upload_youtube._try_resume_existing_broadcast(service) is None

    def test_returns_none_when_state_file_missing_required_keys(self, tmp_path, monkeypatch):
        state_file = self._isolate(tmp_path, monkeypatch)
        state_file.write_text(json.dumps({"title": "x"}), encoding="utf-8")
        service = MagicMock()
        assert upload_youtube._try_resume_existing_broadcast(service) is None

    def test_returns_none_when_broadcast_not_found(self, tmp_path, monkeypatch):
        state_file = self._isolate(tmp_path, monkeypatch)
        state_file.write_text(json.dumps({"broadcast_id": "b1", "stream_id": "s1"}), encoding="utf-8")
        service = self._service_with(broadcast_items=[])

        assert upload_youtube._try_resume_existing_broadcast(service) is None

    def test_returns_none_when_lifecycle_is_complete(self, tmp_path, monkeypatch):
        state_file = self._isolate(tmp_path, monkeypatch)
        state_file.write_text(json.dumps({"broadcast_id": "b1", "stream_id": "s1"}), encoding="utf-8")
        service = self._service_with(broadcast_items=[{"status": {"lifeCycleStatus": "complete"}}])

        assert upload_youtube._try_resume_existing_broadcast(service) is None

    def test_returns_none_when_lifecycle_is_revoked(self, tmp_path, monkeypatch):
        state_file = self._isolate(tmp_path, monkeypatch)
        state_file.write_text(json.dumps({"broadcast_id": "b1", "stream_id": "s1"}), encoding="utf-8")
        service = self._service_with(broadcast_items=[{"status": {"lifeCycleStatus": "revoked"}}])

        assert upload_youtube._try_resume_existing_broadcast(service) is None

    def test_returns_none_when_stream_not_found(self, tmp_path, monkeypatch):
        state_file = self._isolate(tmp_path, monkeypatch)
        state_file.write_text(json.dumps({"broadcast_id": "b1", "stream_id": "s1"}), encoding="utf-8")
        service = self._service_with(broadcast_items=[{"status": {"lifeCycleStatus": "live"}}], stream_items=[])

        assert upload_youtube._try_resume_existing_broadcast(service) is None

    def test_returns_none_on_api_exception(self, tmp_path, monkeypatch):
        state_file = self._isolate(tmp_path, monkeypatch)
        state_file.write_text(json.dumps({"broadcast_id": "b1", "stream_id": "s1"}), encoding="utf-8")
        service = MagicMock()
        service.liveBroadcasts().list.side_effect = RuntimeError("api down")

        assert upload_youtube._try_resume_existing_broadcast(service) is None

    def test_resumes_when_lifecycle_is_live(self, tmp_path, monkeypatch):
        state_file = self._isolate(tmp_path, monkeypatch)
        state_file.write_text(
            json.dumps({
                "broadcast_id": "b1", "stream_id": "s1",
                "title": "Pata Jazz Live", "description": "desc", "privacy": "public",
            }),
            encoding="utf-8",
        )
        service = self._service_with(
            broadcast_items=[{"status": {"lifeCycleStatus": "live"}}],
            stream_items=[{"cdn": {"ingestionInfo": {"streamName": "abcd-1234"}}}],
        )

        result = upload_youtube._try_resume_existing_broadcast(service)

        assert result == {
            "broadcast_id": "b1",
            "stream_id": "s1",
            "stream_name": "abcd-1234",
            "ingestion_url": "rtmp://a.rtmp.youtube.com/live2/abcd-1234",
            "title": "Pata Jazz Live",
            "description": "desc",
            "privacy": "public",
        }

    def test_resumes_when_lifecycle_is_ready(self, tmp_path, monkeypatch):
        """'ready' (upcoming, ainda nao foi ao ar) tambem e reaproveitavel -
        cleanup_orphan_broadcasts ja cuida de apagar um 'ready' velho demais
        antes desta funcao rodar."""
        state_file = self._isolate(tmp_path, monkeypatch)
        state_file.write_text(json.dumps({"broadcast_id": "b1", "stream_id": "s1"}), encoding="utf-8")
        service = self._service_with(
            broadcast_items=[{"status": {"lifeCycleStatus": "ready"}}],
            stream_items=[{"cdn": {"ingestionInfo": {"streamName": "abcd-1234"}}}],
        )

        result = upload_youtube._try_resume_existing_broadcast(service)

        assert result is not None
        assert result["broadcast_id"] == "b1"


class TestCreateLiveStreamResume:
    """create_live_stream(): so cria um broadcast novo quando nao ha um
    reaproveitavel - o caminho de reaproveitamento nao deve chamar
    liveBroadcasts().insert()/liveStreams().insert() de jeito nenhum."""

    def _isolate(self, tmp_path, monkeypatch):
        state_file = tmp_path / "live_state.json"
        monkeypatch.setattr(upload_youtube, "_LIVE_STATE_FILE", state_file)
        return state_file

    def test_reuses_existing_broadcast_without_creating_new(self, tmp_path, monkeypatch):
        state_file = self._isolate(tmp_path, monkeypatch)
        resumed_meta = {
            "broadcast_id": "b1", "stream_id": "s1", "stream_name": "abcd",
            "ingestion_url": "rtmp://a.rtmp.youtube.com/live2/abcd",
            "title": "t", "description": "d", "privacy": "public",
        }
        service = MagicMock()
        with (
            patch("upload_youtube.get_youtube_service", return_value=service),
            patch("upload_youtube.cleanup_orphan_broadcasts"),
            patch("upload_youtube._try_resume_existing_broadcast", return_value=resumed_meta),
        ):
            result = upload_youtube.create_live_stream(privacy="public", resolution="720p")

        assert result == resumed_meta
        service.liveBroadcasts().insert.assert_not_called()
        service.liveStreams().insert.assert_not_called()
        assert json.loads(state_file.read_text(encoding="utf-8")) == resumed_meta

    def test_creates_new_broadcast_when_nothing_resumable(self, tmp_path, monkeypatch):
        state_file = self._isolate(tmp_path, monkeypatch)
        service = MagicMock()
        service.liveBroadcasts().insert().execute.return_value = {"id": "new_broadcast"}
        service.liveStreams().insert().execute.return_value = {
            "id": "new_stream",
            "cdn": {"ingestionInfo": {"streamName": "new-key"}},
        }
        with (
            patch("upload_youtube.get_youtube_service", return_value=service),
            patch("upload_youtube.cleanup_orphan_broadcasts"),
            patch("upload_youtube._try_resume_existing_broadcast", return_value=None),
            patch("upload_youtube._generate_live_title", return_value="Generated Title"),
        ):
            result = upload_youtube.create_live_stream(privacy="public", resolution="720p")

        assert result["broadcast_id"] == "new_broadcast"
        assert result["stream_id"] == "new_stream"
        assert result["ingestion_url"] == "rtmp://a.rtmp.youtube.com/live2/new-key"
        service.liveBroadcasts().insert.assert_called()
        service.liveStreams().insert.assert_called()
        assert json.loads(state_file.read_text(encoding="utf-8"))["broadcast_id"] == "new_broadcast"
