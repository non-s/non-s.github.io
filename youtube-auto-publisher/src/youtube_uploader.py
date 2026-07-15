"""
youtube_uploader.py - Upload de videos para o YouTube
Gerencia autenticacao OAuth e upload via YouTube Data API v3
"""
import json
import os
import random
import time
from pathlib import Path
from loguru import logger
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
import config


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = Path("token.json")
CLIENT_SECRETS_FILE = Path("client_secrets.json")
RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Reasons the YouTube Data API uses in a 403 error body when the caller has
# exhausted its daily quota or per-channel upload allowance. These are not
# transient/retriable like the codes above - retrying immediately will not
# help - so they are detected and handled distinctly from other 403s.
QUOTA_ERROR_REASONS = {"quotaExceeded", "uploadLimitExceeded"}


class QuotaExceededError(RuntimeError):
    """Raised when YouTube reports the daily API quota or upload limit was exceeded.

    This is an expected, recoverable-on-a-later-run condition (similar to the
    "daily video limit" skip already handled in main.py), not a generic
    pipeline failure. Callers should catch it specifically and exit
    gracefully instead of letting an unhandled HttpError propagate.
    """

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"YouTube API quota/upload limit exceeded (reason={reason!r})")


class YouTubeUploader:
    """Gerencia upload de videos para o YouTube"""

    def __init__(self):
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Autentica com a API do YouTube"""
        creds = None
        creds_source = None

        # 1. Tenta usar token do GitHub Secret (CI/CD)
        token_json_str = config.YOUTUBE_TOKEN_JSON
        if token_json_str:
            try:
                token_data = json.loads(token_json_str)
                creds = Credentials.from_authorized_user_info(token_data, SCOPES)
                creds_source = "env"
                logger.info("Usando token do ambiente (GitHub Secret)")
            except Exception as e:
                logger.warning(f"Erro ao carregar token do ambiente: {type(e).__name__}")

        # 2. Tenta usar token.json local
        if not creds and TOKEN_FILE.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
                creds_source = "file"
                logger.info("Usando token local (token.json)")
            except Exception as e:
                logger.warning(f"Erro ao carregar token local: {type(e).__name__}")

        # 3. Renova token expirado
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Token renovado com sucesso")
                if creds_source == "file":
                    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
            except Exception as e:
                logger.error(f"Erro ao renovar token: {type(e).__name__}")
                creds = None

        # 4. Fluxo OAuth interativo (apenas local)
        if not creds or not creds.valid:
            if os.getenv("CI"):
                raise RuntimeError(
                    "Credenciais YouTube invalidas no CI. Configure YOUTUBE_TOKEN_JSON "
                    "com refresh_token valido nos GitHub Actions secrets."
                )
            if CLIENT_SECRETS_FILE.exists():
                logger.info("Iniciando fluxo OAuth interativo...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CLIENT_SECRETS_FILE), SCOPES
                )
                creds = flow.run_local_server(port=0)
                TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
                logger.success(f"Token salvo em {TOKEN_FILE}")
            else:
                # Tenta usar client_id/secret do ambiente
                if not config.YOUTUBE_CLIENT_ID or not config.YOUTUBE_CLIENT_SECRET:
                    raise RuntimeError(
                        "YOUTUBE_CLIENT_ID e YOUTUBE_CLIENT_SECRET sao obrigatorios para OAuth local"
                    )
                client_config = {
                    "installed": {
                        "client_id": config.YOUTUBE_CLIENT_ID,
                        "client_secret": config.YOUTUBE_CLIENT_SECRET,
                        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                }
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                creds = flow.run_local_server(port=0)
                TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
                logger.success(f"Token salvo em {TOKEN_FILE}")

        self.service = build("youtube", "v3", credentials=creds)
        logger.success("Autenticado com YouTube API v3")

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list = None,
        privacy_status: str = "private",
        category_id: str = None,
    ) -> dict:
        """Faz upload de video para o YouTube e retorna a resposta da API."""
        if not self.service:
            raise RuntimeError("Servico YouTube nao autenticado")

        cat_id = category_id or config.VIDEO_CATEGORY_ID

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags or [],
                "categoryId": cat_id,
                "defaultLanguage": "pt",
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 5,  # 5 MB chunks
        )

        logger.info(f"Iniciando upload: '{title[:50]}'...")
        request = self.service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        retry_count = 0
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.info(f"Upload: {progress}%")
                retry_count = 0
            except HttpError as exc:
                status_code = getattr(exc.resp, "status", None)
                if status_code == 403:
                    reason = self._extract_error_reason(exc)
                    if reason in QUOTA_ERROR_REASONS:
                        logger.error(
                            f"Cota/limite de upload do YouTube excedido (reason={reason}). "
                            "Encerrando esta publicacao com seguranca; novas tentativas "
                            "so devem ocorrer apos a renovacao da cota diaria da API."
                        )
                        raise QuotaExceededError(reason) from exc
                if status_code not in RETRIABLE_STATUS_CODES:
                    raise
                retry_count = self._sleep_before_retry(retry_count, f"HTTP {status_code}")
            except (OSError, TimeoutError, ConnectionError) as exc:
                retry_count = self._sleep_before_retry(retry_count, type(exc).__name__)

        video_id = response.get("id")
        logger.success(f"Video publicado! ID: {video_id}")
        logger.success(f"URL: https://youtu.be/{video_id}")
        return response

    def _sleep_before_retry(self, retry_count: int, reason: str) -> int:
        if retry_count >= config.MAX_UPLOAD_RETRIES:
            raise RuntimeError(f"Upload falhou apos {config.MAX_UPLOAD_RETRIES} retries: {reason}")
        next_retry = retry_count + 1
        sleep_seconds = min(
            (2 ** retry_count) + random.random(),
            config.UPLOAD_RETRY_MAX_SLEEP_SECONDS,
        )
        logger.warning(
            f"Upload temporariamente indisponivel ({reason}); retry "
            f"{next_retry}/{config.MAX_UPLOAD_RETRIES} em {sleep_seconds:.1f}s"
        )
        time.sleep(sleep_seconds)
        return next_retry

    @staticmethod
    def _extract_error_reason(exc: HttpError) -> str:
        """Extrai o campo 'reason' do corpo JSON de erro de uma HttpError.

        Retorna string vazia se o corpo nao estiver presente ou nao for JSON
        valido, para que o chamador trate isso como "motivo desconhecido"
        em vez de falhar ao interpretar o erro.
        """
        content = getattr(exc, "content", b"") or b""
        if isinstance(content, bytes):
            try:
                content = content.decode("utf-8")
            except UnicodeDecodeError:
                return ""
        try:
            payload = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return ""
        error_body = payload.get("error", {}) if isinstance(payload, dict) else {}
        errors = error_body.get("errors") or []
        if errors and isinstance(errors[0], dict):
            reason = errors[0].get("reason")
            if reason:
                return reason
        return error_body.get("status", "") or ""

    def get_channel_info(self) -> dict:
        """Retorna informacoes do canal autenticado"""
        try:
            response = self.service.channels().list(
                part="snippet,statistics",
                mine=True,
            ).execute()
            items = response.get("items", [])
            if items:
                channel = items[0]
                return {
                    "id": channel["id"],
                    "name": channel["snippet"]["title"],
                    "subscribers": channel["statistics"].get("subscriberCount", "N/A"),
                    "videos": channel["statistics"].get("videoCount", "N/A"),
                    "views": channel["statistics"].get("viewCount", "N/A"),
                }
        except Exception as e:
            logger.error(f"Erro ao obter info do canal: {e}")
        return {}
