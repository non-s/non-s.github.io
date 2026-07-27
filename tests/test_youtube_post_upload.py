"""Testes para utils/youtube_post_upload.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from utils import youtube_post_upload as ypu


def _no_retry(func):
    return func()


def test_apply_thumbnail_skips_when_missing():
    service = MagicMock()
    ypu.apply_thumbnail(service, "vid", None, _no_retry)
    service.thumbnails.assert_not_called()


def test_apply_thumbnail_calls_api(tmp_path: Path):
    thumb = tmp_path / "thumb.png"
    thumb.write_text("fake", encoding="utf-8")
    service = MagicMock()
    ypu.apply_thumbnail(service, "vid", thumb, _no_retry)
    service.thumbnails().set.assert_called_once()


def test_apply_thumbnail_logs_warning_on_error(tmp_path: Path, caplog):
    thumb = tmp_path / "thumb.png"
    thumb.write_text("fake", encoding="utf-8")
    service = MagicMock()
    service.thumbnails.return_value.set.side_effect = RuntimeError("503")
    ypu.apply_thumbnail(service, "vid", thumb, _no_retry)
    assert "Falha ao aplicar thumbnail" in caplog.text


def test_apply_caption_skips_when_missing():
    service = MagicMock()
    ypu.apply_caption(service, "vid", None, _no_retry)
    service.captions.assert_not_called()


def test_apply_caption_srt_mimetype(tmp_path: Path):
    caption = tmp_path / "caption.srt"
    caption.write_text("fake", encoding="utf-8")
    service = MagicMock()
    ypu.apply_caption(service, "vid", caption, _no_retry)
    call_kwargs = service.captions().insert.call_args[1]
    assert call_kwargs["media_body"].mimetype() == "application/x-subrip"


def test_apply_caption_vtt_mimetype(tmp_path: Path):
    caption = tmp_path / "caption.vtt"
    caption.write_text("fake", encoding="utf-8")
    service = MagicMock()
    ypu.apply_caption(service, "vid", caption, _no_retry)
    call_kwargs = service.captions().insert.call_args[1]
    assert call_kwargs["media_body"].mimetype() == "text/vtt"


def test_add_to_playlists_calls_playlist_manager():
    service = MagicMock()
    with patch("utils.youtube_post_upload.add_video_to_playlist") as mock_add:
        ypu.add_to_playlists(service, "vid", {"kind": "short", "mood": "chill"})
    assert mock_add.call_count == 2


def test_add_to_playlists_logs_error():
    service = MagicMock()
    with patch("utils.youtube_post_upload.add_video_to_playlist", side_effect=RuntimeError("boom")):
        # Nao deve levantar.
        ypu.add_to_playlists(service, "vid", {"kind": "short"})
