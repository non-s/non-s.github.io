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

import hashlib
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


def _generate_pkce_pair() -> tuple[str, str]:
    """Return a (code_verifier, code_challenge) pair for TikTok OAuth.

    TikTok's PKCE deviates from RFC 7636: instead of the standard
    base64url(SHA256(verifier)), TikTok requires HEX encoding of the
    SHA-256 hash. The `code_challenge_method=S256` parameter is still
    advertised. We followed the standard initially and TikTok rejected
    every exchange with `Code verifier or code challenge is invalid`
    despite a local SHA-256 round-trip matching — the mismatch was
    against TikTok's internally-recomputed *hex* digest.

    See: https://developers.tiktok.com/doc/login-kit-desktop/
    """
    verifier = secrets.token_urlsafe(64)        # 43-128 URL-safe chars
    challenge = hashlib.sha256(verifier.encode("ascii")).hexdigest()
    return verifier, challenge


def _build_authorize_url(client_key: str, state: str,
                          code_challenge: str) -> str:
    params = {
        "client_key":            client_key,
        "scope":                 ",".join(SCOPES),
        "response_type":         "code",
        "redirect_uri":          REDIRECT_URI,
        "state":                 state,
        "code_challenge":        code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def _exchange_code(code: str, client_key: str, client_secret: str,
                    code_verifier: str) -> dict:
    """Exchange an authorization code for access + refresh tokens.

    `code_verifier` is the PKCE secret minted before the consent URL
    was opened; TikTok requires it on the token exchange to match the
    `code_challenge` it received on the authorize step.
    """
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_key":    client_key,
            "client_secret": client_secret,
            "code":          code,
            "grant_type":    "authorization_code",
            "redirect_uri":  REDIRECT_URI,
            "code_verifier": code_verifier,
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
    """Spin up a one-shot local server to receive the OAuth redirect.

    The previous implementation raced two competing handlers
    (a `serve_forever` daemon thread + a `handle_request` loop on the
    main thread), which sometimes hung after the callback arrived.
    TikTok only ever sends ONE callback, so a single blocking
    `handle_request()` is both simpler and correct.
    """
    with socketserver.TCPServer(("127.0.0.1", port), _CallbackHandler) as srv:
        srv.timeout = 300  # 5 min to click the consent screen
        srv.handle_request()
    if _CallbackHandler.state != state:
        raise RuntimeError(
            "OAuth state mismatch — possible CSRF. Aborting."
        )
    return _CallbackHandler.code or ""


def _interactive_prompt(label: str, hint: str) -> str:
    """Read a value from stdin, retrying on empty input. Used when this
    script is packaged as a .exe and the user double-clicks it instead
    of running with env vars."""
    print(f"\n  {label}")
    if hint:
        print(f"  ({hint})")
    while True:
        try:
            value = input("  > ").strip()
        except EOFError:
            return ""
        if value:
            return value
        print("  ⚠️ Valor vazio — tenta de novo:")


def main() -> None:
    print("\n" + "=" * 70)
    print("  TikTok OAuth Helper — Wild Brief Bot")
    print("=" * 70)

    client_key = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
    if not client_key:
        client_key = _interactive_prompt(
            "Cole o TIKTOK_CLIENT_KEY:",
            "Pega em developers.tiktok.com → Manage apps → App details → Client key",
        )
    if not client_secret:
        client_secret = _interactive_prompt(
            "Cole o TIKTOK_CLIENT_SECRET:",
            "Mesma página → Client secret (cuidado, é sensível)",
        )
    if not client_key or not client_secret:
        print("\n❌ Sem client key/secret não dá pra continuar.")
        input("\nPressione Enter para fechar...")
        sys.exit(2)

    state = secrets.token_urlsafe(16)
    code_verifier, code_challenge = _generate_pkce_pair()
    url = _build_authorize_url(client_key, state, code_challenge)
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
        input("\nPressione Enter para fechar...")
        sys.exit(1)

    print("🔁 Trocando code por access_token + refresh_token…")
    try:
        payload = _exchange_code(code, client_key, client_secret, code_verifier)
    except RuntimeError as exc:
        print(f"\n❌ {exc}")
        input("\nPressione Enter para fechar...")
        sys.exit(1)

    payload["client_key"] = client_key
    payload["issued_at"] = datetime.now(timezone.utc).isoformat()
    token_json = json.dumps(payload, indent=2)
    TOKEN_FILE.write_text(token_json)

    print("\n" + "=" * 70)
    print("  ✅ TOKEN GERADO COM SUCESSO")
    print("=" * 70)
    print(f"\n  Arquivo salvo em: {TOKEN_FILE.resolve()}")
    print("\n  COPIA TUDO entre as linhas tracejadas abaixo e cola no")
    print("  GitHub Secret TIKTOK_TOKEN:")
    print("\n" + "-" * 70)
    print(token_json)
    print("-" * 70)
    print("\n  📋 Próximo passo:")
    print("     https://github.com/non-s/non-s.github.io/settings/secrets/actions")
    print("     → TIKTOK_TOKEN → Update → cola o JSON acima → Update secret\n")

    input("Pressione Enter para fechar...")


if __name__ == "__main__":
    main()
