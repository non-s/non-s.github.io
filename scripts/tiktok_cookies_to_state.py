"""scripts/tiktok_cookies_to_state.py — converte cookies exportados do seu
Chrome normal para o formato storage_state do Playwright, SEM automatizar
nenhum login.

Por que isso existe: tanto o Chromium do Playwright quanto o Chrome de
verdade controlado via --use-chrome-profile (scripts/tiktok_login_qr.py)
esbarram no mesmo bloqueio ao logar com "Continuar com o Google": o
Google detecta que o navegador esta sob controle de automacao (CDP/
remote debugging - e assim que o Playwright funciona, nao tem como
esconder isso) e recusa o OAuth ("Esse navegador ou app pode nao ser
seguro"). Nao existe contorno confiavel via flag/stealth script pra isso
- e uma protecao deliberada do Google contra qualquer ferramenta de
automacao, nao um detalhe de fingerprint.

A solucao e nunca automatizar o login: voce ja esta logado no TikTok no
SEU Chrome normal (sessao real, sem Playwright/CDP envolvido nenhum) -
so precisamos capturar os cookies dessa sessao ja existente.

Passo a passo:
1. No seu Chrome normal (o de sempre, ja logado no TikTok), instale a
   extensao "Cookie-Editor" (busque na Chrome Web Store).
2. Abra tiktok.com (logado), clique no icone da extensao Cookie-Editor,
   clique em "Export" -> "Export as JSON" (copia pra area de
   transferencia).
3. Cole o conteudo copiado num arquivo de texto, ex.:
   tiktok_cookies_export.json (na pasta do projeto).
4. Rode:
   python scripts/tiktok_cookies_to_state.py tiktok_cookies_export.json
5. Gera tiktok_state.json - copie o conteudo pro secret TIKTOK_STATE_JSON
   (Settings > Secrets and variables > Actions, no GitHub).

NUNCA faça commit de tiktok_state.json nem do arquivo de export dos
cookies (contêm sessionid) - tiktok_state.json já está no .gitignore.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.tiktok_uploader import DEFAULT_STATE_PATH  # noqa: E402

# Cookie-Editor/Chrome usam esses valores pra sameSite; Playwright espera
# exatamente "Strict"|"Lax"|"None". "unspecified"/ausente cai em "Lax"
# (comportamento padrao mais comum, evita rejeicao do Playwright por
# valor invalido).
_SAME_SITE_MAP = {
    "no_restriction": "None",
    "lax": "Lax",
    "strict": "Strict",
}


# Alguns apps de chat/clipboard "linkificam" automaticamente dominios nus
# (www.tiktok.com) ao copiar/colar texto, corrompendo o campo domain do
# JSON exportado pra algo tipo ".[www.tiktok.com](https://www.tiktok.com)"
# em vez de ".www.tiktok.com". Isso quebraria o storage_state do
# Playwright (domain invalido) - desfaz o link markdown antes de usar.
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def _clean_domain(domain: str) -> str:
    return _MARKDOWN_LINK_RE.sub(r"\1", domain)


def _convert_cookie(raw: dict) -> dict | None:
    name, value, domain = raw.get("name"), raw.get("value"), raw.get("domain")
    if not name or value is None or not domain:
        return None
    domain = _clean_domain(str(domain))
    same_site_raw = str(raw.get("sameSite", "") or "").strip().lower()
    expires = raw.get("expirationDate")
    return {
        "name": name,
        "value": value,
        "domain": domain,
        "path": raw.get("path", "/"),
        "expires": float(expires) if expires is not None else -1,
        "httpOnly": bool(raw.get("httpOnly", False)),
        "secure": bool(raw.get("secure", False)),
        "sameSite": _SAME_SITE_MAP.get(same_site_raw, "Lax"),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python scripts/tiktok_cookies_to_state.py <arquivo_export.json>")
        return 1

    src = Path(sys.argv[1])
    if not src.exists():
        print(f"Arquivo nao encontrado: {src}")
        return 1

    try:
        raw_cookies = json.loads(src.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Falha ao ler/parsear {src}: {exc}")
        return 1

    if not isinstance(raw_cookies, list):
        print("Formato inesperado - esperava uma lista de cookies (export do Cookie-Editor).")
        return 1

    tiktok_cookies = [
        cookie
        for raw in raw_cookies
        if isinstance(raw, dict) and "tiktok.com" in str(raw.get("domain", ""))
        for cookie in [_convert_cookie(raw)]
        if cookie is not None
    ]
    if not tiktok_cookies:
        print("Nenhum cookie de tiktok.com encontrado no arquivo. Confirme que exportou "
              "estando logado em tiktok.com (nao em outra aba).")
        return 1

    state = {"cookies": tiktok_cookies, "origins": []}
    DEFAULT_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Sessao salva em {DEFAULT_STATE_PATH} ({len(tiktok_cookies)} cookies do TikTok).")
    print("Copie TODO o conteudo desse arquivo e cole no secret TIKTOK_STATE_JSON")
    print("em Settings > Secrets and variables > Actions do repositorio no GitHub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
