"""
utils/youtube_oauth.py — autenticacao OAuth2 com a YouTube Data API.

Em CI (GitHub Actions), o fluxo manual ``flow.run_local_server`` nao pode
rodar (nao ha browser). Para que CI funcione, o token salvo em
``youtube_token.json`` (ou no secret ``YOUTUBE_TOKEN``) deve incluir
``refresh_token`` + ``client_id``/``client_secret`` para que
``google-auth`` renove o ``access_token`` expirado em memoria, sem
interacao humana.

IMPORTANTE (CI): o ``youtube_token.json`` no runner e efemero — e apagado no
fim do job. O refresh acontece em memoria e o ``access_token`` novo e usado
naquela run, porem **o secret ``YOUTUBE_TOKEN`` no GitHub NAO e atualizado
automaticamente** (exigiria ``gh secret set`` com permissoes extras que nao
configuramos). Consequencia: quando o ``refresh_token`` expirar (90 dias
padrao do Google sem uso), o refresh vai falhar e a CI quebrara. Nesse caso,
rodar ``python utils/youtube_oauth.py`` localmente (com
``YOUTUBE_CLIENT_SECRET`` apontando para o client_secret.json) para gerar um
token novo e atualizar o secret ``YOUTUBE_TOKEN`` manualmente.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

log = logging.getLogger(__name__)

# yt-analytics.readonly: necessario para o YouTube Analytics API
# (retention/CTR). Adicionar este scope exige RE-AUTORIZAR o token OAuth:
# o refresh_token salvo em youtube_token.json nao cobre o novo scope e o
# google-auth ignora o mismatch silenciosamente (a chamada a Analytics
# retorna 403). Rode `python utils/youtube_oauth.py` localmente para gerar
# um token novo com o scope atualizado e atualize o secret YOUTUBE_TOKEN.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    # #4: force-ssl e estritamente necessario - cobre channels.update
    # (identity), comments.insert (engagement), videos.update (A/B title
    # rotation), playlists.insert, captions.insert. youtube.upload so
    # cobre videos.insert + thumbnails.set. Remover force-ssl quebra 5
    # workflows essenciais. Avaliado e mantido.
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def validate_token_scopes(token_path: str | None = None) -> list[str]:
    """#4: valida que o token OAuth tem todos os scopes necessarios.

    Retorna lista de scopes FALTANTES (vazia se tudo OK). Usado pelo
    healthcheck e pelo oauth-token-refresh.yml para detectar tokens
    expirados/invalidos antes que os workflows falhem em producao.

    Causa comum de scopes faltantes: token gerado com client_secret de
    um projeto diferente do que tem as APIs habilitadas.
    """
    path = Path(token_path) if token_path else Path(_token_path())
    if not path.exists():
        return list(SCOPES)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Credentials guarda scopes em "scopes" (lista) ou no campo
        # "token_uri" adjacente. google-auth serializa como "scopes".
        token_scopes = data.get("scopes") or []
        if isinstance(token_scopes, str):
            token_scopes = [token_scopes]
        token_set = {str(s) for s in token_scopes}
        return [s for s in SCOPES if s not in token_set]
    except Exception:
        return list(SCOPES)

ROOT = Path(__file__).resolve().parent.parent

# Janela de antecipacao do refresh: se faltam menos que isso para expirar,
# renovamos proativamente para evitar 401 no meio de uma chamada.
_REFRESH_MARGIN = timedelta(minutes=5)


def _token_path() -> str:
    """Caminho do token OAuth. Resolvido relativo ao ROOT do projeto."""
    env_path = os.environ.get("YOUTUBE_TOKEN_PATH")
    if env_path:
        return env_path
    return str(ROOT / "youtube_token.json")


def _load_token() -> Credentials | None:
    token_path = _token_path()
    if not Path(token_path).exists():
        return None
    try:
        with open(token_path, encoding="utf-8") as f:
            data = json.load(f)
        return Credentials.from_authorized_user_info(data, SCOPES)
    except Exception as exc:
        log.warning("Token invalido em %s: %s", token_path, exc)
        return None


def _save_token(creds: Credentials, token_path: str | None = None) -> None:
    if token_path is None:
        token_path = _token_path()
    Path(token_path).parent.mkdir(parents=True, exist_ok=True)
    # Cria com permissoes 0600 desde o inicio para proteger o refresh_token.
    old_umask = os.umask(0o077)
    try:
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    finally:
        os.umask(old_umask)


def _client_secrets_path() -> str | None:
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    if client_secret:
        # Cria o arquivo temporario com permissoes restritas desde o inicio.
        old_umask = os.umask(0o077)
        try:
            fd, tmp_path = tempfile.mkstemp(prefix="client_secret_", suffix=".json")
        finally:
            os.umask(old_umask)
        # tmp_path so existe se mkstemp() teve sucesso; separado do bloco
        # acima para nao referenciar uma variavel nao definida no except
        # caso o proprio mkstemp() falhe (mascarando o erro real com NameError).
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(client_secret)
            return tmp_path
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise
    client_secret_path = os.environ.get("YOUTUBE_CLIENT_SECRET_PATH", str(ROOT / "client_secret.json"))
    if Path(client_secret_path).exists():
        return client_secret_path
    return None


def refresh_token_if_needed(token_path: Path) -> bool:
    """Renova o ``access_token`` expirado/quoti-expirado em ``token_path``.

    Le o token, e se ``expiry`` < agora + 5 min, chama
    ``Credentials.refresh(Request())`` e salva o token atualizado de volta no
    disco. Retorna ``True`` se renovou, ``False`` caso contrario. Nao levanta
    em falha — loga warning e retorna ``False`` (fallback para o fluxo normal
    em ``get_youtube_service``).

    Cenarios em que retorna ``False`` sem tentar refresh:
      - arquivo inexistente ou JSON invalido
      - token sem ``expiry`` ou sem ``refresh_token`` (sem refresh_token nao
        ha como renovar; sem expiry nao sabemos se precisa)
    """
    try:
        if not token_path.exists():
            return False
        with open(token_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        log.warning("refresh_token_if_needed: nao foi ler %s: %s", token_path, exc)
        return False

    if not data.get("refresh_token"):
        # Sem refresh_token nao ha como renovar; deixa o fluxo normal decidir.
        return False
    if not data.get("expiry"):
        # Sem expiry registrado, nao sabemos se precisa renovar. Deixa o
        # fluxo normal tratar (credenciais validas/expiradas sao decididas
        # por Credentials.valid no get_youtube_service).
        return False

    try:
        creds = Credentials.from_authorized_user_info(data, SCOPES)
    except Exception as exc:
        log.warning("refresh_token_if_needed: token invalido em %s: %s", token_path, exc)
        return False

    expiry = creds.expiry
    if expiry is None:
        return False

    # Normaliza timezone: google-auth devolve naive (UTC) em producao, mas
    # se vier aware fazemos comparacao contra agora aware para evitar erro.
    now = datetime.now(expiry.tzinfo) if expiry.tzinfo else datetime.now(UTC).replace(tzinfo=None)
    if expiry > now + _REFRESH_MARGIN:
        # Ainda valido por mais que a margem: nada a fazer.
        return False

    try:
        creds.refresh(Request())
    except Exception as exc:
        log.warning("refresh_token_if_needed: falha ao renovar token em %s: %s", token_path, exc)
        return False

    try:
        _save_token(creds, str(token_path))
    except Exception as exc:
        # O refresh em si deu certo; so falhou persistir. Loga e ainda
        # retorna True pois o access_token novo ja esta em creds (utilizado
        # in-memory pelo get_youtube_service que chama esta funcao).
        log.warning("refresh_token_if_needed: token renovado mas falhou ao salvar em %s: %s", token_path, exc)
    return True


def _acquire_credentials() -> Credentials:
    """Carrega/renova/obtem credenciais OAuth validas (logica compartilhada
    por get_youtube_service e get_youtube_analytics_service)."""
    refresh_token_if_needed(Path(_token_path()))

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
            creds = flow.run_local_server(port=0, timeout=60)
        finally:
            # Remove apenas arquivos temporarios criados por este modulo.
            if secrets_path.startswith(tempfile.gettempdir()):
                Path(secrets_path).unlink(missing_ok=True)
        _save_token(creds)
    return creds


def get_youtube_service() -> Resource:
    # Renova proativamente o access_token se proximo da expiracao, antes de
    # buildar o service. Isso garante que em CI (sem fluxo manual) o token
    # esteja valido quando ``build`` for chamado.
    creds = _acquire_credentials()
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def get_youtube_analytics_service() -> Resource:
    """Builda o service do YouTube Analytics API (retention/CTR).

    Reusa as mesmas credenciais do Data API v3, mas exige o scope
    yt-analytics.readonly em SCOPES (ver comentario no topo de SCOPES) - se o
    token salvo nao cobrir esse scope, a chamada a reports().query() retorna
    403 e o caller deve tratar (o _collect_retention_metrics em
    collect_analytics.py envolve a chamada em try/except)."""
    creds = _acquire_credentials()
    return build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
