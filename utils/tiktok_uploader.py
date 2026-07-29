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

import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE_PATH = ROOT / "tiktok_state.json"
_UPLOAD_STATE_FILE = ROOT / "_videos" / "tiktok_upload_state.json"
_MAX_TIKTOK_POSTS = 500


def _record_tiktok_post(video: str, title: str, url: str) -> None:
    """Acrescenta um post publicado com sucesso a _data/tiktok_posts.json.

    Historico durable (cacheado entre runs de cross-post.yml via
    actions/cache) consumido por scripts/generate_dashboard.py pra dar
    visibilidade ao cross-posting - sem isso o dashboard so mostrava dados
    do YouTube, nunca do TikTok. Best-effort: uma falha aqui nao deve
    derrubar o upload, que ja terminou com sucesso nesse ponto.
    """
    try:
        from utils.paths import data_dir
        from utils.state_lock import state_lock

        posts_file = data_dir() / "tiktok_posts.json"
        with state_lock(posts_file):
            try:
                posts = json.loads(posts_file.read_text(encoding="utf-8")) if posts_file.exists() else []
                if not isinstance(posts, list):
                    posts = []
            except Exception:
                posts = []
            posts.append({
                "video": video,
                "title": title,
                "url": url,
                "posted_at": datetime.now(UTC).isoformat(),
            })
            if len(posts) > _MAX_TIKTOK_POSTS:
                posts = posts[-_MAX_TIKTOK_POSTS:]
            posts_file.parent.mkdir(parents=True, exist_ok=True)
            posts_file.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning("Falha ao registrar post do TikTok em tiktok_posts.json (nao critico): %s", exc)

# Marcadores de texto usados pelo TikTok em desafios de verificacao
# (captcha/slider). Headless nao consegue resolver isso - detectar cedo
# evita esperar os 30s inteiros de timeout so pra falhar do mesmo jeito,
# e deixa um log claro do motivo real em vez de "login nao completou".
_CAPTCHA_MARKERS = ("verify to continue", "captcha", "drag the slider", "verify you're human")

# Textos de erro/toast comuns apos tentar publicar - se aparecerem, o post
# nao foi aceito mesmo que a pagina nao tenha redirecionado.
_POST_ERROR_MARKERS = (
    "failed to upload", "upload failed", "something went wrong",
    "video is still uploading", "violat", "try again later", "network error",
)


# Mood (utils/channel_config, usado na geracao) -> categoria (vocabulario
# de utils/seo_keywords.generate_tiktok_hashtags/generate_hashtags).
_MOOD_TO_CATEGORIA = {
    "relax": "relaxation",
    "fofura": "cuteness",
    "diversao": "fun",
}


def _hashtags_for_tiktok(meta: dict) -> list[str]:
    """Hashtags pro TikTok, geradas com o vocabulario nativo da plataforma
    (ver utils.seo_keywords.generate_tiktok_hashtags) em vez de reusar
    meta['hashtags'] do YouTube (#Shorts/#YouTubeShorts nao existem la).

    Deriva animal/categoria do proprio meta do video (scene/mood); em caso
    de meta incompleto ou falha na geracao, cai para meta['hashtags'] (o
    conjunto do YouTube) em vez de nao ter nenhuma hashtag.
    """
    try:
        from utils.animal_branding import detect_animal
        from utils.seo_keywords import generate_tiktok_hashtags

        animal = detect_animal(str(meta.get("scene", "")))
        categoria = _MOOD_TO_CATEGORIA.get(str(meta.get("mood", "")), "cuteness")
        hashtags = generate_tiktok_hashtags(animal=animal, categoria=categoria)
        if hashtags:
            return hashtags
    except Exception as exc:
        log.debug("Falha ao gerar hashtags nativas do TikTok (usando fallback): %s", exc)
    return list(meta.get("hashtags") or [])


def _write_upload_state(video: str, stage: str, detail: str = "") -> None:
    """Grava o ultimo estagio conhecido do upload em disco (debug em CI).

    Best-effort: uma falha aqui nunca deve derrubar o upload em si.
    """
    try:
        _UPLOAD_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "video": video,
            "stage": stage,
            "detail": detail,
            "at": datetime.now(UTC).isoformat(),
        }
        _UPLOAD_STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("[tiktok:%s] %s", stage, detail or video)
    except Exception:
        log.debug("Falha ao gravar estado do upload TikTok (nao critico).")

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


def _page_mentions_any(page, markers: tuple[str, ...]) -> str | None:
    """Retorna o primeiro marcador encontrado no texto visivel da pagina, ou
    None. Nunca levanta excecao - inner_text pode falhar em paginas ainda
    carregando, o que nao deve derrubar a deteccao de estado."""
    try:
        body_text = page.inner_text("body").lower()
    except Exception:
        return None
    for marker in markers:
        if marker in body_text:
            return marker
    return None


