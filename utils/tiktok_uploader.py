"""utils/tiktok_uploader.py — upload de videos para o TikTok via browser automation.

Usa Playwright (Chromium headless) com stealth scripts para passar pelo WAF
do TikTok. Login por email/senha com persistencia de sessao via
storage_state (cookies + localStorage). O upload e feito navegando para
tiktok.com/upload, preenchendo o input de arquivo e a descricao.

Dependencies: playwright (pip install playwright && playwright install chromium)
Env vars:
  TIKTOK_EMAIL — email da conta
  TIKTOK_PASSWORD — senha da conta
  TIKTOK_STATE_PATH — path do storage_state (default: tiktok_state.json)
  TIKTOK_HEADLESS — "0" para headed (default: headless)
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE_PATH = ROOT / "tiktok_state.json"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

_STEALTH_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
    Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
    window.chrome = { runtime: {} };
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) =>
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters);
"""

_LOGIN_URL = "https://www.tiktok.com/login/phone-or-email/email"
_UPLOAD_URL = "https://www.tiktok.com/upload"


def _is_logged_in(page) -> bool:
    """Verifica se a pagina atual indica sessao ativa."""
    url = page.url
    if "login" in url.lower():
        return False
    avatar = page.query_selector("[data-e2e='profile-icon']")
    return avatar is not None


def _do_login(page, email: str, password: str) -> bool:
    """Faz login no TikTok com email/senha. Retorna True se logou."""
    log.info("Fazendo login no TikTok: %s", email)
    page.goto(_LOGIN_URL, wait_until="networkidle", timeout=45000)
    time.sleep(3)

    email_input = page.query_selector("input[name='username']")
    if not email_input:
        log.error("Campo de email nao encontrado na pagina de login.")
        return False

    email_input.click()
    email_input.fill("")
    for ch in email:
        page.keyboard.type(ch, delay=50)
    time.sleep(0.5)

    pass_input = page.query_selector("input[type='password']")
    if not pass_input:
        log.error("Campo de senha nao encontrado.")
        return False

    pass_input.click()
    pass_input.fill("")
    for ch in password:
        page.keyboard.type(ch, delay=50)
    time.sleep(1)

    page.keyboard.press("Enter")

    for i in range(30):
        time.sleep(1)
        if "login" not in page.url.lower():
            log.info("Login sucesso em %ds. URL: %s", i + 1, page.url)
            return True
        # Verifica se apareceu mensagem de erro
        body_text = page.inner_text("body")
        if "maximum number of attempts" in body_text.lower():
            log.error("TikTok bloqueou por tentativas excessivas. Tente mais tarde.")
            return False
        if "incorrect" in body_text.lower() or "invalid" in body_text.lower():
            log.error("Credenciais invalidas.")
            return False

    log.error("Login nao completou em 30s. URL: %s", page.url)
    return False


def _ensure_login(page, context, email: str, password: str, state_path: Path) -> bool:
    """Garante que estamos logados. Tenta storage_state primeiro, depois login."""
    if _is_logged_in(page):
        return True

    log.info("Sessao invalida ou expirada. Tentando login com credenciais...")
    if not _do_login(page, email, password):
        return False

    # Salva a sessao para reuso
    try:
        context.storage_state(path=str(state_path))
        log.info("Sessao salva em %s", state_path)
    except Exception as exc:
        log.warning("Falha ao salvar sessao: %s", exc)
    return True


def upload_to_tiktok(
    video_path: Path,
    meta: dict,
    *,
    email: str | None = None,
    password: str | None = None,
    state_path: Path | None = None,
    headless: bool = True,
) -> str | None:
    """Faz upload de um video para o TikTok via browser automation.

    Retorna a URL do video publicado, ou None em falha.
    """
    email = email or os.environ.get("TIKTOK_EMAIL", "")
    password = password or os.environ.get("TIKTOK_PASSWORD", "")
    state_path = state_path or Path(os.environ.get("TIKTOK_STATE_PATH", str(DEFAULT_STATE_PATH)))
    headless = os.environ.get("TIKTOK_HEADLESS", "1") != "0" if headless else False

    if not email or not password:
        log.info("TikTok: TIKTOK_EMAIL/TIKTOK_PASSWORD nao configurados.")
        return None

    if not video_path.exists():
        log.error("Video nao encontrado: %s", video_path)
        return None

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("Playwright nao instalado. Rode: pip install playwright && playwright install chromium")
        return None

    title = str(meta.get("title", "Pata Jazz"))[:150]
    hashtags = meta.get("hashtags") or []
    hashtag_text = " ".join(f"#{h.lstrip('#')}" for h in hashtags)
    description = f"{title}\n\n{hashtag_text}".strip()[:2200]

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        # Reusa sessao salva se existir
        storage_state = str(state_path) if state_path.exists() else None
        context = browser.new_context(
            user_agent=_USER_AGENT,
            viewport={"width": 1280, "height": 720},
            locale="en-US",
            timezone_id="America/Sao_Paulo",
            storage_state=storage_state,
        )
        context.add_init_script(_STEALTH_SCRIPT)

        page = context.new_page()
        page.set_default_timeout(120000)

        try:
            # Garante login
            page.goto(_UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)

            if not _ensure_login(page, context, email, password, state_path):
                log.error("Nao foi possivel fazer login no TikTok.")
                browser.close()
                return None

            # Navega para upload
            log.info("Navegando para pagina de upload...")
            page.goto(_UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)

            # Encontra o input de arquivo
            file_input = page.query_selector("input[type='file']")
            if not file_input:
                log.error("Input de arquivo nao encontrado na pagina de upload.")
                page.screenshot(path=str(ROOT / "_videos" / "tiktok_upload_fail.png"))
                browser.close()
                return None

            log.info("Enviando arquivo: %s", video_path.name)
            file_input.set_input_files(str(video_path))

            # Aguarda upload + processamento (pode demorar)
            log.info("Aguardando upload e processamento...")
            for i in range(120):
                time.sleep(2)
                # Procura pelo campo de descricao (contenteditable)
                desc_el = page.query_selector("[contenteditable='true']")
                post_btn = page.query_selector("button:has-text('Post')")
                if desc_el and post_btn:
                    log.info("Upload concluido em %ds. Preenchendo descricao...", (i + 1) * 2)
                    break
            else:
                log.error("Upload nao concluiu em 240s.")
                browser.close()
                return None

            # Preenche descricao
            desc_el.click()
            desc_el.fill("")
            for ch in description:
                page.keyboard.type(ch, delay=30)
            time.sleep(1)

            # Clica em Post
            log.info("Clicando Post...")
            post_btn.click()

            # Aguarda confirmacao
            for _i in range(30):
                time.sleep(1)
                url = page.url
                if "/upload" not in url and "tiktok.com" in url:
                    log.info("Video publicado! URL: %s", url)
                    browser.close()
                    return url

            log.info("Post clicado mas sem confirmacao de redirect.")
            browser.close()
            return None

        except Exception as exc:
            log.error("Erro no upload TikTok: %s", exc)
            try:
                page.screenshot(path=str(ROOT / "_videos" / "tiktok_error.png"))
            except Exception:
                pass
            browser.close()
            return None
