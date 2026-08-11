"""Testes para upload_youtube.py::upload_video.

upload_video() e o caminho de upload usado todo dia pelos crons de shorts.
Cobre principalmente o padrao de duas chamadas a add_video_to_playlist (kind
e mood) - o fix da auditoria desta sessao (playlists por mood nunca eram
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


def test_latest_video_skips_already_uploaded_file(tmp_path, monkeypatch):
    monkeypatch.setattr(upload_youtube, "OUTPUT_DIR", tmp_path)
    _write_video_with_meta(tmp_path, {"scene": "cat"}, stem="pata_jazz_short_fresh")
    _write_video_with_meta(
        tmp_path,
        {"scene": "cat", "video_id": "already-on-youtube", "published": True},
        stem="pata_jazz_short_uploaded",
    )
    uploaded = tmp_path / "pata_jazz_short_uploaded.mp4"
    uploaded.touch()

    found = upload_youtube._latest_video_meta(prefix="pata_jazz_short_")

    assert found is not None
    assert found[0].name == "pata_jazz_short_fresh.mp4"


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
            "title": "Gatinho Fofo",
            "description": "desc",
            "scene": "cat",
            "kind": "short",
            "mood": "relax",
            "thumbnail": str(thumb_path),
            "caption": str(caption_path),
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

        with (
            patch("upload_youtube.get_youtube_service", return_value=service),
            patch("upload_youtube._retry_youtube_call", side_effect=fake_retry),
            patch("utils.youtube_post_upload.add_video_to_playlist") as mock_add,
        ):
            video_id = upload_youtube.upload_video(prefix="pata_jazz_")

        assert video_id == "vid-ok"
        # Execucao continuou apos a falha do thumbnail: playlist ainda foi chamada (animal+mood+kind).
        assert mock_add.call_count == 3

    def test_runtime_error_from_caption_retry_exhaustion_does_not_crash(self, tmp_path, monkeypatch):
        service = self._setup(tmp_path, monkeypatch)

        def fake_retry(func, *a, **kw):
            if "captions" in str(func):
                raise RuntimeError("YouTube API: maximo de tentativas excedido sem resposta.")
            return func(*a, **kw)

        with (
            patch("upload_youtube.get_youtube_service", return_value=service),
            patch("upload_youtube._retry_youtube_call", side_effect=fake_retry),
            patch("utils.youtube_post_upload.add_video_to_playlist") as mock_add,
        ):
            video_id = upload_youtube.upload_video(prefix="pata_jazz_")

        assert video_id == "vid-ok"
        assert mock_add.call_count == 3


class TestUploadVideoPlaylists:
    def test_adds_to_both_kind_and_mood_playlists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(upload_youtube, "OUTPUT_DIR", tmp_path)
        monkeypatch.setattr(upload_youtube.ffmpeg_helpers, "get_video_duration", lambda path: 30.0)
        _write_video_with_meta(
            tmp_path,
            {
                "title": "Gatinho Fofo",
                "description": "desc",
                "scene": "cat",
                "kind": "short",
                "mood": "relax",
            },
        )

        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid123"}

        with (
            patch("upload_youtube.get_youtube_service", return_value=service),
            patch("utils.youtube_post_upload.add_video_to_playlist") as mock_add,
        ):
            video_id = upload_youtube.upload_video(prefix="pata_jazz_")

        assert video_id == "vid123"
        assert mock_add.call_count == 3
        calls = mock_add.call_args_list
        assert calls[0].kwargs.get("mood") == "cat_playlist"
        assert calls[1].kwargs.get("mood") == "relax"
        assert calls[2].kwargs.get("kind") == "short"

    def test_skips_mood_playlist_when_mood_missing(self, tmp_path, monkeypatch):
        """Sem meta['mood'], ainda adiciona a playlist por animal e por kind."""
        monkeypatch.setattr(upload_youtube, "OUTPUT_DIR", tmp_path)
        monkeypatch.setattr(upload_youtube.ffmpeg_helpers, "get_video_duration", lambda path: 30.0)
        _write_video_with_meta(
            tmp_path,
            {
                "title": "Gatinho Fofo",
                "description": "desc",
                "scene": "cat",
                "kind": "short",
            },
        )

        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid456"}

        with (
            patch("upload_youtube.get_youtube_service", return_value=service),
            patch("utils.youtube_post_upload.add_video_to_playlist") as mock_add,
        ):
            upload_youtube.upload_video(prefix="pata_jazz_")

        assert mock_add.call_count == 2
        calls = mock_add.call_args_list
        assert calls[0].kwargs.get("mood") == "cat_playlist"
        assert calls[1].kwargs.get("kind") == "short"

    def test_playlist_failure_does_not_fail_upload(self, tmp_path, monkeypatch):
        """Falha ao adicionar a playlist e so um warning - upload_video ainda
        retorna o video_id normalmente."""
        monkeypatch.setattr(upload_youtube, "OUTPUT_DIR", tmp_path)
        monkeypatch.setattr(upload_youtube.ffmpeg_helpers, "get_video_duration", lambda path: 30.0)
        _write_video_with_meta(
            tmp_path,
            {
                "title": "Gatinho Fofo",
                "description": "desc",
                "scene": "cat",
                "kind": "short",
                "mood": "relax",
            },
        )

        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid789"}

        with (
            patch("upload_youtube.get_youtube_service", return_value=service),
            patch("utils.youtube_post_upload.add_video_to_playlist", side_effect=RuntimeError("api down")),
        ):
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
            "vid1",
            {
                "scene": "cat",
                "hook": "Cute Cat",
                "mood": "fofura",
                "kind": "short",
                "title_pattern": "{emoji} {adjetivo} {animal}",
            },
        )

        data = json.loads(tags_file.read_text(encoding="utf-8"))
        assert data["vid1"]["scene"] == "cat"
        assert data["vid1"]["hook"] == "Cute Cat"
        assert data["vid1"]["mood"] == "fofura"
        assert data["vid1"]["kind"] == "short"
        assert data["vid1"]["title_pattern"] == "{emoji} {adjetivo} {animal}"
        assert "uploaded_at" in data["vid1"]

    def test_title_pattern_defaults_to_empty_string_when_missing(self, tmp_path, monkeypatch):
        tags_file = tmp_path / "video_tags.json"
        monkeypatch.setattr(upload_youtube, "_VIDEO_TAGS_FILE", tags_file)

        upload_youtube._record_video_tags("vid1", {"scene": "cat"})

        data = json.loads(tags_file.read_text(encoding="utf-8"))
        assert data["vid1"]["title_pattern"] == ""

    def test_persists_thumbnails_and_default_variant(self, tmp_path, monkeypatch):
        """_record_video_tags grava a lista de variantes de thumbnail (pra
        maybe_rotate_thumbnail saber que o video tem B disponivel) e cai em
        thumbnail_variant='A' quando o meta nao informa qual foi a
        primaria."""
        tags_file = tmp_path / "video_tags.json"
        monkeypatch.setattr(upload_youtube, "_VIDEO_TAGS_FILE", tags_file)

        upload_youtube._record_video_tags(
            "vid1",
            {
                "scene": "cat",
                "thumbnails": ["/tmp/a.png", "/tmp/b.png"],
            },
        )

        data = json.loads(tags_file.read_text(encoding="utf-8"))
        assert data["vid1"]["thumbnails"] == ["/tmp/a.png", "/tmp/b.png"]
        assert data["vid1"]["thumbnail_variant"] == "A"

    def test_records_thumbnail_variant_chosen_by_feedback_loop(self, tmp_path, monkeypatch):
        """Quando video_builder decidiu comecar com a variante vencedora
        (ex.: "B", por ter mais views historicamente), _record_video_tags
        grava essa variante - nao trava sempre em "A"."""
        tags_file = tmp_path / "video_tags.json"
        monkeypatch.setattr(upload_youtube, "_VIDEO_TAGS_FILE", tags_file)

        upload_youtube._record_video_tags(
            "vid1",
            {
                "scene": "cat",
                "thumbnails": ["/tmp/a.png", "/tmp/b.png", "/tmp/c.png"],
                "thumbnail_variant": "B",
            },
        )

        data = json.loads(tags_file.read_text(encoding="utf-8"))
        assert data["vid1"]["thumbnail_variant"] == "B"

    def test_thumbnail_fields_default_when_meta_has_no_thumbnails(self, tmp_path, monkeypatch):
        tags_file = tmp_path / "video_tags.json"
        monkeypatch.setattr(upload_youtube, "_VIDEO_TAGS_FILE", tags_file)

        upload_youtube._record_video_tags("vid1", {"scene": "cat"})

        data = json.loads(tags_file.read_text(encoding="utf-8"))
        assert data["vid1"]["thumbnails"] == []
        assert data["vid1"]["thumbnail_variant"] == "A"

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
        _write_video_with_meta(
            tmp_path,
            {
                "title": "Gatinho Fofo",
                "description": "desc",
                "scene": "cat",
                "kind": "short",
                "mood": "relax",
            },
        )

        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid_e2e", "status": {"privacyStatus": "public"}}

        with (
            patch("upload_youtube.get_youtube_service", return_value=service),
            patch("utils.youtube_post_upload.add_video_to_playlist"),
        ):
            video_id = upload_youtube.upload_video(prefix="pata_jazz_")

        assert video_id == "vid_e2e"
        data = json.loads(tags_file.read_text(encoding="utf-8"))
        assert data["vid_e2e"]["scene"] == "cat"
        assert data["vid_e2e"]["mood"] == "relax"


class TestQuotaGuard:
    """upload_video aborta antes de gastar quota quando o dia ja esta no
    limiar de alerta - evita um insert que estoura a quota e deixa o video
    preso em processing/private no canal."""

    def _setup(self, tmp_path, monkeypatch):
        monkeypatch.setattr(upload_youtube, "OUTPUT_DIR", tmp_path)
        monkeypatch.setattr(upload_youtube.ffmpeg_helpers, "get_video_duration", lambda path: 30.0)
        _write_video_with_meta(
            tmp_path,
            {
                "title": "Gatinho Fofo",
                "description": "desc",
                "scene": "cat",
                "kind": "short",
                "mood": "relax",
            },
        )

    def test_aborts_when_quota_at_threshold(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch)
        service = MagicMock()
        with (
            patch("upload_youtube.get_youtube_service", return_value=service),
            patch("upload_youtube.daily_total", return_value=upload_youtube.ALERT_THRESHOLD),
        ):
            video_id = upload_youtube.upload_video(prefix="pata_jazz_")

        assert video_id is None
        service.videos().insert.assert_not_called()

    def test_proceeds_when_quota_below_threshold(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch)
        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid-ok"}
        with (
            patch("upload_youtube.get_youtube_service", return_value=service),
            patch("upload_youtube.daily_total", return_value=100),
            patch("utils.youtube_post_upload.add_video_to_playlist"),
        ):
            video_id = upload_youtube.upload_video(prefix="pata_jazz_")

        assert video_id == "vid-ok"
