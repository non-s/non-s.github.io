"""Testes para scripts/publish_weekly_batch.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import scripts.publish_weekly_batch as publish_weekly_batch


def _write_video(output_dir: Path, stem: str, meta: dict) -> Path:
    video_path = output_dir / f"{stem}.mp4"
    video_path.write_bytes(b"fake video bytes")
    (output_dir / f"{stem}.json").write_text(json.dumps(meta), encoding="utf-8")
    return video_path


class TestFindUnpublishedVideos:
    def test_finds_video_without_published_flag(self, tmp_path, monkeypatch):
        monkeypatch.setattr(publish_weekly_batch, "OUTPUT_DIR", tmp_path)
        _write_video(tmp_path, "pata_jazz_short_1", {"title": "A"})

        result = publish_weekly_batch._find_unpublished_videos()

        assert len(result) == 1
        assert result[0][1]["title"] == "A"

    def test_skips_already_published(self, tmp_path, monkeypatch):
        monkeypatch.setattr(publish_weekly_batch, "OUTPUT_DIR", tmp_path)
        _write_video(tmp_path, "pata_jazz_short_1", {"title": "A", "published": True})

        result = publish_weekly_batch._find_unpublished_videos()

        assert result == []

    def test_skips_meta_with_video_id_but_no_published_flag(self, tmp_path, monkeypatch):
        """video_id presente (upload private feito) tambem conta como
        'ja processado', mesmo sem published=True ainda."""
        monkeypatch.setattr(publish_weekly_batch, "OUTPUT_DIR", tmp_path)
        _write_video(tmp_path, "pata_jazz_short_1", {"title": "A", "video_id": "abc123"})

        result = publish_weekly_batch._find_unpublished_videos()

        assert result == []

    def test_skips_meta_without_matching_video_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(publish_weekly_batch, "OUTPUT_DIR", tmp_path)
        (tmp_path / "pata_jazz_short_1.json").write_text(json.dumps({"title": "A"}), encoding="utf-8")

        result = publish_weekly_batch._find_unpublished_videos()

        assert result == []

    def test_skips_corrupted_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr(publish_weekly_batch, "OUTPUT_DIR", tmp_path)
        (tmp_path / "pata_jazz_short_1.mp4").write_bytes(b"x")
        (tmp_path / "pata_jazz_short_1.json").write_text("not json{{{", encoding="utf-8")

        result = publish_weekly_batch._find_unpublished_videos()

        assert result == []

    def test_orders_by_modification_time(self, tmp_path, monkeypatch):
        monkeypatch.setattr(publish_weekly_batch, "OUTPUT_DIR", tmp_path)
        _write_video(tmp_path, "pata_jazz_short_2", {"title": "second"})
        import time
        time.sleep(0.01)
        _write_video(tmp_path, "pata_jazz_short_1", {"title": "first_by_mtime"})

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

        with patch("utils.playlist_manager.add_video_to_playlist"):
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

        with patch("utils.playlist_manager.add_video_to_playlist"):
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
