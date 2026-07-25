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

import upload_youtube


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


class TestUploadVideoPlaylists:
    def test_adds_to_both_kind_and_mood_playlists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(upload_youtube, "OUTPUT_DIR", tmp_path)
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
