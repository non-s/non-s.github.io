#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auth_tiktok.py — Autorização OAuth UMA ÚNICA VEZ no TikTok
============================================================
Execute este script UMA VEZ no seu computador.
Ele vai abrir o navegador, você faz login no TikTok,
aprova as permissões, e o tiktok_token.json é salvo.

Depois disso, tudo roda automaticamente.

Pré-requisitos
--------------
1. Conta de developer no TikTok: https://developers.tiktok.com/
2. Criar um app e habilitar os produtos:
     - Login Kit (OAuth)
     - Content Posting API  (Direct Post + Upload)
3. Configurar redirect URI: http://localhost:8080/callback
4. Anotar:
     - TIKTOK_CLIENT_KEY
     - TIKTOK_CLIENT_SECRET

Uso
---
    export TIKTOK_CLIENT_KEY=awxxxxxxxxxx
    export TIKTOK_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    python auth_tiktok.py
"""
from __future__ import annotations

import http.server
import json
import os
import secrets
import socketserver
import sys
import threading
import urllib.parse
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import requests

TOKEN_FILE = Path("tiktok_token.json")
REDIRECT_URI = os.environ.get(
    "TIKTOK_REDIRECT_URI", "http://localhost:8080/callback"
)
# Scopes required by the publishing pipeline:
#   user.info.basic   — channel handle, open_id (analytics joins)
#   video.publish     — direct post via Content Posting API
#   video.upload      — upload as draft (fallback when DIRECT_POST blocked)
#   video.list        — fetch own videos for analytics + velocity snapshots
SCOPES = ["user.info.basic", "video.publish", "video.upload", "video.list"]

# TikTok OAuth endpoints (v2 / open.tiktokapis.com).
AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


def _build_authorize_url(client_key: str, state: str) -> str:
    params = {
        "client_key":    client_key,
        "scope":         ",".join(SCOPES),
        "response_type": "code",
        "redirect_uri":  REDIRECT_URI,
        "state":         state,
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def _exchange_code(code: str, client_key: str, client_secret: str) -> dict:
    """Exchange an authorization code for access + refresh tokens."""
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_key":    client_key,
            "client_secret": client_secret,
            "code":          code,
            "grant_type":    "authorization_code",
            "redirect_uri":  REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "error" in payload and payload["error"]:
        raise RuntimeError(f"TikTok token exchange failed: {payload}")
    return payload


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    code: str | None = None
    state: str | None = None

    def do_GET(self):  # noqa: N802 (stdlib naming)
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != urllib.parse.urlparse(REDIRECT_URI).path:
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        _CallbackHandler.code = (params.get("code") or [None])[0]
        _CallbackHandler.state = (params.get("state") or [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        body = (
            "<html><body style='font-family:sans-serif;padding:40px'>"
            "<h2>✅ Autenticação TikTok concluída</h2>"
            "<p>Pode fechar esta aba.</p></body></html>"
        )
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *_args, **_kwargs):  # silence default logging
        return


def _capture_code(state: str, port: int) -> str:
    """Spin up a one-shot local server to receive the OAuth redirect."""
    with socketserver.TCPServer(("127.0.0.1", port), _CallbackHandler) as srv:
        srv.timeout = 300  # 5 min to click the consent screen
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        while _CallbackHandler.code is None:
            srv.handle_request()
            if _CallbackHandler.code is not None:
                break
        srv.shutdown()
    if _CallbackHandler.state != state:
        raise RuntimeError(
            "OAuth state mismatch — possible CSRF. Aborting."
        )
    return _CallbackHandler.code or ""


def main() -> None:
    client_key = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
    if not client_key or not client_secret:
        print("\n❌ TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET ausentes.")
        print("   Crie um app em https://developers.tiktok.com/ e exporte:")
        print("     export TIKTOK_CLIENT_KEY=awxxxxxxxxxx")
        print("     export TIKTOK_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        sys.exit(2)

    state = secrets.token_urlsafe(16)
    url = _build_authorize_url(client_key, state)
    print("\n🔐 Iniciando autenticação OAuth do TikTok...")
    print("   Uma janela do navegador vai abrir.")
    print("   Faça login com a conta do TikTok do canal e aprove as permissões.")
    print(f"\n   Se o navegador não abrir, acesse manualmente:\n   {url}\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

    port = int(urllib.parse.urlparse(REDIRECT_URI).port or 8080)
    code = _capture_code(state, port)
    if not code:
        print("❌ Nenhum code recebido — timeout ou consentimento negado.")
        sys.exit(1)

    print("🔁 Trocando code por access_token + refresh_token…")
    payload = _exchange_code(code, client_key, client_secret)

    # Persist EVERYTHING returned by TikTok (access_token, refresh_token,
    # open_id, scopes, expires_in). `issued_at` lets upload_tiktok.py
    # compute expiry on the FIRST workflow run without a wasteful
    # preemptive refresh (which would burn the single-use refresh_token).
    payload["client_key"] = client_key
    payload["issued_at"] = datetime.now(timezone.utc).isoformat()
    TOKEN_FILE.write_text(json.dumps(payload, indent=2))
    print(f"\n✅ Autenticação concluída! Token salvo em: {TOKEN_FILE}")
    print("\n📋 PRÓXIMO PASSO:")
    print("   Cole o conteúdo de tiktok_token.json no GitHub Secret")
    print("   com o nome: TIKTOK_TOKEN")
    print("   (e configure também TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET)\n")


if __name__ == "__main__":
    main()
