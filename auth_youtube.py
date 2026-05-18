#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auth_youtube.py — Autorização OAuth UMA ÚNICA VEZ
===================================================
Execute este script UMA VEZ no seu computador.
Ele vai abrir o navegador, você faz login no Google,
aprova as permissões, e o token.json é salvo.

Depois disso, tudo roda automaticamente.

Uso:
    python auth_youtube.py
"""

from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    # Upload videos.
    "https://www.googleapis.com/auth/youtube.upload",
    # Playlists + comments (we auto-add Shorts to per-region playlists
    # and post a first comment crediting the source).
    "https://www.googleapis.com/auth/youtube",
    # Read channel + video metadata (analytics workflow lists recent
    # uploads via the uploads playlist).
    "https://www.googleapis.com/auth/youtube.readonly",
    # YouTube Analytics — retention curves, CTR, traffic sources.
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
CLIENT_SECRET = Path("client_secret.json")
TOKEN_FILE    = Path("token.json")


def main() -> None:
    if not CLIENT_SECRET.exists():
        print("\n❌ ERRO: client_secret.json não encontrado!")
        print("   Coloque o arquivo JSON baixado do Google Cloud nesta pasta")
        print("   e renomeie para: client_secret.json\n")
        return

    print("\n🔐 Iniciando autenticação OAuth do YouTube...")
    print("   Uma janela do navegador vai abrir.")
    print("   Faça login com a conta do YouTube vinculada ao canal.")
    print("   Clique em 'Continuar' mesmo que apareça aviso de app não verificado.\n")

    flow  = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)

    TOKEN_FILE.write_text(creds.to_json())
    print(f"\n✅ Autenticação concluída! Token salvo em: {TOKEN_FILE}")
    print("\n📋 PRÓXIMO PASSO:")
    print("   Copie o conteúdo de token.json e salve como")
    print("   GitHub Secret com o nome: YOUTUBE_TOKEN\n")


if __name__ == "__main__":
    main()
