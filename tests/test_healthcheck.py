"""Testes básicos para o novo módulo de healthcheck."""

from __future__ import annotations

from unittest.mock import patch

import scripts.healthcheck as healthcheck


def test_check_python_ok():
    result = healthcheck._check_python()
    assert result["ok"] is True
    assert "Python" in result["name"]


def test_check_ffmpeg_missing():
    with patch("utils.ffmpeg_helpers.has_ffmpeg", return_value=False), \
         patch("utils.ffmpeg_helpers.has_ffprobe", return_value=False):
        result = healthcheck._check_ffmpeg()
        assert result["ok"] is False
        assert "ffprobe" in result["info"]


def test_check_envs_missing():
    with patch.dict("os.environ", {}, clear=True):
        result = healthcheck._check_envs()
        assert result["ok"] is False
        assert "GEMINI_API_KEY" in result["info"]


def test_check_envs_ok():
    with patch.dict("os.environ", {"GEMINI_API_KEY": "x", "PIXABAY_API_KEY": "y"}):
        result = healthcheck._check_envs()
        assert result["ok"] is True


def test_check_youtube_token_missing():
    class FakePath:
        def __truediv__(self, other):
            return self
        def exists(self):
            return False
        def read_text(self, **kwargs):
            return ""
        def __str__(self):
            return "_data/youtube_token.json"

    with patch("scripts.healthcheck.DATA_DIR", FakePath()):
        result = healthcheck._check_youtube_token()
        assert result["ok"] is False


def test_check_client_secret_present():
    class FakePath:
        def __truediv__(self, other):
            return self
        def exists(self):
            return True
        def __str__(self):
            return "_data/client_secret.json"

    with patch("scripts.healthcheck.DATA_DIR", FakePath()):
        result = healthcheck._check_client_secret()
        assert result["ok"] is True


def test_check_asset_pool_empty():
    with patch("utils.media_pool.pool_stats", return_value={"videos": 0, "audio": 0}):
        result = healthcheck._check_asset_pool()
        assert result["ok"] is False
        assert "videos=0" in result["info"]


def test_check_asset_pool_ready():
    with patch("utils.media_pool.pool_stats", return_value={"videos": 2, "audio": 1}):
        result = healthcheck._check_asset_pool()
        assert result["ok"] is True


def test_run_healthcheck_returns_0_when_all_ok():
    with patch.object(healthcheck, "_check_python", return_value={"name": "py", "ok": True, "info": ""}), \
         patch.object(healthcheck, "_check_ffmpeg", return_value={"name": "ff", "ok": True, "info": ""}), \
         patch.object(healthcheck, "_check_envs", return_value={"name": "env", "ok": True, "info": ""}), \
         patch.object(healthcheck, "_check_youtube_token", return_value={"name": "yt", "ok": True, "info": ""}), \
         patch.object(healthcheck, "_check_client_secret", return_value={"name": "cs", "ok": True, "info": ""}), \
         patch.object(healthcheck, "_check_asset_pool", return_value={"name": "pool", "ok": True, "info": ""}):
        assert healthcheck.run_healthcheck() == 0


def test_run_healthcheck_returns_1_when_any_fails():
    with patch.object(healthcheck, "_check_python", return_value={"name": "py", "ok": True, "info": ""}), \
         patch.object(healthcheck, "_check_ffmpeg", return_value={"name": "ff", "ok": False, "info": ""}), \
         patch.object(healthcheck, "_check_envs", return_value={"name": "env", "ok": True, "info": ""}), \
         patch.object(healthcheck, "_check_youtube_token", return_value={"name": "yt", "ok": True, "info": ""}), \
         patch.object(healthcheck, "_check_client_secret", return_value={"name": "cs", "ok": True, "info": ""}), \
         patch.object(healthcheck, "_check_asset_pool", return_value={"name": "pool", "ok": True, "info": ""}):
        assert healthcheck.run_healthcheck() == 1
