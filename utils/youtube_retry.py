"""utils/youtube_retry.py — retry e backoff para chamadas da YouTube Data API.

Extraido de upload_youtube.py para que utils/ seja autocontido: antes,
utils.playlist_manager importava _retry_youtube_call de upload_youtube
(modulo fora de utils/), criando acoplamento inverso. Agora todos os
modulos de utils/ que precisam de retry importam daqui.
"""

from __future__ import annotations

import logging
import random
import time

from googleapiclient.errors import HttpError

from utils.quota_tracker import record_usage

log = logging.getLogger(__name__)

_YOUTUBE_MAX_RETRIES = 3
_YOUTUBE_BASE_BACKOFF = 2.0

# YouTube returns 403 for several retryable quota/rate-limit conditions.
# Non-retryable 403s (forbidden, channelNotVerifiedForCustomThumbnails) stay
# terminal so we don't waste the retry budget on permanent rejections.
_RETRYABLE_403_REASONS = frozenset(
    {
        "quotaExceeded",
        "rateLimitExceeded",
        "userRateLimitExceeded",
        "dailyLimitExceeded",
        "downloadSizeQuotaExceeded",
    }
)


def _is_retryable_403(exc: HttpError) -> bool:
    """True se o HttpError 403 e uma condicao transitria de quota/rate-limit."""
    try:
        status = exc.resp.status if hasattr(exc, "resp") else 0
        if status != 403:
            return False
        reasons: list[str] = []
        content = exc.content
        if isinstance(content, bytes):
            content = content.decode("utf-8", "replace")
        import json

        data = json.loads(content) if content else {}
        for err in data.get("error", {}).get("errors", []):
            reason = err.get("reason", "")
            if reason:
                reasons.append(reason)
        return any(r in _RETRYABLE_403_REASONS for r in reasons)
    except Exception:
        return False


def _infer_resource_method(func) -> tuple[str | None, str | None]:
    """Tenta extrair (resource, method) de um callable da googleapiclient
    (ex.: service.videos().insert(...).execute). Retorna (None, None) se
    nao for possivel inferir - chamadas que nao vem da API nao sao contadas."""
    try:
        request = getattr(func, "__self__", None) or func
        # HttpRequest da googleapiclient tem atributo .uri com o resource
        # no path (/youtube/v3/videos) e .method (POST/GET). Mapeamos para
        # o nome do metodo (insert/list/etc) via heuristic no body/uri.
        uri = getattr(request, "uri", "") or ""
        http_method = (getattr(request, "method", "") or "").upper()
        # Ex.: https://www.googleapis.com/youtube/v3/videos?...
        parts = uri.split("/youtube/v3/", 1)
        if len(parts) != 2:
            return None, None
        rest = parts[1].split("?", 1)[0]
        resource = rest.split("/", 1)[0]
        method = None
        if http_method == "POST":
            method = "insert"
        elif http_method == "GET":
            method = "list"
        elif http_method == "PUT":
            method = "update"
        elif http_method == "DELETE":
            method = "delete"
        elif http_method == "PATCH":
            method = "bind"
        return resource or None, method
    except Exception:
        return None, None


def retry_youtube_call(func, *args, **kwargs):
    """Executa chamada YouTube API com retry e backoff exponencial.

    Sem circuit breaker (ao contrario de utils.ai_helper.ai_text, que tem
    um de verdade para o Gemini) - cada chamada tenta ate _YOUTUBE_MAX_RETRIES
    vezes independente de falhas anteriores nesta run.

    So faz retry em excecoes de rede transitórias (OSError/ConnectionError/
    TimeoutError cobre socket.error, ConnectionRefusedError, SSLError, etc).
    Bugs de programacao (TypeError, AttributeError, KeyError, ValueError)
    sao propagados imediatamente: antes, o `except Exception` amplo mascarava
    esses bugs como "falha de rede" e tentava 3x com backoff, fazendo a
    chamada demorar ~10s a mais pra falhar do mesmo jeito e escondendo o
    traceback real de quem debuga o log.

    Tambem registra o consumo de quota em _data/quota_usage.json (via
    utils.quota_tracker.record_usage) quando consegue inferir o
    resource/method do HttpRequest. A contagem so acontece apos sucesso
    (chamadas que falham e fazem retry contam uma vez quando finalmente
    sucedem - falhas de rede nao gastam quota do lado do YouTube).
    """
    for attempt in range(_YOUTUBE_MAX_RETRIES):
        try:
            result = func(*args, **kwargs)
            _record_quota(func)
            return result
        except HttpError as e:
            status = e.resp.status if hasattr(e, "resp") else 0
            if status in (409, 429, 500, 502, 503, 504) or _is_retryable_403(e):
                wait = _YOUTUBE_BASE_BACKOFF * (2**attempt) + random.uniform(0, 1)
                log.warning(
                    "YouTube API %s - retry em %ss (tentativa %d/%d)",
                    status,
                    wait,
                    attempt + 1,
                    _YOUTUBE_MAX_RETRIES,
                )
                time.sleep(wait)
                continue
            log.error("YouTube API HTTP %s - nao retryable: %s", status, e)
            raise
        except (OSError, ConnectionError, TimeoutError) as e:
            log.warning(
                "YouTube API erro de rede (tentativa %d/%d): %s",
                attempt + 1,
                _YOUTUBE_MAX_RETRIES,
                e,
            )
            if attempt < _YOUTUBE_MAX_RETRIES - 1:
                wait = _YOUTUBE_BASE_BACKOFF * (2**attempt)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("YouTube API: maximo de tentativas excedido sem resposta.")


def _record_quota(func) -> None:
    """Best-effort: registra quota consumida por uma chamada que acabou de
    suceder. Falhas aqui (inferencia sem .uri, IOError no arquivo) sao
    silenciosas - quota tracking e observabilidade, nao pode quebrar a
    chamada de negocio."""
    try:
        resource, method = _infer_resource_method(func)
        if resource and method:
            record_usage(resource, method)
    except Exception as exc:
        log.debug("Quota tracking pulada: %s", exc)
