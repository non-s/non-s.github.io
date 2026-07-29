"""scripts/tiktok_login_qr.py — gera tiktok_state.json via login manual.

Rode este script na SUA maquina (nunca em CI): ele abre um navegador
VISIVEL (headed) na pagina de login do TikTok. Faca login do jeito que
voce ja usa no dia a dia (QR code escaneado pelo celular, "Continuar com
o Google", etc.) - a automacao em produção (utils/tiktok_uploader.py) não
sabe fazer nenhum desses fluxos sozinha, porque exigem uma interação
humana real (escanear o QR / completar o OAuth do Google) que não dá pra
automatizar headless. O que a automação sabe fazer é REUSAR uma sessão
(cookies) já autenticada por você - é isso que este script produz.

Uso:
    python scripts/tiktok_login_qr.py

Por padrao abre um Chromium com perfil NOVO (zerado) - o TikTok as vezes
trata esse navegador "sem historico" como dispositivo desconhecido e
bloqueia o login (QR/Google nao completam). Se isso acontecer, use
--use-chrome-profile para abrir com o SEU Chrome de verdade (mesmos
cookies/historico/fingerprint que o TikTok ja reconhece - se voce ja
estiver logado no TikTok nesse Chrome, a sessao e detectada na hora, sem
precisar logar de novo):

    python scripts/tiktok_login_qr.py --use-chrome-profile

Feche TODAS as janelas do Chrome antes de rodar com essa opcao (o perfil
fica bloqueado enquanto o Chrome estiver aberto). Se voce usa mais de um
perfil do Chrome, veja o nome certo em chrome://version (campo "Caminho
do perfil", ultima pasta do caminho) e passe com --profile-directory.

Esse modo copia os cookies/sessao do seu perfil pra uma pasta temporaria
antes de abrir o navegador - o Chrome recusa automacao apontando direto
pro perfil "Default" de verdade (protecao contra sequestro de sessao),
entao a copia e necessaria; seus cookies continuam validos nela.

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

import argparse
import os
import shutil
import sys
import tempfile
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

# Pastas pesadas/irrelevantes pra reusar login (cache, service workers,
# extensoes) - copiar isso deixaria a copia gigante e lenta sem nenhum
# ganho, ja que so precisamos dos cookies/sessao.
_PROFILE_COPY_SKIP_DIRS = {
    "Cache", "Code Cache", "GPUCache", "Service Worker", "blob_storage",
    "IndexedDB", "Session Storage", "Extension State", "Extension Rules",
    "Extensions", "component_crx_cache", "GrShaderCache", "ShaderCache",
}


def _default_chrome_profile_dir() -> Path | None:
    """Pasta "User Data" padrao do Chrome por SO, ou None se desconhecido.

    Essa e a pasta RAIZ que o Chrome usa pra guardar todos os perfis (o
    perfil em si - "Default", "Profile 1" etc. - fica DENTRO dela e e
    selecionado via --profile-directory)."""
    home = Path.home()
    if sys.platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local")))
        return local / "Google" / "Chrome" / "User Data"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Google" / "Chrome"
    return home / ".config" / "google-chrome"


def _copy_profile_for_automation(source_root: Path, profile_name: str) -> Path:
    """Copia o essencial do perfil do Chrome pra uma pasta temporaria NAO-
    default.

    O Chrome recusa remote debugging (que o Playwright precisa pra
    controlar o navegador) quando --user-data-dir aponta pro perfil
    DEFAULT de verdade - erro "DevTools remote debugging requires a
    non-default data directory". E um bloqueio de seguranca proposital do
    proprio Chrome contra automacao sequestrando uma sessao real, nao
    contorna via flag. Copiar "Local State" + a pasta do perfil (sem
    cache/extensoes - ver _PROFILE_COPY_SKIP_DIRS) pra um diretorio novo
    satisfaz a exigencia mantendo os cookies reais. Os cookies do Chrome
    no Windows sao criptografados via DPAPI atrelado a conta do Windows
    (nao ao caminho da pasta), entao continuam decodificando normalmente
    na copia.
    """
    dest_root = Path(tempfile.gettempdir()) / "pata_jazz_chrome_profile_copy"
    if dest_root.exists():
        shutil.rmtree(dest_root, ignore_errors=True)
    dest_root.mkdir(parents=True, exist_ok=True)

    local_state = source_root / "Local State"
    if local_state.exists():
        shutil.copy2(local_state, dest_root / "Local State")

    src_profile = source_root / profile_name
    if not src_profile.exists():
        print(f"Perfil {profile_name!r} nao encontrado em {source_root}.")
        raise SystemExit(1)

    def _skip(_dirpath: str, names: list[str]) -> list[str]:
        return [n for n in names if n in _PROFILE_COPY_SKIP_DIRS]

    shutil.copytree(src_profile, dest_root / profile_name, ignore=_skip, dirs_exist_ok=True)
    return dest_root


def _open_context(p, args):
    """Abre o navegador no modo escolhido. Retorna (context, browser) -
    browser e None no modo --use-chrome-profile (launch_persistent_context
    nao tem um Browser separado pra fechar, so o context)."""
    if not args.use_chrome_profile:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent=_USER_AGENT, viewport={"width": 1280, "height": 800})
        context.add_init_script(_STEALTH_SCRIPT)
        return context, browser

    profile_dir = Path(args.chrome_profile_dir) if args.chrome_profile_dir else _default_chrome_profile_dir()
    if not profile_dir or not profile_dir.exists():
        print(f"Pasta de perfil do Chrome nao encontrada: {profile_dir}")
        print('Feche o Chrome e passe o caminho certo com --chrome-profile-dir "CAMINHO".')
        raise SystemExit(1)

    print("Feche TODAS as janelas do Chrome antes de continuar (alguns arquivos do perfil "
          "ficam bloqueados com o Chrome aberto).")
    print(f"Copiando sessao de {profile_dir / args.profile_directory} para uma pasta temporaria...")
    copy_dir = _copy_profile_for_automation(profile_dir, args.profile_directory)
    print(f"Abrindo Chrome com a copia em: {copy_dir}")
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(copy_dir),
        channel="chrome",
        headless=False,
        args=[f"--profile-directory={args.profile_directory}"],
        viewport={"width": 1280, "height": 800},
    )
    return context, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--use-chrome-profile", action="store_true",
        help="Abre com o SEU Chrome de verdade (cookies/historico existentes) em vez de um Chromium "
             "zerado. Use se o login (QR/Google) nao completar no modo padrao. Feche o Chrome antes.",
    )
    parser.add_argument(
        "--chrome-profile-dir", type=str, default=None,
        help='Caminho da pasta "User Data" do Chrome (default: local padrao do SO detectado automaticamente).',
    )
    parser.add_argument(
        "--profile-directory", type=str, default="Default",
        help='Nome do perfil dentro de "User Data" (default: Default). Veja o seu em chrome://version.',
    )
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright nao instalado. Rode: pip install playwright && playwright install chromium")
        return 1

    with sync_playwright() as p:
        context, browser = _open_context(p, args)
        page = context.pages[0] if context.pages else context.new_page()
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
            context.close()
            if browser:
                browser.close()
            return 1

        context.storage_state(path=str(DEFAULT_STATE_PATH))
        context.close()
        if browser:
            browser.close()

    print(f"\nSessao salva em {DEFAULT_STATE_PATH}")
    print("Copie TODO o conteudo desse arquivo e cole no secret TIKTOK_STATE_JSON")
    print("em Settings > Secrets and variables > Actions do repositorio no GitHub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
