"""Testes para cross-posting TikTok (browser automation) e Reels (scaffolding).

TikTok: testa o caminho de credenciais ausentes (no-op) e arg parsing.
Os testes nao abrem browser nem fazem login real — mockam Playwright.
Reels: scaffolding com env vars, mesma estrutura.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import upload_reels
import upload_tiktok


def _no_env(*keys: str):
    """Factory para patch de os.environ.get que retorna None para as keys."""
    import os
    def _get(k, default=None):
        if k in keys:
            return None
        if k in os.environ:
            return os.environ[k]
        return default
    return _get


def _write_video(output_dir: Path, stem: str, meta: dict) -> Path:
    video_path = output_dir / f"{stem}.mp4"
    video_path.write_bytes(b"fake video bytes")
    (output_dir / f"{stem}.json").write_text(json.dumps(meta), encoding="utf-8")
    return video_path


class TestUploadTiktokNotConfigured:
    def test_returns_none_without_credentials(self, caplog):
        with patch.dict("os.environ", {"TIKTOK_STATE_PATH": "non_existent_state.json"}, clear=False), \
             patch("os.environ.get", _no_env("TIKTOK_EMAIL", "TIKTOK_PASSWORD")):
            with caplog.at_level("INFO"):
                result = upload_tiktok.upload_to_tiktok(Path("v.mp4"), {"title": "T"})
        assert result is None
        assert any("TIKTOK_EMAIL" in rec.message or "TIKTOK_PASSWORD" in rec.message for rec in caplog.records)

    def test_returns_none_with_empty_email(self, caplog):
        with patch.dict(
            "os.environ",
            {"TIKTOK_STATE_PATH": "non_existent_state.json", "TIKTOK_EMAIL": "", "TIKTOK_PASSWORD": "x"},
            clear=False,
        ):
            with caplog.at_level("INFO"):
                result = upload_tiktok.upload_to_tiktok(Path("v.mp4"), {"title": "T"})
        assert result is None

    def test_returns_none_with_empty_password(self, caplog):
        with patch.dict(
            "os.environ",
            {"TIKTOK_STATE_PATH": "non_existent_state.json", "TIKTOK_EMAIL": "x@x.com", "TIKTOK_PASSWORD": ""},
            clear=False,
        ):
            with caplog.at_level("INFO"):
                result = upload_tiktok.upload_to_tiktok(
                    Path("v.mp4"), {"title": "T"}
                )
        assert result is None

    def test_returns_none_when_video_not_found(self, caplog):
        with patch.dict("os.environ", {"TIKTOK_EMAIL": "x@x.com", "TIKTOK_PASSWORD": "x"}, clear=False):
            with caplog.at_level("ERROR"):
                result = upload_tiktok.upload_to_tiktok(Path("nonexistent.mp4"), {"title": "T"})
        assert result is None


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


class TestFindPendingTiktokVideos:
    """_find_pending_tiktok_videos: usa criterio proprio (tiktok_url), nao
    o filtro published/video_id do YouTube (bug real corrigido - ver
    docstring da funcao)."""

    def test_video_without_tiktok_url_is_pending(self, tmp_path, monkeypatch):
        monkeypatch.setattr(upload_tiktok, "OUTPUT_DIR", tmp_path)
        _write_video(tmp_path, "pata_jazz_short_1", {"title": "A"})

        result = upload_tiktok._find_pending_tiktok_videos()

        assert len(result) == 1
        assert result[0][1]["title"] == "A"

    def test_video_with_tiktok_url_is_excluded(self, tmp_path, monkeypatch):
        monkeypatch.setattr(upload_tiktok, "OUTPUT_DIR", tmp_path)
        _write_video(tmp_path, "pata_jazz_short_1", {"title": "A", "tiktok_url": "https://tiktok.com/x"})

        assert upload_tiktok._find_pending_tiktok_videos() == []

    def test_video_published_on_youtube_but_not_tiktok_is_still_pending(self, tmp_path, monkeypatch):
        """O bug corrigido: um video ja publicado no YouTube (video_id/
        published setados pelo lote semanal) NAO deve ser pulado pelo
        cross-posting do TikTok so por causa disso - sao publicacoes
        independentes em plataformas diferentes."""
        monkeypatch.setattr(upload_tiktok, "OUTPUT_DIR", tmp_path)
        _write_video(tmp_path, "pata_jazz_short_1", {
            "title": "A", "published": True, "video_id": "yt123",
        })

        result = upload_tiktok._find_pending_tiktok_videos()

        assert len(result) == 1
        assert result[0][1]["video_id"] == "yt123"

    def test_skips_video_missing_mp4_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(upload_tiktok, "OUTPUT_DIR", tmp_path)
        (tmp_path / "pata_jazz_short_1.json").write_text(json.dumps({"title": "A"}), encoding="utf-8")

        assert upload_tiktok._find_pending_tiktok_videos() == []

    def test_skips_corrupted_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr(upload_tiktok, "OUTPUT_DIR", tmp_path)
        (tmp_path / "pata_jazz_short_1.mp4").write_bytes(b"x")
        (tmp_path / "pata_jazz_short_1.json").write_text("not json{{{", encoding="utf-8")

        assert upload_tiktok._find_pending_tiktok_videos() == []


class TestCrossPostAllUnpublished:
    def test_tiktok_no_unpublished_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("upload_tiktok.OUTPUT_DIR", tmp_path)
        assert upload_tiktok.cross_post_all_unpublished() == []

    def test_tiktok_unpublished_without_credentials_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("upload_tiktok.OUTPUT_DIR", tmp_path)
        _write_video(tmp_path, "pata_jazz_short_1", {"title": "A"})
        with patch.dict("os.environ", {}, clear=False), \
             patch("os.environ.get", _no_env("TIKTOK_EMAIL", "TIKTOK_PASSWORD")):
            assert upload_tiktok.cross_post_all_unpublished() == []

    def test_tiktok_stops_after_max_consecutive_failures(self, tmp_path, monkeypatch):
        """Se o login/sessao esta quebrado, cada video falharia do mesmo
        jeito - continuar tentando so aumenta o risco de a conta ser
        bloqueada por excesso de tentativas. Aborta apos N falhas seguidas
        em vez de percorrer o lote inteiro."""
        monkeypatch.setattr("upload_tiktok.OUTPUT_DIR", tmp_path)
        for i in range(5):
            _write_video(tmp_path, f"pata_jazz_short_{i}", {"title": f"V{i}"})

        with patch("upload_tiktok.upload_to_tiktok", return_value=None) as mock_upload, \
             patch("upload_tiktok.time.sleep"):
            result = upload_tiktok.cross_post_all_unpublished()

        assert result == []
        assert mock_upload.call_count == upload_tiktok._MAX_CONSECUTIVE_FAILURES

    def test_tiktok_failure_counter_resets_on_success(self, tmp_path, monkeypatch):
        monkeypatch.setattr("upload_tiktok.OUTPUT_DIR", tmp_path)
        for i in range(3):
            _write_video(tmp_path, f"pata_jazz_short_{i}", {"title": f"V{i}"})

        with patch(
            "upload_tiktok.upload_to_tiktok",
            side_effect=[None, "https://tiktok.com/@x/video/1", None],
        ) as mock_upload, patch("upload_tiktok.time.sleep"):
            result = upload_tiktok.cross_post_all_unpublished()

        # 1 falha, depois sucesso reseta o contador, depois +1 falha -
        # nunca atinge _MAX_CONSECUTIVE_FAILURES (2) seguidas, entao os 3 rodam.
        assert mock_upload.call_count == 3
        assert result == ["https://tiktok.com/@x/video/1"]

    def test_tiktok_marks_metadata_with_url_on_success(self, tmp_path, monkeypatch):
        monkeypatch.setattr("upload_tiktok.OUTPUT_DIR", tmp_path)
        video_path = _write_video(tmp_path, "pata_jazz_short_1", {"title": "A"})

        with patch("upload_tiktok.upload_to_tiktok", return_value="https://tiktok.com/@x/video/1"), \
             patch("upload_tiktok.time.sleep"):
            result = upload_tiktok.cross_post_all_unpublished()

        assert result == ["https://tiktok.com/@x/video/1"]
        meta = json.loads(video_path.with_suffix(".json").read_text(encoding="utf-8"))
        assert meta["tiktok_url"] == "https://tiktok.com/@x/video/1"

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

    def test_valid_args_without_credentials_returns_1(self, tmp_path, monkeypatch):
        """Regressao: main() sempre retornava 0 mesmo quando upload_to_tiktok
        falhava (ex.: sem credenciais) - um workflow de CI nunca saberia que
        o cross-post nao aconteceu. Sem credenciais, upload_to_tiktok
        retorna None e main() precisa propagar isso como falha (exit 1)."""
        video_path = tmp_path / "v.mp4"
        video_path.write_bytes(b"x")
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({"title": "T"}), encoding="utf-8")
        argv = ["upload_tiktok.py", "--video", str(video_path), "--meta", str(meta_path)]
        monkeypatch.setattr("sys.argv", argv)
        with patch("upload_tiktok.configure_logging"), \
             patch.dict("os.environ", {}, clear=False), \
             patch("os.environ.get", _no_env("TIKTOK_EMAIL", "TIKTOK_PASSWORD")):
            assert upload_tiktok.main() == 1

    def test_valid_args_with_successful_upload_returns_0(self, tmp_path, monkeypatch):
        video_path = tmp_path / "v.mp4"
        video_path.write_bytes(b"x")
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({"title": "T"}), encoding="utf-8")
        argv = ["upload_tiktok.py", "--video", str(video_path), "--meta", str(meta_path)]
        monkeypatch.setattr("sys.argv", argv)
        with patch("upload_tiktok.configure_logging"), \
             patch("upload_tiktok.upload_to_tiktok", return_value="https://tiktok.com/@x/video/1"):
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
