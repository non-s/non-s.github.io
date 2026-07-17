"""Pinned-comment handoff text for the just-uploaded Short."""

from __future__ import annotations


def pinned_comment_payload(meta: dict, handoff: dict | None = None) -> str:
    handoff = handoff or {}
    title = str(handoff.get("title") or "").strip()
    url = str(handoff.get("url") or "").strip()
    if title and url:
        return f"Assista a seguir: {title[:72]} {url}"
    series = str(meta.get("series") or meta.get("category") or "Wild Brief").strip()
    return f"Próximo episódio: acompanhe a saga de vídeos sobre {series} na nossa playlist do canal."
