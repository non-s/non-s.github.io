"""Testes básicos para o novo módulo de healthcheck."""

from __future__ import annotations

from unittest.mock import patch

import scripts.healthcheck as healthcheck


def test_check_python_ok():
    result = healthcheck._check_python()
    assert result["ok"] is True
    assert "Python" in result["name"]


def test_check_ffmpeg_missing():
    with (
        patch("utils.ffmpeg_helpers.has_ffmpeg", return_value=False),
        patch("utils.ffmpeg_helpers.has_ffprobe", return_value=False),
    ):
        result = healthcheck._check_ffmpeg()
        assert result["ok"] is False
        assert "ffprobe" in result["info"]


def test_check_envs_missing():
    with patch.dict("os.environ", {}, clear=True):
        result = healthcheck._check_envs()
        assert result["ok"] is False
        assert "GEMINI_API_KEY" in result["info"]


def test_check_envs_ok():
    with patch.dict(
        "os.environ",
        {
            "GEMINI_API_KEY": "x",
            "PIXABAY_API_KEY": "y",
            "JAMENDO_CLIENT_ID": "z",
        },
    ):
        result = healthcheck._check_envs()
        assert result["ok"] is True


def test_check_youtube_token_missing():
    with patch("scripts.healthcheck._token_path", return_value="/nonexistent/youtube_token.json"):
        result = healthcheck._check_youtube_token()
        assert result["ok"] is False


def test_check_client_secret_present():
    with patch("scripts.healthcheck._client_secrets_path", return_value="client_secret.json"):
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


def test_check_pool_drift_ok_above_thresholds():
    with patch("utils.media_pool.pool_stats", return_value={"videos": 60, "audio": 40}):
        result = healthcheck.check_pool_drift()
        assert result["ok"] is True
        assert result["info"] == "OK"


def test_check_pool_drift_warns_low_videos():
    with patch("utils.media_pool.pool_stats", return_value={"videos": 10, "audio": 40}):
        result = healthcheck.check_pool_drift()
        assert result["ok"] is False
        assert "videos=10<20" in result["info"]


def test_check_pool_drift_warns_low_audio():
    with patch("utils.media_pool.pool_stats", return_value={"videos": 60, "audio": 5}):
        result = healthcheck.check_pool_drift()
        assert result["ok"] is False
        assert "audio=5<10" in result["info"]


def test_check_pool_drift_warns_both_low():
    with patch("utils.media_pool.pool_stats", return_value={"videos": 0, "audio": 0}):
        result = healthcheck.check_pool_drift()
        assert result["ok"] is False
        assert "videos=0<20" in result["info"]
        assert "audio=0<10" in result["info"]


def test_run_healthcheck_returns_0_when_all_ok():
    with (
        patch.object(healthcheck, "_check_python", return_value={"name": "py", "ok": True, "info": ""}),
        patch.object(healthcheck, "_check_ffmpeg", return_value={"name": "ff", "ok": True, "info": ""}),
        patch.object(healthcheck, "_check_envs", return_value={"name": "env", "ok": True, "info": ""}),
        patch.object(healthcheck, "_check_youtube_token", return_value={"name": "yt", "ok": True, "info": ""}),
        patch.object(healthcheck, "_check_client_secret", return_value={"name": "cs", "ok": True, "info": ""}),
        patch.object(healthcheck, "_check_asset_pool", return_value={"name": "pool", "ok": True, "info": ""}),
        patch.object(healthcheck, "check_pool_drift", return_value={"name": "drift", "ok": True, "info": ""}),
    ):
        assert healthcheck.run_healthcheck() == 0


def test_run_healthcheck_returns_1_when_any_fails():
    with (
        patch.object(healthcheck, "_check_python", return_value={"name": "py", "ok": True, "info": ""}),
        patch.object(healthcheck, "_check_ffmpeg", return_value={"name": "ff", "ok": False, "info": ""}),
        patch.object(healthcheck, "_check_envs", return_value={"name": "env", "ok": True, "info": ""}),
        patch.object(healthcheck, "_check_youtube_token", return_value={"name": "yt", "ok": True, "info": ""}),
        patch.object(healthcheck, "_check_client_secret", return_value={"name": "cs", "ok": True, "info": ""}),
        patch.object(healthcheck, "_check_asset_pool", return_value={"name": "pool", "ok": True, "info": ""}),
        patch.object(healthcheck, "check_pool_drift", return_value={"name": "drift", "ok": True, "info": ""}),
    ):
        assert healthcheck.run_healthcheck() == 1
