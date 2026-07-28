"""Testes para o scaffolding de cross-posting (upload_tiktok.py / upload_reels.py).

Cobre os caminhos de "credenciais ausentes" (no-op) e parsing de argumentos.
Os uploads reais sao stubs (NotImplementedError capturado internamente), entao
estes testes garantem que o workflow de cross-posting roda em CI sem credenciais
sem falhar e sem tentar nenhuma chamada HTTP real.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import upload_reels
import upload_tiktok


def _no_env(key: str):
    """Factory para patch de os.environ.get que retorna None para `key`."""
    def _get(k, default=None):
        return None if k == key else default
    return _get


def _write_video(output_dir: Path, stem: str, meta: dict) -> Path:
    video_path = output_dir / f"{stem}.mp4"
    video_path.write_bytes(b"fake video bytes")
    (output_dir / f"{stem}.json").write_text(json.dumps(meta), encoding="utf-8")
    return video_path


class TestUploadTiktokNotConfigured:
    def test_returns_none_without_access_token(self, caplog):
        with patch.dict("os.environ", {}, clear=False), \
             patch("os.environ.get", _no_env("TIKTOK_ACCESS_TOKEN")):
            with caplog.at_level("INFO"):
                result = upload_tiktok.upload_to_tiktok(Path("v.mp4"), {"title": "T"})
        assert result is None
        assert any("TIKTOK_ACCESS_TOKEN" in rec.message for rec in caplog.records)

    def test_returns_none_when_credentials_dict_empty(self):
        result = upload_tiktok.upload_to_tiktok(Path("v.mp4"), {"title": "T"}, credentials={})
        assert result is None

    def test_scaffolding_message_when_token_present(self, caplog, monkeypatch):
        monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "fake-token")
        meta = {"title": "T", "description": "d", "hashtags": ["cat"]}
        with caplog.at_level("INFO"):
            result = upload_tiktok.upload_to_tiktok(Path("v.mp4"), meta)
        assert result is None
        assert any("scaffolding" in rec.message.lower() for rec in caplog.records)


class TestUploadReelsNotConfigured:
    def test_returns_none_without_access_token(self, caplog):
        with patch.dict("os.environ", {}, clear=False), \
             patch("os.environ.get", _no_env("INSTAGRAM_ACCESS_TOKEN")):
            with caplog.at_level("INFO"):
                result = upload_reels.upload_to_reels(Path("v.mp4"), {"title": "T"})
        assert result is None
        assert any("INSTAGRAM_ACCESS_TOKEN" in rec.message for rec in caplog.records)

    def test_returns_none_when_credentials_dict_empty(self):
        result = upload_reels.upload_to_reels(Path("v.mp4"), {"title": "T"}, credentials={})
        assert result is None

    def test_scaffolding_message_when_token_present(self, caplog, monkeypatch):
        monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "fake-token")
        meta = {"title": "T", "description": "d", "hashtags": ["cat"]}
        with caplog.at_level("INFO"):
            result = upload_reels.upload_to_reels(Path("v.mp4"), meta)
        assert result is None
        assert any("scaffolding" in rec.message.lower() for rec in caplog.records)


class TestCrossPostAllUnpublished:
    def test_tiktok_no_unpublished_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.publish_weekly_batch.OUTPUT_DIR", tmp_path)
        assert upload_tiktok.cross_post_all_unpublished() == []

    def test_tiktok_unpublished_without_token_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.publish_weekly_batch.OUTPUT_DIR", tmp_path)
        _write_video(tmp_path, "pata_jazz_short_1", {"title": "A"})
        with patch.dict("os.environ", {}, clear=False), \
             patch("os.environ.get", _no_env("TIKTOK_ACCESS_TOKEN")):
            assert upload_tiktok.cross_post_all_unpublished() == []

    def test_reels_no_unpublished_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.publish_weekly_batch.OUTPUT_DIR", tmp_path)
        assert upload_reels.cross_post_all_unpublished() == []

    def test_reels_unpublished_without_token_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.publish_weekly_batch.OUTPUT_DIR", tmp_path)
        _write_video(tmp_path, "pata_jazz_short_1", {"title": "A"})
        with patch.dict("os.environ", {}, clear=False), \
             patch("os.environ.get", _no_env("INSTAGRAM_ACCESS_TOKEN")):
            assert upload_reels.cross_post_all_unpublished() == []


class TestTiktokArgParsing:
    def test_all_flag_runs_cross_post(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["upload_tiktok.py", "--all"])
        with patch("upload_tiktok.configure_logging"), \
             patch("upload_tiktok.cross_post_all_unpublished", return_value=[]) as mock_cross:
            assert upload_tiktok.main() == 0
        mock_cross.assert_called_once()

    def test_missing_video_and_meta_returns_1(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["upload_tiktok.py"])
        with patch("upload_tiktok.configure_logging"):
            assert upload_tiktok.main() == 1

    def test_missing_video_file_returns_1(self, tmp_path, monkeypatch):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({"title": "T"}), encoding="utf-8")
        argv = ["upload_tiktok.py", "--video", str(tmp_path / "nope.mp4"), "--meta", str(meta_path)]
        monkeypatch.setattr("sys.argv", argv)
        with patch("upload_tiktok.configure_logging"):
            assert upload_tiktok.main() == 1

    def test_invalid_meta_json_returns_1(self, tmp_path, monkeypatch):
        video_path = tmp_path / "v.mp4"
        video_path.write_bytes(b"x")
        meta_path = tmp_path / "meta.json"
        meta_path.write_text("not json{{{", encoding="utf-8")
        argv = ["upload_tiktok.py", "--video", str(video_path), "--meta", str(meta_path)]
        monkeypatch.setattr("sys.argv", argv)
        with patch("upload_tiktok.configure_logging"):
            assert upload_tiktok.main() == 1

    def test_valid_args_without_token_returns_0(self, tmp_path, monkeypatch):
        video_path = tmp_path / "v.mp4"
        video_path.write_bytes(b"x")
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({"title": "T"}), encoding="utf-8")
        argv = ["upload_tiktok.py", "--video", str(video_path), "--meta", str(meta_path)]
        monkeypatch.setattr("sys.argv", argv)
        with patch("upload_tiktok.configure_logging"), \
             patch.dict("os.environ", {}, clear=False), \
             patch("os.environ.get", _no_env("TIKTOK_ACCESS_TOKEN")):
            assert upload_tiktok.main() == 0


class TestReelsArgParsing:
    def test_all_flag_runs_cross_post(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["upload_reels.py", "--all"])
        with patch("upload_reels.configure_logging"), \
             patch("upload_reels.cross_post_all_unpublished", return_value=[]) as mock_cross:
            assert upload_reels.main() == 0
        mock_cross.assert_called_once()

    def test_missing_video_and_meta_returns_1(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["upload_reels.py"])
        with patch("upload_reels.configure_logging"):
            assert upload_reels.main() == 1

    def test_missing_video_file_returns_1(self, tmp_path, monkeypatch):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({"title": "T"}), encoding="utf-8")
        argv = ["upload_reels.py", "--video", str(tmp_path / "nope.mp4"), "--meta", str(meta_path)]
        monkeypatch.setattr("sys.argv", argv)
        with patch("upload_reels.configure_logging"):
            assert upload_reels.main() == 1

    def test_invalid_meta_json_returns_1(self, tmp_path, monkeypatch):
        video_path = tmp_path / "v.mp4"
        video_path.write_bytes(b"x")
        meta_path = tmp_path / "meta.json"
        meta_path.write_text("not json{{{", encoding="utf-8")
        argv = ["upload_reels.py", "--video", str(video_path), "--meta", str(meta_path)]
        monkeypatch.setattr("sys.argv", argv)
        with patch("upload_reels.configure_logging"):
            assert upload_reels.main() == 1

    def test_valid_args_without_token_returns_0(self, tmp_path, monkeypatch):
        video_path = tmp_path / "v.mp4"
        video_path.write_bytes(b"x")
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({"title": "T"}), encoding="utf-8")
        argv = ["upload_reels.py", "--video", str(video_path), "--meta", str(meta_path)]
        monkeypatch.setattr("sys.argv", argv)
        with patch("upload_reels.configure_logging"), \
             patch.dict("os.environ", {}, clear=False), \
             patch("os.environ.get", _no_env("INSTAGRAM_ACCESS_TOKEN")):
            assert upload_reels.main() == 0
