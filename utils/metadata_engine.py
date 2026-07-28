"""
utils/metadata_engine.py — gera títulos, descrições e hashtags otimizados para YouTube.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

from utils.ai_helper import ai_text, is_safe_ai_text
from utils.animal_branding import detect_animal
from utils.seo_keywords import (
    _MAX_HASHTAGS,
    generate_description,
    generate_hashtags,
    generate_title_with_pattern,
    optimize_for_search,
)

log = logging.getLogger(__name__)


def _build_metadata_prompt(hook: str, scene: str, duration: int, kind: str, emoji: str) -> str:
    target_len = 80 if kind == "short" else 100
    desc_lines = 3 if kind == "short" else 4
    return (
        f"Create English YouTube metadata for a {'Short' if kind == 'short' else 'video'} "
        f"about {hook} {emoji}. The channel is Pata Jazz (cute cats and dogs + relaxing jazz), "
        f"targeting searches like 'relaxing music for cats/dogs' and 'pet anxiety music'. "
        f"Duration: ~{duration}s. "
        f"Rules:\n"
        f"- Warm, cute title, NO clickbait, NO sensationalist words, max {target_len} characters.\n"
        f"- {desc_lines}-line description, light and cute tone, with a cat/dog and jazz emoji.\n"
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
) -> dict[str, Any]:
    """Gera metadados completos usando Gemini + SEO otimizado, com fallback local seguro.

    ``title_pattern_hint`` (quando fornecido por utils/slot_optimizer) obriga
    o titulo a seguir o padrao previsto como otimo para o slot atual; quando
    vazio, o padrao e decidido por generate_title_with_pattern/IA como antes.
    """
    # Extrai informações da cena para SEO
    animal = detect_animal(scene)
    s = scene.lower()
    acao = "relaxing" if ("sleep" in s or "relax" in s) else "playing"
    estilo_musical = "relaxing jazz"

    # Gera título otimizado com SEO, usando fallback_title como base se fornecido.
    # Antes, "fallback_title" era uma magic string que poluia o tracking de
    # padroes em video_tags.json/title_pattern_performance.json. Agora usamos
    # um valor explicito para distinguir "fallback fornecido" de "sem padrao".
    title_pattern = "fallback_provided"
    if title_pattern_hint:
        # Slot optimizer determinou o padrao otimo; forca o titulo a segui-lo.
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

    # Gera hashtags estratégicas em camadas
    categoria = "cuteness"
    if "sleep" in s or "relax" in s:
        categoria = "relaxation"
    elif "play" in s or "fun" in s:
        categoria = "fun"

    hashtags = generate_hashtags(animal=animal, categoria=categoria, kind=kind)

    # Tenta melhorar com IA (opcional)
    prompt = _build_metadata_prompt(hook, scene, duration, kind, emoji)
    out = ai_text(prompt, json_mode=True, task=f"{kind}_metadata")

    description, cta_used = generate_description(
        hook=hook,
        kind=kind,
        hashtags=hashtags,
        include_cta=True,
    )
    if not description:
        description = fallback_description

    if out:
        try:
            data = json.loads(out)
            # Usa título da IA se for valido, nao vazio e nao suspeito; senao
            # mantém título SEO.
            ai_title = str(data.get("title", "")).strip()[:100]
            if ai_title and is_safe_ai_text(ai_title):
                title = ai_title
                title_pattern = "ai_generated"
            elif ai_title:
                log.warning("Titulo da IA rejeitado (padrao suspeito): %r", ai_title)

            # Usa descrição da IA se disponível e nao suspeita
            ai_description = str(data.get("description", "")).strip()[:5000]
            if ai_description and is_safe_ai_text(ai_description):
                description = ai_description
            elif ai_description:
                log.warning("Descricao da IA rejeitada (padrao suspeito): %r", ai_description)

            # Merge de hashtags (filtra apenas strings, evita alucinacoes de dict/list)
            raw_hashtags = data.get("hashtags", [])
            if isinstance(raw_hashtags, str):
                raw_hashtags = raw_hashtags.split()
            ai_hashtags = [str(h).strip() for h in raw_hashtags
                           if isinstance(h, str) and h.strip()][:_MAX_HASHTAGS]
            if ai_hashtags:
                # AI hashtags primeiro: generate_hashtags() ja preenche o
                # orcamento de _MAX_HASHTAGS sozinho (brand+animal+musica+
                # categoria+formato), entao "hashtags + ai_hashtags" nunca
                # deixava as sugestoes da IA sobreviverem ao slice final.
                hashtags = list(dict.fromkeys(ai_hashtags + hashtags))[:_MAX_HASHTAGS]
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
        "title_pattern": title_pattern,
        "cta": cta_used,
    }


def clean_title(title: str) -> str:
    """Remove aspas duplas e excesso de espaços do título."""
    cleaned = title.replace('"', "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned
