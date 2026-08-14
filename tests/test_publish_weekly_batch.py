"""Testes para scripts/publish_weekly_batch.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import scripts.publish_weekly_batch as publish_weekly_batch
import upload_youtube


@pytest.fixture(autouse=True)
def _isolate_video_tags_file(tmp_path, monkeypatch):
    """_publish_video() chama _record_video_tags (upload_youtube.py) no
    caminho de upload novo - isola pra nao escrever no _data/video_tags.json
    real do repo."""
    monkeypatch.setattr(upload_youtube, "_VIDEO_TAGS_FILE", tmp_path / "video_tags.json")


def _write_video(output_dir: Path, stem: str, meta: dict) -> Path:
    video_path = output_dir / f"{stem}.mp4"
    video_path.write_bytes(b"fake video bytes")
    (output_dir / f"{stem}.json").write_text(json.dumps(meta), encoding="utf-8")
    return video_path


class TestFindUnpublishedVideos:
    def test_finds_video_without_published_flag(self, tmp_path, monkeypatch):
        monkeypatch.setattr(publish_weekly_batch, "OUTPUT_DIR", tmp_path)
        _write_video(tmp_path, "liquid_wire_short_1", {"title": "A"})

        result = publish_weekly_batch._find_unpublished_videos()

        assert len(result) == 1
        assert result[0][1]["title"] == "A"

    def test_skips_already_published(self, tmp_path, monkeypatch):
        monkeypatch.setattr(publish_weekly_batch, "OUTPUT_DIR", tmp_path)
        _write_video(tmp_path, "liquid_wire_short_1", {"title": "A", "published": True})

        result = publish_weekly_batch._find_unpublished_videos()

        assert result == []

    def test_skips_meta_with_video_id_but_no_published_flag(self, tmp_path, monkeypatch):
        """video_id presente (upload private feito) tambem conta como
        'ja processado', mesmo sem published=True ainda."""
        monkeypatch.setattr(publish_weekly_batch, "OUTPUT_DIR", tmp_path)
        _write_video(tmp_path, "liquid_wire_short_1", {"title": "A", "video_id": "abc123"})

        result = publish_weekly_batch._find_unpublished_videos()

        assert result == []

    def test_skips_meta_without_matching_video_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(publish_weekly_batch, "OUTPUT_DIR", tmp_path)
        (tmp_path / "liquid_wire_short_1.json").write_text(json.dumps({"title": "A"}), encoding="utf-8")

        result = publish_weekly_batch._find_unpublished_videos()

        assert result == []

    def test_skips_corrupted_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr(publish_weekly_batch, "OUTPUT_DIR", tmp_path)
        (tmp_path / "liquid_wire_short_1.mp4").write_bytes(b"x")
        (tmp_path / "liquid_wire_short_1.json").write_text("not json{{{", encoding="utf-8")

        result = publish_weekly_batch._find_unpublished_videos()

        assert result == []

    def test_orders_by_modification_time(self, tmp_path, monkeypatch):
        monkeypatch.setattr(publish_weekly_batch, "OUTPUT_DIR", tmp_path)
        _write_video(tmp_path, "liquid_wire_short_2", {"title": "second"})
        _write_video(tmp_path, "liquid_wire_short_1", {"title": "first_by_mtime"})

        mtimes = {"liquid_wire_short_2": 100.0, "liquid_wire_short_1": 200.0}
        real_stat = Path.stat

        def _fake_stat(self, *args, **kwargs):
            if self.stem in mtimes:
                result = MagicMock(wraps=real_stat(self, *args, **kwargs))
                result.st_mtime = mtimes[self.stem]
                return result
            return real_stat(self, *args, **kwargs)

        monkeypatch.setattr(Path, "stat", _fake_stat)

        result = publish_weekly_batch._find_unpublished_videos()

        assert [meta["title"] for _, meta in result] == ["second", "first_by_mtime"]


class TestPublishVideo:
    def _service_with_duration_ok(self, monkeypatch, duration=30.0):
        monkeypatch.setattr(publish_weekly_batch.ffmpeg_helpers, "get_video_duration", lambda p: duration)

    def test_existing_video_id_updates_privacy_instead_of_reuploading(self, tmp_path, monkeypatch):
        self._service_with_duration_ok(monkeypatch)
        service = MagicMock()
        video_path = tmp_path / "v.mp4"
        video_path.write_bytes(b"x")
        meta = {"title": "T", "video_id": "existing123"}

        result = publish_weekly_batch._publish_video(service, video_path, meta)

        assert result == "existing123"
        service.videos().update.assert_called_once()
        service.videos().insert.assert_not_called()

    def test_falls_back_to_new_upload_when_privacy_update_fails(self, tmp_path, monkeypatch):
        self._service_with_duration_ok(monkeypatch)
        service = MagicMock()
        service.videos().update().execute.side_effect = RuntimeError("404 not found")
        service.videos().insert().execute.return_value = {"id": "new456", "status": {"privacyStatus": "public"}}
        video_path = tmp_path / "v.mp4"
        video_path.write_bytes(b"x")
        meta = {"title": "T", "video_id": "gone789"}

        with patch("utils.youtube_post_upload.add_video_to_playlist"):
            result = publish_weekly_batch._publish_video(service, video_path, meta)

        assert result == "new456"

    def test_rejects_zero_duration_video(self, tmp_path, monkeypatch):
        self._service_with_duration_ok(monkeypatch, duration=0.0)
        service = MagicMock()
        video_path = tmp_path / "v.mp4"
        video_path.write_bytes(b"x")

        result = publish_weekly_batch._publish_video(service, video_path, {"title": "T"})

        assert result is None
        service.videos().insert.assert_not_called()

    def test_new_upload_returns_video_id(self, tmp_path, monkeypatch):
        self._service_with_duration_ok(monkeypatch)
        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid1", "status": {"privacyStatus": "public"}}
        video_path = tmp_path / "v.mp4"
        video_path.write_bytes(b"x")

        with patch("utils.youtube_post_upload.add_video_to_playlist"):
            result = publish_weekly_batch._publish_video(service, video_path, {"title": "T", "scene": "cat"})

        assert result == "vid1"

    def test_mismatched_privacy_status_is_logged_but_not_fatal(self, tmp_path, monkeypatch, caplog):
        self._service_with_duration_ok(monkeypatch)
        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid1", "status": {"privacyStatus": "private"}}
        video_path = tmp_path / "v.mp4"
        video_path.write_bytes(b"x")

        with patch("utils.playlist_manager.add_video_to_playlist"), caplog.at_level("ERROR"):
            result = publish_weekly_batch._publish_video(service, video_path, {"title": "T"})

        assert result == "vid1"
        assert any("privacyStatus" in rec.message for rec in caplog.records)


class TestPublishVideoMediaBranches:
    def _service_with_duration_ok(self, monkeypatch, duration=30.0):
        monkeypatch.setattr(publish_weekly_batch.ffmpeg_helpers, "get_video_duration", lambda p: duration)

    def test_applies_thumbnail_when_present(self, tmp_path, monkeypatch):
        self._service_with_duration_ok(monkeypatch)
        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid1", "status": {"privacyStatus": "public"}}
        video_path = tmp_path / "v.mp4"
        video_path.write_bytes(b"x")
        thumb = tmp_path / "thumb.png"
        thumb.write_bytes(b"png")
        meta = {"title": "T", "_meta_dir": str(tmp_path), "thumbnail": "thumb.png"}

        with (
            patch("utils.playlist_manager.add_video_to_playlist"),
            patch("scripts.publish_weekly_batch._meta_path", return_value=thumb),
        ):
            publish_weekly_batch._publish_video(service, video_path, meta)

        service.thumbnails().set.assert_called_once()

    def test_thumbnail_failure_is_logged_not_fatal(self, tmp_path, monkeypatch, caplog):
        self._service_with_duration_ok(monkeypatch)
        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid1", "status": {"privacyStatus": "public"}}
        service.thumbnails().set().execute.side_effect = Exception("403 Forbidden")
        video_path = tmp_path / "v.mp4"
        video_path.write_bytes(b"x")
        thumb = tmp_path / "thumb.png"
        thumb.write_bytes(b"png")

        with (
            patch("utils.playlist_manager.add_video_to_playlist"),
            patch("scripts.publish_weekly_batch._meta_path", return_value=thumb),
            caplog.at_level("WARNING"),
        ):
            result = publish_weekly_batch._publish_video(service, video_path, {"title": "T"})

        assert result == "vid1"
        assert any("thumbnail" in rec.message.lower() for rec in caplog.records)

    def test_applies_caption_vtt(self, tmp_path, monkeypatch):
        self._service_with_duration_ok(monkeypatch)
        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid1", "status": {"privacyStatus": "public"}}
        video_path = tmp_path / "v.mp4"
        video_path.write_bytes(b"x")
        caption = tmp_path / "cap.vtt"
        caption.write_text("WEBVTT\n", encoding="utf-8")

        with (
            patch("utils.playlist_manager.add_video_to_playlist"),
            patch("utils.youtube_post_upload._meta_path", return_value=caption),
        ):
            publish_weekly_batch._publish_video(service, video_path, {"title": "T"})

        service.captions().insert.assert_called_once()

    def test_applies_caption_ass(self, tmp_path, monkeypatch):
        self._service_with_duration_ok(monkeypatch)
        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid1", "status": {"privacyStatus": "public"}}
        video_path = tmp_path / "v.mp4"
        video_path.write_bytes(b"x")
        caption = tmp_path / "cap.ass"
        caption.write_text("[Events]\n", encoding="utf-8")

        with (
            patch("utils.playlist_manager.add_video_to_playlist"),
            patch("utils.youtube_post_upload._meta_path", return_value=caption),
        ):
            publish_weekly_batch._publish_video(service, video_path, {"title": "T"})

        service.captions().insert.assert_called_once()

    def test_caption_failure_is_logged_not_fatal(self, tmp_path, monkeypatch, caplog):
        self._service_with_duration_ok(monkeypatch)
        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid1", "status": {"privacyStatus": "public"}}
        service.captions().insert().execute.side_effect = Exception("caption boom")
        video_path = tmp_path / "v.mp4"
        video_path.write_bytes(b"x")
        caption = tmp_path / "cap.srt"
        caption.write_text("1\n", encoding="utf-8")

        with (
            patch("utils.playlist_manager.add_video_to_playlist"),
            patch("utils.youtube_post_upload._meta_path", return_value=caption),
            caplog.at_level("WARNING"),
        ):
            result = publish_weekly_batch._publish_video(service, video_path, {"title": "T"})

        assert result == "vid1"
        assert any("legenda" in rec.message.lower() for rec in caplog.records)

    def test_playlist_add_failure_is_logged_not_fatal(self, tmp_path, monkeypatch, caplog):
        self._service_with_duration_ok(monkeypatch)
        service = MagicMock()
        service.videos().insert().execute.return_value = {"id": "vid1", "status": {"privacyStatus": "public"}}
        video_path = tmp_path / "v.mp4"
        video_path.write_bytes(b"x")

        with (
            patch("utils.youtube_post_upload.add_video_to_playlist", side_effect=Exception("pl boom")),
            caplog.at_level("WARNING"),
        ):
            result = publish_weekly_batch._publish_video(service, video_path, {"title": "T", "mood": "relax"})

        assert result == "vid1"
        assert any("playlist" in rec.message.lower() for rec in caplog.records)


class TestMain:
    def test_no_service_returns_1(self, monkeypatch):
        monkeypatch.setattr(publish_weekly_batch, "configure_logging", lambda: None)
        monkeypatch.setattr(publish_weekly_batch, "get_youtube_service", MagicMock(side_effect=Exception("auth boom")))
        assert publish_weekly_batch.main() == 1

    def test_no_unpublished_returns_0(self, tmp_path, monkeypatch):
        monkeypatch.setattr(publish_weekly_batch, "configure_logging", lambda: None)
        monkeypatch.setattr(publish_weekly_batch, "get_youtube_service", lambda: MagicMock())
        monkeypatch.setattr(publish_weekly_batch, "OUTPUT_DIR", tmp_path)  # vazio
        assert publish_weekly_batch.main() == 0

    def test_publishes_one_video(self, tmp_path, monkeypatch):
        monkeypatch.setattr(publish_weekly_batch, "configure_logging", lambda: None)
        service = MagicMock()
        monkeypatch.setattr(publish_weekly_batch, "get_youtube_service", lambda: service)
        monkeypatch.setattr(publish_weekly_batch, "OUTPUT_DIR", tmp_path)
        monkeypatch.setattr(publish_weekly_batch.time, "sleep", lambda s: None)
        vp = _write_video(tmp_path, "liquid_wire_short_1", {"title": "A"})
        monkeypatch.setattr(publish_weekly_batch, "_publish_video", lambda *a, **k: "vid1")
        assert publish_weekly_batch.main() == 0
        saved = json.loads(vp.with_suffix(".json").read_text(encoding="utf-8"))
        assert saved["published"] is True
        assert saved["video_id"] == "vid1"

    def test_publish_video_returns_none_increments_attempts(self, tmp_path, monkeypatch):
        monkeypatch.setattr(publish_weekly_batch, "configure_logging", lambda: None)
        service = MagicMock()
        monkeypatch.setattr(publish_weekly_batch, "get_youtube_service", lambda: service)
        monkeypatch.setattr(publish_weekly_batch, "OUTPUT_DIR", tmp_path)
        monkeypatch.setattr(publish_weekly_batch.time, "sleep", lambda s: None)
        vp = _write_video(tmp_path, "liquid_wire_short_1", {"title": "A"})
        monkeypatch.setattr(publish_weekly_batch, "_publish_video", lambda *a, **k: None)
        assert publish_weekly_batch.main() == 0
        saved = json.loads(vp.with_suffix(".json").read_text(encoding="utf-8"))
        assert saved.get("publish_attempts") == 1

    def test_publish_video_raises_increments_attempts(self, tmp_path, monkeypatch):
        monkeypatch.setattr(publish_weekly_batch, "configure_logging", lambda: None)
        service = MagicMock()
        monkeypatch.setattr(publish_weekly_batch, "get_youtube_service", lambda: service)
        monkeypatch.setattr(publish_weekly_batch, "OUTPUT_DIR", tmp_path)
        monkeypatch.setattr(publish_weekly_batch.time, "sleep", lambda s: None)
        vp = _write_video(tmp_path, "liquid_wire_short_1", {"title": "A"})
        monkeypatch.setattr(publish_weekly_batch, "_publish_video", MagicMock(side_effect=RuntimeError("boom")))
        monkeypatch.setattr(publish_weekly_batch, "log_exception_to_file", lambda *a, **k: None)
        assert publish_weekly_batch.main() == 0
        saved = json.loads(vp.with_suffix(".json").read_text(encoding="utf-8"))
        assert saved.get("publish_attempts") == 1

    def test_skips_videos_at_max_attempts(self, tmp_path, monkeypatch):
        monkeypatch.setattr(publish_weekly_batch, "OUTPUT_DIR", tmp_path)
        _write_video(
            tmp_path,
            "liquid_wire_short_1",
            {"title": "A", "publish_attempts": publish_weekly_batch._MAX_PUBLISH_ATTEMPTS},
        )
        assert publish_weekly_batch._find_unpublished_videos() == []
