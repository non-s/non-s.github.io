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
        f"Create English captions for a {duration}-second {'Short' if kind == 'short' else 'video'} "
        f"about {hook} {emoji}. "
        f"The channel is Pata Jazz (cute cats and dogs + relaxing jazz). "
        f"Create 4-6 short caption lines (max 40 chars each), spread across the duration. "
        f"Return ONLY the SRT format (numbered, with timestamps HH:MM:SS,mmm --> HH:MM:SS,mmm)."
    )
    out = ai_text(prompt, task="caption")

    if out and " --> " in out:
        return out.strip()

    # Fallback: gerar SRT localmente
    return _fallback_srt(hook, duration)


def _fmt_ts(seconds: float) -> str:
    """Formata segundos como timestamp SRT ``HH:MM:SS,mmm`` (zero-padded)."""
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _fallback_srt(hook: str, duration: int) -> str:
    """Gera SRT simples com o hook dividido em 3 partes."""
    lines = [
        (_fmt_ts(0.0), _fmt_ts(min(3.0, duration)), hook[:40]),
        (_fmt_ts(min(3.0, duration)), _fmt_ts(min(8.0, duration)), "Welcome to Pata Jazz"),
        (_fmt_ts(min(8.0, duration)), _fmt_ts(float(duration)), "Cats and dogs + jazz"),
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
