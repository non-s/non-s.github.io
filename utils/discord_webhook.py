"""
utils/discord_webhook.py — envia notificações para Discord via webhook.

Usado para notificar início/fim de lives, uploads de vídeos, ou erros críticos.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

log = logging.getLogger(__name__)

_DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
_TIMEOUT = 10  # segundos


def send_notification(
    title: str,
    message: str,
    color: int = 0x00ff00,  # verde por padrão
    thumbnail_url: str | None = None,
) -> bool:
    """Envia notificação embed para Discord.
    
    Args:
        title: Título da notificação.
        message: Mensagem principal.
        color: Cor do embed em hexadecimal (ex: 0x00ff00 para verde).
        thumbnail_url: URL opcional de thumbnail para exibir.
    
    Returns:
        True se enviado com sucesso, False caso contrário.
    """
    if not _DISCORD_WEBHOOK_URL:
        log.warning("DISCORD_WEBHOOK_URL não configurado; pulando notificação.")
        return False
    
    embed: dict[str, Any] = {
        "title": title,
        "description": message,
        "color": color,
    }
    
    if thumbnail_url:
        embed["thumbnail"] = {"url": thumbnail_url}
    
    payload = {
        "embeds": [embed],
        "username": "Pata Jazz Bot 🐾🎷",
    }
    
    try:
        response = requests.post(
            _DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=_TIMEOUT,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        log.info("Notificação Discord enviada: %s", title)
        return True
    except requests.exceptions.RequestException as exc:
        log.error("Falha ao enviar notificação Discord: %s", exc)
        return False


def notify_live_start(title: str, stream_url: str, thumbnail: str | None = None) -> bool:
    """Notifica início de live."""
    message = f"🔴 **LIVE NO AR!**\n\n{title}\n\n🔗 URL: {stream_url}"
    return send_notification(
        title="🎷 Pata Jazz Live Iniciou!",
        message=message,
        color=0xff0000,  # vermelho
        thumbnail_url=thumbnail,
    )


def notify_live_end(title: str, duration_minutes: int) -> bool:
    """Notifica fim de live."""
    message = f"✅ Live encerrada após **{duration_minutes} minutos**.\n\nObrigado por assistir! 🐾🎷"
    return send_notification(
        title="🔴 Pata Jazz Live Encerrada",
        message=message,
        color=0x808080,  # cinza
    )


def notify_video_upload(title: str, video_url: str, thumbnail: str | None = None) -> bool:
    """Notifica upload de novo vídeo."""
    message = f"🎬 **Novo vídeo no ar!**\n\n{title}\n\n🔗 Assista: {video_url}"
    return send_notification(
        title="🐾 Novo Vídeo Pata Jazz",
        message=message,
        color=0x0000ff,  # azul
        thumbnail_url=thumbnail,
    )


def notify_error(error_message: str, stack_trace: str | None = None) -> bool:
    """Notifica erro crítico."""
    message = f"❌ **Erro Crítico**\n\n{error_message}"
    if stack_trace:
        message += f"\n\n```\n{stack_trace[:1000]}\n```"  # Limita a 1000 chars
    return send_notification(
        title="🚨 Erro Pata Jazz",
        message=message,
        color=0xff0000,  # vermelho
    )
