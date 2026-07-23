"""
utils/youtube_oauth.py — autenticacao OAuth2 com a YouTube Data API.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"]


def _token_path() -> str:
    return os.environ.get("YOUTUBE_TOKEN_PATH", "youtube_token.json")


def _load_token() -> Credentials | None:
    token_path = _token_path()
    if not Path(token_path).exists():
        return None
    try:
        with open(token_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Credentials.from_authorized_user_info(data, SCOPES)
    except Exception as exc:
        log.warning("Token invalido em %s: %s", token_path, exc)
        return None


def _save_token(creds: Credentials) -> None:
    token_path = _token_path()
    Path(token_path).parent.mkdir(parents=True, exist_ok=True)
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())


def _client_secrets_path() -> str | None:
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    if client_secret:
        fd, tmp_path = tempfile.mkstemp(prefix="client_secret_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(client_secret)
            os.chmod(tmp_path, 0o600)
            return tmp_path
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise
    client_secret_path = os.environ.get("YOUTUBE_CLIENT_SECRET_PATH", "client_secret.json")
    if Path(client_secret_path).exists():
        return client_secret_path
    return None


def get_youtube_service() -> build:
    creds = _load_token()
    if creds and not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_token(creds)
        else:
            creds = None
    if not creds:
        secrets_path = _client_secrets_path()
        if not secrets_path:
            raise RuntimeError("Nenhuma credencial do YouTube encontrada.")
        try:
            flow = InstalledAppFlow.from_client_secrets_file(secrets_path, SCOPES)
            creds = flow.run_local_server(port=0)
        finally:
            # Remove apenas arquivos temporarios criados por este modulo.
            if secrets_path.startswith(tempfile.gettempdir()):
                Path(secrets_path).unlink(missing_ok=True)
        _save_token(creds)
    return build("youtube", "v3", credentials=creds, cache_discovery=False)
