"""utils/notifier.py — envia alertas via webhook (Slack-compativel ou generico).

Lê a URL do webhook da variavel de ambiente ``LIQUID_WIRE_ALERT_WEBHOOK``. Se
nao estiver definida, apenas loga a mensagem e retorna False (sem falhar o
fluxo que chamou - o alerta e best-effort, nao bloqueante).

Sem dependencias externas: usa urllib.request da stdlib (o projeto so dep
de requests para a API do Gemini; alertas sao esporadicos e leves, nao
justifica adicionar outro cliente HTTP so por isso).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request

log = logging.getLogger(__name__)

WEBHOOK_ENV = "LIQUID_WIRE_ALERT_WEBHOOK"
_LEGACY_WEBHOOK_ENV = "PATA_JAZZ_ALERT_WEBHOOK"
_TIMEOUT_SECONDS = 10


def _is_slack_webhook(url: str) -> bool:
    return "hooks.slack.com" in url


def send_alert(message: str, level: str = "warning") -> bool:
    """Envia ``message`` para o webhook configurado em ``LIQUID_WIRE_ALERT_WEBHOOK``.

    Retorna True se enviou com sucesso, False caso contrario (webhook nao
    configurado, erro de rede ou HTTP != 2xx). Nunca levanta excecao: o
    alerta e best-effort e nao deve derrubar o workflow que o chamou.

    Suporta dois formatos de payload:
    - Slack-compatible (URL contem hooks.slack.com): ``{"text": message}``
    - Generico: ``{"level": level, "message": message, "source": "liquid-wire"}``
    """
    url = os.environ.get(WEBHOOK_ENV, "").strip()
    if not url:
        url = os.environ.get(_LEGACY_WEBHOOK_ENV, "").strip()
    if not url:
        log.info("Alerta (sem webhook configurado) [%s]: %s", level, message)
        return False

    if _is_slack_webhook(url):
        payload = {"text": message}
    else:
        payload = {"level": level, "message": message, "source": "liquid-wire"}

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(  # nosec B310
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:  # nosec B310
            status = getattr(resp, "status", 0) or resp.getcode()
            if 200 <= status < 300:
                log.info("Alerta enviado via webhook (HTTP %s): %s", status, message)
                return True
            log.warning("Webhook respondeu HTTP %s: %s", status, message)
            return False
    except Exception as exc:
        log.warning("Falha ao enviar alerta via webhook (%s): %s", type(exc).__name__, exc)
        return False
