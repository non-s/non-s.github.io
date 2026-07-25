"""
utils/metadata_engine.py — gera títulos, descrições e hashtags otimizados para YouTube.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

from utils.ai_helper import ai_text
from utils.seo_keywords import (
    generate_description,
    generate_hashtags,
    generate_title,
    optimize_for_search,
)

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
    kind: Literal["short", "horizontal", "live"],
    emoji: str,
    fallback_title: str = "",
    fallback_description: str = "",
) -> dict[str, Any]:
    """Gera metadados completos usando Gemini + SEO otimizado, com fallback local seguro."""
    # Extrai informações da cena para SEO
    s = scene.lower()
    animal = "gato" if ("cat" in s or "kitten" in s) else "cachorro"
    acao = "relaxando" if ("sleep" in s or "relax" in s) else "brincando"
    estilo_musical = "jazz relaxante"

    # Gera título otimizado com SEO, usando fallback_title como base se fornecido
    title = fallback_title or generate_title(
        animal=animal,
        acao=acao,
        estilo_musical=estilo_musical,
        kind=kind,
        emoji=emoji,
        duracao=round(duration / 60) if kind != "short" else None,
    )

    # Gera hashtags estratégicas em camadas
    categoria = "fofura"
    if "sleep" in s or "relax" in s:
        categoria = "relaxamento"
    elif "play" in s or "fun" in s:
        categoria = "diversao"

    hashtags = generate_hashtags(animal=animal, categoria=categoria, kind=kind)

    # Tenta melhorar com IA (opcional)
    prompt = _build_metadata_prompt(hook, scene, duration, kind, emoji)
    out = ai_text(prompt, json_mode=True, task=f"{kind}_metadata")

    description = generate_description(
        hook=hook,
        kind=kind,
        hashtags=hashtags,
        include_cta=True,
    ) or fallback_description

    if out:
        try:
            data = json.loads(out)
            # Usa título da IA se for valido e nao vazio; senao mantém título SEO.
            ai_title = str(data.get("title", "")).strip()[:100]
            if ai_title:
                title = ai_title

            # Usa descrição da IA se disponível
            ai_description = str(data.get("description", "")).strip()[:5000]
            if ai_description:
                description = ai_description

            # Merge de hashtags (filtra apenas strings, evita alucinacoes de dict/list)
            raw_hashtags = data.get("hashtags", [])
            if isinstance(raw_hashtags, str):
                raw_hashtags = raw_hashtags.split()
            ai_hashtags = [str(h).strip() for h in raw_hashtags
                           if isinstance(h, str) and h.strip()][:15]
            if ai_hashtags:
                hashtags = list(dict.fromkeys(hashtags + ai_hashtags))[:15]
        except Exception:
            log.warning("Falha ao parsear metadata JSON; usando fallback otimizado.")

    # Otimização final para busca
    title, description = optimize_for_search(title, description)

    # Garante prefixo de marca "Pata Jazz |" para consistencia
    if not title.startswith("Pata Jazz"):
        title = f"Pata Jazz | {title}"
    # Limita a 100 chars (limite do YouTube)
    if len(title) > 100:
        title = title[:97] + "..."

    # Garante que as hashtags apareçam na descrição (evita duplicar quando
    # generate_description ja as incluiu). So boundary de palavra DEPOIS da
    # hashtag (nao antes: "#" e o char antes dele - espaco/inicio - sao
    # ambos nao-palavra, entao \b nunca bate ali, o que fazia essa checagem
    # falhar sempre e duplicar as hashtags em toda descricao). O boundary
    # final ainda evita falso-positivo tipo "#Gato" combinando com "#Gatos".
    if hashtags and not any(re.search(rf"{re.escape(h)}\b", description) for h in hashtags):
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
