"""
utils/youtube_oauth.py — autenticacao OAuth2 com a YouTube Data API.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"]


def _load_token() -> Credentials | None:
    token_path = os.environ.get("YOUTUBE_TOKEN_PATH", "youtube_token.json")
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
    token_path = os.environ.get("YOUTUBE_TOKEN_PATH", "youtube_token.json")
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())


def get_youtube_service() -> build:
    creds = _load_token()
    if creds and not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_token(creds)
        else:
            creds = None
    if not creds:
        client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
        client_secret_path = os.environ.get("YOUTUBE_CLIENT_SECRET_PATH", "client_secret.json")
        if client_secret:
            Path("client_secret_tmp.json").write_text(client_secret, encoding="utf-8")
            flow = InstalledAppFlow.from_client_secrets_file("client_secret_tmp.json", SCOPES)
            try:
                os.remove("client_secret_tmp.json")
            except FileNotFoundError:
                pass
        elif Path(client_secret_path).exists():
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
        else:
            raise RuntimeError("Nenhuma credencial do YouTube encontrada.")
        creds = flow.run_local_server(port=0)
        _save_token(creds)
    return build("youtube", "v3", credentials=creds, cache_discovery=False)
