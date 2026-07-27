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

log = logging.getLogger(__name__)

_YOUTUBE_MAX_RETRIES = 3
_YOUTUBE_BASE_BACKOFF = 2.0


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
    """
    for attempt in range(_YOUTUBE_MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except HttpError as e:
            status = e.resp.status if hasattr(e, 'resp') else 0
            if status in (409, 429, 500, 502, 503, 504):
                wait = _YOUTUBE_BASE_BACKOFF * (2 ** attempt) + random.uniform(0, 1)
                log.warning(
                    "YouTube API %s - retry em %ss (tentativa %d/%d)",
                    status, wait, attempt + 1, _YOUTUBE_MAX_RETRIES,
                )
                time.sleep(wait)
                continue
            log.error("YouTube API HTTP %s - nao retryable: %s", status, e)
            raise
        except (OSError, ConnectionError, TimeoutError) as e:
            log.warning(
                "YouTube API erro de rede (tentativa %d/%d): %s",
                attempt + 1, _YOUTUBE_MAX_RETRIES, e,
            )
            if attempt < _YOUTUBE_MAX_RETRIES - 1:
                wait = _YOUTUBE_BASE_BACKOFF * (2 ** attempt)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("YouTube API: maximo de tentativas excedido sem resposta.")