def _do_login(page, email: str, password: str) -> bool:
    """Faz login no TikTok com email/senha. Retorna True se logou."""
    log.info("Fazendo login no TikTok: %s", email)
    page.goto(_LOGIN_URL, wait_until="networkidle", timeout=45000)
    time.sleep(3)

    if _page_mentions_any(page, _CAPTCHA_MARKERS):
        log.error("TikTok pediu verificacao (captcha/slider) - nao resolvivel headless.")
        return False

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
        # Verifica se apareceu mensagem de erro/desafio
        captcha_hit = _page_mentions_any(page, _CAPTCHA_MARKERS)
        if captcha_hit:
            log.error("TikTok pediu verificacao (%r) durante o login - nao resolvivel headless.", captcha_hit)
            return False
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
    """Garante que estamos logados. Tenta storage_state primeiro, depois login.

    Cobre o caso de cookies expirados/invalidos: `_is_logged_in` sempre
    reflete a sessao REAL apos navegar (nao so a presenca do arquivo de
    storage_state), entao cookies vencidos caem automaticamente no fluxo
    de login por email/senha abaixo, sem tratamento especial.
    """
    if _is_logged_in(page):
        log.info("Sessao reaproveitada de %s (cookies validos).", state_path)
        return True

    log.info("Sessao ausente/expirada em %s. Tentando login com credenciais...", state_path)
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
    hashtags = _hashtags_for_tiktok(meta)
    hashtag_text = " ".join(f"#{h.lstrip('#')}" for h in hashtags)
    description = f"{title}\n\n{hashtag_text}".strip()[:2200]
    video_name = video_path.name
    _write_upload_state(video_name, "starting", f"headless={headless}")

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

        page = None
        try:
            # Reusa sessao salva se existir. Um storage_state corrompido
            # (JSON invalido, escrita parcial de uma run anterior que
            # crashou) faria new_context() levantar - trata como cookie
            # expirado/ausente e recomeca do zero em vez de derrubar o
            # upload inteiro por causa de um arquivo de cache ruim.
            storage_state = str(state_path) if state_path.exists() else None
            try:
                context = browser.new_context(
                    user_agent=_USER_AGENT,
                    viewport={"width": 1280, "height": 720},
                    locale="en-US",
                    timezone_id="America/Sao_Paulo",
                    storage_state=storage_state,
                )
            except Exception as exc:
                if storage_state is None:
                    raise
                log.warning("storage_state em %s parece corrompido (%s); descartando e logando do zero.",
                            state_path, exc)
                state_path.unlink(missing_ok=True)
                context = browser.new_context(
                    user_agent=_USER_AGENT,
                    viewport={"width": 1280, "height": 720},
                    locale="en-US",
                    timezone_id="America/Sao_Paulo",
                )
            context.add_init_script(_STEALTH_SCRIPT)

            page = context.new_page()
            page.set_default_timeout(120000)

            # Garante login
            _write_upload_state(video_name, "login", "verificando sessao")
            page.goto(_UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)

            if not _ensure_login(page, context, email, password, state_path):
                _write_upload_state(video_name, "failed", "login falhou (credenciais/captcha/timeout)")
                return None

            # Navega para upload
            _write_upload_state(video_name, "navigating", "indo para pagina de upload")
            page.goto(_UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)

            # Encontra o input de arquivo
            file_input = page.query_selector("input[type='file']")
            if not file_input:
                _write_upload_state(video_name, "failed", "input de arquivo nao encontrado")
                page.screenshot(path=str(ROOT / "_videos" / "tiktok_upload_fail.png"))
                return None

            _write_upload_state(video_name, "uploading_file", video_name)
            file_input.set_input_files(str(video_path))

            # Aguarda upload + processamento (pode demorar)
            for i in range(120):
                time.sleep(2)
                # Procura pelo campo de descricao (contenteditable)
                desc_el = page.query_selector("[contenteditable='true']")
                post_btn = page.query_selector("button:has-text('Post')")
                if desc_el and post_btn:
                    _write_upload_state(video_name, "processed", f"em {(i + 1) * 2}s")
                    break
                error_hit = _page_mentions_any(page, _POST_ERROR_MARKERS)
                if error_hit:
                    _write_upload_state(video_name, "failed", f"erro do TikTok durante processamento: {error_hit!r}")
                    page.screenshot(path=str(ROOT / "_videos" / "tiktok_upload_fail.png"))
                    return None
            else:
                _write_upload_state(video_name, "failed", "upload nao concluiu em 240s")
                return None

            # Preenche descricao
            desc_el.click()
            desc_el.fill("")
            for ch in description:
                page.keyboard.type(ch, delay=30)
            time.sleep(1)

            # Clica em Post
            _write_upload_state(video_name, "posting", "clicando Post")
            post_btn.click()

            # Aguarda confirmacao, verificando tambem por erro pos-click
            # (ex.: video rejeitado por diretrizes de comunidade) - sem
            # isso um erro silencioso passava como sucesso so por nao ter
            # mais o botao Post na tela.
            for _i in range(30):
                time.sleep(1)
                url = page.url
                if "/upload" not in url and "tiktok.com" in url:
                    _write_upload_state(video_name, "published", url)
                    _record_tiktok_post(video_name, title, url)
                    log.info("Video publicado! URL: %s", url)
                    return url
                error_hit = _page_mentions_any(page, _POST_ERROR_MARKERS)
                if error_hit:
                    _write_upload_state(video_name, "failed", f"erro do TikTok apos Post: {error_hit!r}")
                    page.screenshot(path=str(ROOT / "_videos" / "tiktok_upload_fail.png"))
                    return None

            _write_upload_state(video_name, "unconfirmed", "Post clicado mas sem confirmacao de redirect")
            return None

        except Exception as exc:
            _write_upload_state(video_name, "error", str(exc))
            log.error("Erro no upload TikTok: %s", exc)
            from utils.log_config import log_exception_to_file
            log_exception_to_file(exc, ROOT / "_videos")
            if page is not None:
                try:
                    page.screenshot(path=str(ROOT / "_videos" / "tiktok_error.png"))
                except Exception:
                    pass
            return None
        finally:
            browser.close()
