"""
utils/caption_engine.py — gera legendas SRT automaticas via Gemini.

Cria um arquivo .srt com transcricao narrada do video e envia para o YouTube
como caption track. Legendas melhoram SEO e acessibilidade.
"""

from __future__ import annotations

import logging
from pathlib import Path

from utils.ai_helper import ai_text

log = logging.getLogger(__name__)


def generate_srt(hook: str, scene: str, duration: int, kind: str, emoji: str) -> str:
    """Gera conteudo SRT via Gemini, com fallback local.

    Retorna o texto completo do arquivo .srt.
    """
    prompt = (
        f"Crie legendas em portugues do Brasil para um {'Short' if kind == 'short' else 'video'} "
        f"de {duration} segundos sobre {hook} {emoji}. "
        f"O canal e Pata Jazz (gatos e cachorros fofos + jazz relaxante). "
        f"Crie 4-6 linhas de legenda curtas (max 40 chars cada), distribuindo ao longo da duracao. "
        f"Retorne APENAS o formato SRT (numerado, com timestamps HH:MM:SS,mmm --> HH:MM:SS,mmm)."
    )
    out = ai_text(prompt, task="caption")

    if out and " --> " in out:
        return out.strip()

    # Fallback: gerar SRT localmente
    return _fallback_srt(hook, duration)


def _fallback_srt(hook: str, duration: int) -> str:
    """Gera SRT simples com o hook dividido em 3 partes."""
    lines = [
        ("0:00:00,000", "0:00:03,000", hook[:40]),
        ("0:00:03,000", "0:00:08,000", "Bem-vindo ao Pata Jazz"),
        ("0:00:08,000", f"0:{duration//60:02d}:{duration%60:02d},000", "Gatinhos e cachorrinhos + jazz"),
    ]

    srt_lines: list[str] = []
    for i, (start, end, text) in enumerate(lines, 1):
        srt_lines.append(str(i))
        srt_lines.append(f"{start} --> {end}")
        srt_lines.append(text)
        srt_lines.append("")
    return "\n".join(srt_lines)


def save_srt(content: str, video_path: Path) -> Path:
    """Salva o SRT ao lado do video com o mesmo nome."""
    srt_path = video_path.with_suffix(".srt")
    srt_path.write_text(content, encoding="utf-8")
    log.info("SRT salvo: %s", srt_path)
    return srt_path