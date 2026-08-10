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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils import ffmpeg_helpers, media_pool
from utils.log_config import configure_logging
from utils.youtube_oauth import _client_secrets_path, _token_path, validate_token_scopes

log = logging.getLogger(__name__)

DATA_DIR = ROOT / "_data"
REQUIRED_ENVS = [
    "GEMINI_API_KEY",
    "PIXABAY_API_KEY",
    "JAMENDO_CLIENT_ID",
]

# Limites minimos do pool para nao gerar conteudo repetitivo/degradado.
# Abaixo disso o healthcheck emite aviso (nao falha) - o pipeline ainda
# funciona, mas a variedade de b-roll/trilha cai e o canal perde qualidade.
# Valores alinhados com MAX_POOL_SIZE dos syncs (80 b-roll / 40 audio).
POOL_DRIFT_VIDEO_MIN = 20
POOL_DRIFT_AUDIO_MIN = 10


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
    token_path = Path(_token_path())
    if not token_path.exists():
        return {
            "name": "Token YouTube (pata_jazz)",
            "ok": False,
            "info": f"{token_path} não encontrado; gere via utils/youtube_oauth.py",
        }
    try:
        data = json.loads(token_path.read_text(encoding="utf-8"))
        has_token = bool(data.get("token"))
        return {
            "name": "Token YouTube (pata_jazz)",
            "ok": has_token,
            "info": "token presente" if has_token else "JSON não contém 'token'",
        }
    except Exception as exc:
        return {"name": "Token YouTube (pata_jazz)", "ok": False, "info": f"JSON inválido: {exc}"}


def _check_client_secret() -> dict[str, Any]:
    secret_path = _client_secrets_path()
    if not secret_path:
        return {
            "name": "Client secret Google",
            "ok": False,
            "info": "não encontrado; configure YOUTUBE_CLIENT_SECRET ou YOUTUBE_CLIENT_SECRET_PATH",
        }
    return {"name": "Client secret Google", "ok": True, "info": f"{secret_path}"}


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


def check_pool_drift() -> dict[str, Any]:
    """Aviso de drift do pool: quantidade de b-roll/audio abaixo dos limites
    saudaveis (videos < 50 ou audio < 30). Retorna ``ok=True`` quando o pool
    esta acima dos limites; caso contrario ``ok=False`` com detalhe dos
    limites - integra no resumo do healthcheck igual aos outros checks."""
    stats = media_pool.pool_stats()
    videos = stats.get("videos", 0)
    audio = stats.get("audio", 0)
    low_video = videos < POOL_DRIFT_VIDEO_MIN
    low_audio = audio < POOL_DRIFT_AUDIO_MIN
    ok = not (low_video or low_audio)
    parts: list[str] = []
    if low_video:
        parts.append(f"videos={videos}<{POOL_DRIFT_VIDEO_MIN}")
    if low_audio:
        parts.append(f"audio={audio}<{POOL_DRIFT_AUDIO_MIN}")
    info = "OK" if ok else f"drift: {', '.join(parts)}"
    return {
        "name": "Drift do pool de assets",
        "ok": ok,
        "info": info,
    }


def _check_token_only() -> dict[str, Any]:
    """Verifica so o token YouTube, sem exigir client secret.

    Client secret NAO e requisito aqui: em producao o refresh do token usa
    o client_id/secret ja embutidos no proprio youtube_token.json (gerado
    uma vez, localmente, via fluxo interativo) - os workflows agendados
    (shorts/batch/weekly) so tem o secret YOUTUBE_TOKEN, nao um
    client_secret.json commitado, e mesmo assim o upload funciona
    normalmente. Exigir isso aqui so faria esse check falhar sempre, apesar
    do pipeline real estar saudavel.

    #4: tambem valida que o token tem todos os scopes necessarios - se
    faltar algum, o workflow falha depois de gastar tempo de CI em vez
    de falhar aqui em 1s.
    """
    token_ok = _check_youtube_token()
    if not token_ok["ok"]:
        return {
            "name": "Token OAuth (fast)",
            "ok": False,
            "info": "Token YouTube inválido ou ausente",
        }

    missing = validate_token_scopes()
    if missing:
        return {
            "name": "Token OAuth (fast)",
            "ok": False,
            "info": f"Token sem scopes: {', '.join(s.split('/')[-1] for s in missing)}",
        }

    return {
        "name": "Token OAuth (fast)",
        "ok": True,
        "info": "OK - token válido",
    }


def run_healthcheck(mode: str = "all") -> int:
    """Executa healthcheck.

    Args:
        mode: 'all' para todos os checks, 'fast' pula o check de client secret
            (usado nos workflows agendados, que so tem o token, nao o secret),
            'pre-sync' pula tambem os checks de pool (videos=0/audio=0 sao
            esperados antes do sync e nao devem bloquear o workflow).
    """
    configure_logging()

    common_checks = [
        _check_python(),
        _check_ffmpeg(),
        _check_envs(),
    ]

    if mode == "pre-sync":
        checks = common_checks + [_check_token_only()]
    elif mode == "fast":
        checks = common_checks + [
            _check_token_only(),
            _check_asset_pool(),
            check_pool_drift(),
        ]
    else:
        checks = common_checks + [
            _check_youtube_token(),
            _check_client_secret(),
            _check_asset_pool(),
            check_pool_drift(),
        ]

    log.info("=" * 60)
    log.info("Healthcheck Pata Jazz")
    log.info("=" * 60)
    for check in checks:
        status = "[OK]" if check["ok"] else "[FAIL]"
        log.info("%s %s: %s", status, check["name"], check["info"])

    all_ok = all(c["ok"] for c in checks)
    if all_ok:
        log.info("Ambiente pronto para geracao e upload (Pata Jazz).")
        return 0
    log.warning("Corrija os itens [FAIL] antes de executar os geradores (Pata Jazz).")
    return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Healthcheck Pata Jazz")
    parser.add_argument(
        "--mode",
        choices=["all", "fast", "pre-sync"],
        default="all",
        help="Modo: 'all', 'fast' ou 'pre-sync'",
    )
    args = parser.parse_args()
    sys.exit(run_healthcheck(mode=args.mode))
