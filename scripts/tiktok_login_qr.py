"""scripts/tiktok_login_qr.py — gera tiktok_state.json via login manual.

Rode este script na SUA maquina (nunca em CI): ele abre um Chromium
VISIVEL (headed) na pagina de login do TikTok. Faca login do jeito que
voce ja usa no dia a dia (QR code escaneado pelo celular, "Continuar com
o Google", etc.) - a automacao em produção (utils/tiktok_uploader.py) não
sabe fazer nenhum desses fluxos sozinha, porque exigem uma interação
humana real (escanear o QR / completar o OAuth do Google) que não dá pra
automatizar headless. O que a automação sabe fazer é REUSAR uma sessão
(cookies) já autenticada por você - é isso que este script produz.

Uso:
    python scripts/tiktok_login_qr.py

Depois de detectar a sessão ativa, salva tiktok_state.json na raiz do
repo e imprime instruções para colar o conteúdo no secret
TIKTOK_STATE_JSON (Settings > Secrets and variables > Actions, no
GitHub). O workflow cross-post.yml escreve esse secret em
tiktok_state.json antes de cada execução, então a automação reusa a
mesma sessão até ela expirar - quando isso acontecer, rode este script
de novo e atualize o secret.

NUNCA faça commit de tiktok_state.json (contém sessionid) - já está no
.gitignore.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.tiktok_uploader import (  # noqa: E402
    _STEALTH_SCRIPT,
    _USER_AGENT,
    DEFAULT_STATE_PATH,
    _is_logged_in,
)

_LOGIN_URL = "https://www.tiktok.com/login"
_TIMEOUT_SECONDS = 300
_POLL_SECONDS = 2


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright nao instalado. Rode: pip install playwright && playwright install chromium")
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent=_USER_AGENT, viewport={"width": 1280, "height": 800})
        context.add_init_script(_STEALTH_SCRIPT)
        page = context.new_page()
        page.goto(_LOGIN_URL, wait_until="domcontentloaded")

        print("Faca login na janela do navegador que abriu (QR code, Google, o que voce usar).")
        print(f"Aguardando ate {_TIMEOUT_SECONDS}s por uma sessao ativa...")

        deadline = time.time() + _TIMEOUT_SECONDS
        logged_in = False
        while time.time() < deadline:
            if _is_logged_in(page):
                logged_in = True
                break
            time.sleep(_POLL_SECONDS)

        if not logged_in:
            print("Tempo esgotado sem detectar login. Rode de novo e tente completar o login mais rapido.")
            browser.close()
            return 1

        context.storage_state(path=str(DEFAULT_STATE_PATH))
        browser.close()

    print(f"\nSessao salva em {DEFAULT_STATE_PATH}")
    print("Copie TODO o conteudo desse arquivo e cole no secret TIKTOK_STATE_JSON")
    print("em Settings > Secrets and variables > Actions do repositorio no GitHub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
