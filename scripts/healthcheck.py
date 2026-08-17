"""Healthcheck for the Liquid Wire procedural pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils import ffmpeg_helpers
from utils.log_config import configure_logging
from utils.youtube_oauth import _client_secrets_path, _token_path, validate_token_scopes

log = logging.getLogger(__name__)


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


def _check_render_deps() -> dict[str, Any]:
    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401

        return {"name": "Render deps", "ok": True, "info": "numpy + Pillow OK"}
    except Exception as exc:
        return {"name": "Render deps", "ok": False, "info": str(exc)}


def _check_youtube_token() -> dict[str, Any]:
    token_path = Path(_token_path())
    if not token_path.exists():
        return {
            "name": "Token YouTube (Liquid Wire)",
            "ok": False,
            "info": f"{token_path} not found; generate it with python utils/youtube_oauth.py",
        }
    try:
        data = json.loads(token_path.read_text(encoding="utf-8"))
        has_token = bool(data.get("token"))
        return {
            "name": "Token YouTube (Liquid Wire)",
            "ok": has_token,
            "info": "token present" if has_token else "JSON does not contain 'token'",
        }
    except Exception as exc:
        return {"name": "Token YouTube (Liquid Wire)", "ok": False, "info": f"Invalid JSON: {exc}"}


def _check_client_secret() -> dict[str, Any]:
    secret_path = _client_secrets_path()
    if secret_path:
        return {"name": "Google client secret", "ok": True, "info": f"{secret_path}"}
    # Em CI, o client_secret so e necessario para o fluxo interativo
    # flow.run_local_server (primeiro login com browser). Para renovar o
    # access_token expirado, google-auth usa o refresh_token + client_id +
    # client_secret que ja estao embutidos no proprio youtube_token.json.
    # Portanto, se o token OAuth tem refresh_token, a ausencia de
    # client_secret nao bloqueia a producao - sinalizamos como warning.
    token_path = Path(_token_path())
    has_refresh_token = False
    if token_path.exists():
        try:
            data = json.loads(token_path.read_text(encoding="utf-8"))
            has_refresh_token = bool(data.get("refresh_token"))
        except Exception:
            pass
    if has_refresh_token:
        return {
            "name": "Google client secret",
            "ok": True,
            "info": "not found, but token has refresh_token (refresh uses embedded client_id/secret)",
        }
    return {
        "name": "Google client secret",
        "ok": False,
        "info": (
            "not found and token has no refresh_token; set YOUTUBE_CLIENT_SECRET"
            " or run utils/youtube_oauth.py locally"
        ),
    }


def _check_token_scopes() -> dict[str, Any]:
    token_ok = _check_youtube_token()
    if not token_ok["ok"]:
        return {"name": "Token scopes", "ok": False, "info": "token missing or invalid"}
    missing = validate_token_scopes()
    if missing:
        return {
            "name": "Token scopes",
            "ok": False,
            "info": f"missing: {', '.join(s.split('/')[-1] for s in missing)}",
        }
    return {"name": "Token scopes", "ok": True, "info": "OK"}


def run_healthcheck(mode: str = "all") -> int:
    configure_logging()
    checks = [_check_python(), _check_ffmpeg(), _check_render_deps()]
    if mode == "fast":
        checks.append(_check_token_scopes())
    else:
        checks.extend([_check_youtube_token(), _check_client_secret(), _check_token_scopes()])

    log.info("=" * 60)
    log.info("Healthcheck Liquid Wire")
    log.info("=" * 60)
    for check in checks:
        status = "[OK]" if check["ok"] else "[FAIL]"
        log.info("%s %s: %s", status, check["name"], check["info"])

    all_ok = all(c["ok"] for c in checks)
    if all_ok:
        log.info("Environment ready for Liquid Wire generation/upload.")
        return 0
    log.warning("Fix [FAIL] items before running production uploads.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Healthcheck Liquid Wire")
    parser.add_argument("--mode", choices=["all", "fast"], default="all")
    args = parser.parse_args()
    return run_healthcheck(mode=args.mode)


if __name__ == "__main__":
    sys.exit(main())
