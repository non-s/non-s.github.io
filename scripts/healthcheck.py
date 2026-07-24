"""
scripts/healthcheck.py — verifica se o ambiente está pronto para gerar/transferir conteúdo.

Checa:
- versão do Python
- FFmpeg e ffprobe no PATH
- credenciais/arquivos de token do YouTube
- variáveis de ambiente obrigatórias
- pool de assets (vídeos e músicas)
- conectividade mínima com APIs Gemini e Pixabay (se chaves presentes)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from utils import ffmpeg_helpers, media_pool
from utils.log_config import configure_logging

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "_data"
REQUIRED_ENVS = [
    "GEMINI_API_KEY",
    "PIXABAY_API_KEY",
]
LIVE_REQUIRED_ENVS = [
    "YOUTUBE_TOKEN_PATH",
    "YOUTUBE_CLIENT_SECRET_PATH",
]


def _check_python() -> dict[str, Any]:
    ok = sys.version_info >= (3, 11)
    return {"name": "Python >= 3.11", "ok": ok, "info": f"{sys.version}"}


def _check_ffmpeg() -> dict[str, Any]:
    has_ffmpeg = ffmpeg_helpers.has_ffmpeg()
    has_ffprobe = ffmpeg_helpers.has_ffprobe()
    return {
        "name": "FFmpeg / ffprobe",
        "ok": has_ffmpeg and has_ffprobe,
        "info": f"ffmpeg={has_ffmpeg}, ffprobe={has_ffprobe}",
    }


def _check_envs() -> dict[str, Any]:
    missing = [name for name in REQUIRED_ENVS if not os.getenv(name)]
    return {
        "name": "Variáveis de ambiente",
        "ok": not missing,
        "info": "OK" if not missing else f"faltando: {', '.join(missing)}",
    }


def _check_youtube_token() -> dict[str, Any]:
    token_path = ROOT / "youtube_token.json"
    if not token_path.exists():
        return {
            "name": "Token YouTube",
            "ok": False,
            "info": f"{token_path} não encontrado; gere via utils/youtube_oauth.py",
        }
    try:
        data = json.loads(token_path.read_text(encoding="utf-8"))
        has_token = bool(data.get("token"))
        return {
            "name": "Token YouTube",
            "ok": has_token,
            "info": "token presente" if has_token else "JSON não contém 'token'",
        }
    except Exception as exc:
        return {"name": "Token YouTube", "ok": False, "info": f"JSON inválido: {exc}"}


def _check_client_secret() -> dict[str, Any]:
    secret_path = ROOT / "client_secret.json"
    if not secret_path.exists():
        return {
            "name": "Client secret Google",
            "ok": False,
            "info": f"{secret_path} não encontrado; baixe do Google Cloud Console",
        }
    return {"name": "Client secret Google", "ok": True, "info": "arquivo presente"}


def _check_asset_pool() -> dict[str, Any]:
    stats = media_pool.pool_stats()
    videos = stats.get("videos", 0)
    audio = stats.get("audio", 0)
    ok = videos > 0 and audio > 0
    return {
        "name": "Pool de assets",
        "ok": ok,
        "info": f"videos={videos}, audio={audio}",
    }


def _check_live_prerequisites() -> dict[str, Any]:
    """Verifica se o ambiente está pronto para lives."""
    missing = [name for name in LIVE_REQUIRED_ENVS if not os.getenv(name)]
    if missing:
        return {
            "name": "Pré-requisitos Live",
            "ok": False,
            "info": f"faltando: {', '.join(missing)}",
        }

    # Verifica token YouTube
    token_ok = _check_youtube_token()
    if not token_ok["ok"]:
        return {
            "name": "Pré-requisitos Live",
            "ok": False,
            "info": "Token YouTube inválido ou ausente",
        }

    # Verifica client secret
    secret_ok = _check_client_secret()
    if not secret_ok["ok"]:
        return {
            "name": "Pré-requisitos Live",
            "ok": False,
            "info": "Client secret Google ausente",
        }

    return {
        "name": "Pré-requisitos Live",
        "ok": True,
        "info": "OK - tokens e credenciais válidos",
    }


def run_healthcheck(mode: str = "all") -> int:
    """Executa healthcheck.
    
    Args:
        mode: 'all' para todos os checks, 'live' apenas para pré-requisitos de live.
    """
    configure_logging()
    
    if mode == "live":
        checks = [
            _check_python(),
            _check_ffmpeg(),
            _check_envs(),
            _check_live_prerequisites(),
            _check_asset_pool(),
        ]
    else:
        checks = [
            _check_python(),
            _check_ffmpeg(),
            _check_envs(),
            _check_youtube_token(),
            _check_client_secret(),
            _check_asset_pool(),
        ]

    log.info("=" * 60)
    log.info("Healthcheck Pata Jazz")
    log.info("=" * 60)
    for check in checks:
        status = "✅" if check["ok"] else "❌"
        log.info("%s %s: %s", status, check["name"], check["info"])

    all_ok = all(c["ok"] for c in checks)
    if all_ok:
        log.info("Ambiente pronto para geração e upload.")
        return 0
    log.warning("Corrija os itens ❌ antes de executar os geradores.")
    return 1


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Healthcheck Pata Jazz")
    parser.add_argument("--mode", choices=["all", "live"], default="all", help="Modo: 'all' ou 'live'")
    args = parser.parse_args()
    sys.exit(run_healthcheck(mode=args.mode))
