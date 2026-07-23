"""
utils/metadata_engine.py — gera títulos, descrições e hashtags otimizados para YouTube.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from utils.ai_helper import ai_text

log = logging.getLogger(__name__)


def _build_metadata_prompt(hook: str, scene: str, duration: int, kind: str, emoji: str) -> str:
    target_len = 80 if kind == "short" else 100
    desc_lines = 3 if kind == "short" else 4
    return (
        f"Crie metadados em português do Brasil para um {'Short' if kind == 'short' else 'vídeo'} "
        f"do YouTube sobre {hook} {emoji}. O canal é Pata Jazz (gatos e cachorros fofos + jazz relaxante). "
        f"Duração: ~{duration}s. "
        f"Regras:\n"
        f"- Título amigável, fofo, SEM clickbait, SEM palavras sensacionalistas, máximo {target_len} caracteres.\n"
        f"- Descrição de {desc_lines} linhas, leve, com tom fofo, com emoji de gato/cachorro e jazz.\n"
        f"- 5 a 8 hashtags relevantes separadas por espaço.\n"
        f"Retorne APENAS JSON com chaves: title, description, hashtags."
    )


def generate_metadata(
    hook: str,
    scene: str,
    duration: int,
    kind: str,
    emoji: str,
    fallback_title: str = "",
    fallback_description: str = "",
) -> dict[str, Any]:
    """Gera metadados completos usando Gemini, com fallback local seguro."""
    prompt = _build_metadata_prompt(hook, scene, duration, kind, emoji)
    out = ai_text(prompt, json_mode=True, task=f"{kind}_metadata")

    title = fallback_title or f"{hook} | Pata Jazz"
    description = fallback_description or (
        f"{hook} com jazz de fundo. 🐾🎷 Curta, relaxe e acompanhe os bichinhos fofos. #PataJazz"
    )
    hashtags: list[str] = ["#PataJazz", "#Gatos", "#Cachorros", "#Jazz"]

    if out:
        try:
            data = json.loads(out)
            title = str(data.get("title", title))[:100]
            description = str(data.get("description", description))[:5000]
            raw_hashtags = data.get("hashtags", [])
            if isinstance(raw_hashtags, str):
                raw_hashtags = raw_hashtags.split()
            hashtags = [str(h).strip() for h in raw_hashtags if str(h).strip()][:15]
        except Exception:
            log.warning("Falha ao parsear metadata JSON; usando fallback.")

    # Garante que as hashtags apareçam na descrição
    if hashtags and not any(h in description for h in hashtags):
        description = f"{description}\n\n{' '.join(hashtags)}"

    return {
        "title": title,
        "description": description,
        "hashtags": hashtags,
    }


def clean_title(title: str) -> str:
    """Remove aspas duplas e excesso de espaços do título."""
    cleaned = title.replace('"', "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned
