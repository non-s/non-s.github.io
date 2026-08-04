"""
utils/metadata_engine.py — gera títulos, descrições e hashtags otimizados para YouTube.
"""

from __future__ import annotations

import json
import logging
import random
import re
from typing import Any, Literal

from utils.ai_helper import ai_text, is_safe_ai_text
from utils.animal_branding import detect_animal
from utils.channel_config import active_channel
from utils.seo_keywords import (
    _MAX_HASHTAGS,
    generate_description,
    generate_hashtags,
    generate_title_with_pattern,
    music_style_for_mood,
    optimize_for_search,
    title_is_too_repetitive,
)

log = logging.getLogger(__name__)


def _build_metadata_prompt(hook: str, scene: str, duration: int, kind: str, emoji: str) -> str:
    target_len = 80 if kind == "short" else 100
    desc_lines = 3 if kind == "short" else 4
    channel_name = active_channel.name
    default_desc = active_channel.default_description
    return (
        f"Create English YouTube metadata for a {'Short' if kind == 'short' else 'video'} "
        f"about {hook} {emoji}. The channel is {channel_name} ({default_desc}), "
        f"targeting searches like 'relaxing music for cats/dogs' and 'pet anxiety music'. "
        f"Duration: ~{duration}s. "
        f"Rules:\n"
        f"- Warm, cute title, NO clickbait, NO sensationalist words, max {target_len} characters.\n"
        f"- Sound like a real person posting a video they like, not an ad - "
        f"skip stock phrases like 'Discover' or 'Get ready', skip generic "
        f"'welcome to my channel' openers, no dramatic em-dashes.\n"
        f"- {desc_lines}-line description, light and cute tone, with a cat/dog and music emoji.\n"
        f"- 5 to 8 relevant hashtags separated by spaces.\n"
        f"Return ONLY JSON with keys: title, description, hashtags."
    )


def generate_metadata(
    hook: str,
    scene: str,
    duration: int,
    kind: Literal["short"],
    emoji: str,
    fallback_title: str = "",
    fallback_description: str = "",
    title_pattern_hint: str = "",
    mood: str = "",
) -> dict[str, Any]:
    """Gera metadados completos com SEO agressivo (Operação Zeus).

    Títulos espelham palavras-chave de alto volume real, descrições são longas
    e semanticamente otimizadas, hashtags atacam problema + animal + música.
    """
    animal = detect_animal(scene)
    s = scene.lower()

    # Mapeia cena para mood SEO
    if "sleep" in s or "nap" in s:
        acao = "sleep"
    elif "anxious" in s or "nervous" in s or "scared" in s or "hiding" in s:
        acao = "anxiety"
    elif "play" in s or "fun" in s:
        acao = "diversao"
    elif "relax" in s:
        acao = "relax"
    else:
        acao = mood or "relax"

    estilo_musical = music_style_for_mood(acao)

    title_pattern = "fallback_provided"
    if title_pattern_hint:
        title, title_pattern = generate_title_with_pattern(
            animal=animal,
            acao=acao,
            estilo_musical=estilo_musical,
            kind=kind,
            emoji=emoji,
            duracao=round(duration / 60) if kind != "short" else None,
            pattern=title_pattern_hint,
        )
    elif fallback_title:
        title = fallback_title
    else:
        title, title_pattern = generate_title_with_pattern(
            animal=animal,
            acao=acao,
            estilo_musical=estilo_musical,
            kind=kind,
            emoji=emoji,
            duracao=round(duration / 60) if kind != "short" else None,
        )

    categoria = "relaxation"
    if "sleep" in s or "nap" in s:
        categoria = "sleep"
    elif "anxious" in s or "nervous" in s or "scared" in s:
        categoria = "anxiety"
    elif "play" in s or "fun" in s:
        categoria = "fun"

    hashtags = generate_hashtags(animal=animal, categoria=categoria, kind=kind)

    description, cta_used = generate_description(
        hook=hook,
        kind=kind,
        hashtags=hashtags,
        include_cta=True,
        animal=animal,
        mood=acao,
        title=title,
    )
    if not description:
        description = fallback_description

    # IA opcional: tenta melhorar título/descricao, mas SEO Zeus tem prioridade.
    # Em 80% dos casos usamos o título/descricao local (mais previsível e rápido);
    # em 20% deixamos a IA sugerir alternativas, mantendo a marca e as keywords.
    if random.random() < 0.20:  # noqa: S311 - nao e seguranca
        prompt = _build_metadata_prompt(hook, scene, duration, kind, emoji)
        out = ai_text(prompt, json_mode=True, task=f"{kind}_metadata")
        if out:
            try:
                data = json.loads(out)
                ai_title = str(data.get("title", "")).strip()[:100]
                if ai_title and is_safe_ai_text(ai_title):
                    # Mantém prefixo de marca e garante keyword
                    if not ai_title.startswith(active_channel.brand_prefix.removesuffix(" |")):
                        ai_title = f"{active_channel.brand_prefix} {ai_title}"
                    title = ai_title
                    title_pattern = "ai_generated"

                ai_description = str(data.get("description", "")).strip()[:5000]
                if ai_description and is_safe_ai_text(ai_description):
                    description = ai_description

                raw_hashtags = data.get("hashtags", [])
                if isinstance(raw_hashtags, str):
                    raw_hashtags = raw_hashtags.split()
                ai_hashtags = [str(h).strip() for h in raw_hashtags if isinstance(h, str) and h.strip()][:_MAX_HASHTAGS]
                if ai_hashtags:
                    hashtags = list(dict.fromkeys(ai_hashtags + hashtags))[:_MAX_HASHTAGS]
            except Exception:
                log.warning("Falha ao parsear metadata JSON; usando SEO local.")

    # Anti-repeat: evita títulos quase-duplicados
    if title_is_too_repetitive(title):
        for _attempt in range(5):
            title2, pat2 = generate_title_with_pattern(
                animal=animal,
                acao=acao,
                estilo_musical=estilo_musical,
                kind=kind,
                emoji=emoji,
                duracao=round(duration / 60) if kind != "short" else None,
            )
            if not title_is_too_repetitive(title2):
                title = title2
                title_pattern = pat2
                break
        else:
            log.warning(
                "Anti-repeat: 5 re-sorteios ainda colidem com titulos recentes; mantendo %r (best-effort).",
                title,
            )

    # Otimização final para busca
    title, description = optimize_for_search(title, description)

    # Garante prefixo de marca
    brand_prefix = active_channel.brand_prefix
    if not title.startswith(brand_prefix.removesuffix(" |")):
        title = f"{brand_prefix} {title}"
    if len(title) > 100:
        title = title[:97] + "..."

    # Garante que as hashtags apareçam na descrição
    if hashtags and not any(re.search(rf"{re.escape(h)}\b", description) for h in hashtags):
        description = f"{description}\n\n{' '.join(hashtags)}"

    return {
        "title": title,
        "description": description,
        "hashtags": hashtags,
        "title_pattern": title_pattern,
        "cta": cta_used,
    }


def clean_title(title: str) -> str:
    """Remove aspas duplas e excesso de espaços do título."""
    cleaned = title.replace('"', "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned
