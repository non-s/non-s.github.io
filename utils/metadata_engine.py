"""
utils/metadata_engine.py — gera títulos, descrições e hashtags otimizados para YouTube.
"""

from __future__ import annotations

import json
import logging
import random
import re
from typing import Any, Literal

from utils.ai_helper import ai_batch_metadata, ai_text, is_safe_ai_text
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


def _audience_for_scene(scene: str) -> str:
    """Retorna o publico coerente com a cena, sem cruzar gato e cachorro."""
    animal = detect_animal(scene)
    return "cats" if animal == "cat" else "dogs"


def _normalise_title_branding(title: str) -> str:
    """Mantem a marca uma unica vez e remove separadores deixados pela limpeza."""
    brand = active_channel.name
    # O gerador local adiciona a marca no final; uma resposta da IA tambem
    # pode inclui-la. Repetir a marca ocupa o pouco espaco util do titulo e
    # deixa o canal com aparencia automatizada.
    title = re.sub(rf"(?i)\s*\|?\s*{re.escape(brand)}\s*\|?", " | ", title)
    title = re.sub(r"(?:\s*\|\s*){2,}", " | ", title)
    title = re.sub(r"\s*\|\s*", " | ", title)
    return re.sub(r"^(?:\s*\|\s*)+|(?:\s*\|\s*)+$", "", title).strip()


def _build_metadata_prompt(hook: str, scene: str, duration: int, kind: str, emoji: str, lang: str = "en") -> str:
    target_len = 80 if kind == "short" else 100
    desc_lines = 3 if kind == "short" else 4
    channel_name = active_channel.name
    default_desc = active_channel.default_description
    audience = _audience_for_scene(scene)
    if lang == "pt":
        return (
            f"Crie metadados em PORTUGUES (PT-BR) para um {'Short' if kind == 'short' else 'video'} "
            f"do YouTube sobre {hook} {emoji}. O canal e {channel_name} ({default_desc}), "
            f"focando em buscas como 'musica para gatos', 'musica relaxante para cachorros' e "
            f"'musica para ansiedade de pets'. Duracao: ~{duration}s. "
            f"Regras:\n"
            f"- Titulo fofo e acolhedor, SEM clickbait, SEM palavras sensacionalistas, max {target_len} caracteres.\n"
            f"- Soe como uma pessoa real postando um video que gostou, nao como anuncio.\n"
            f"- Descricao de {desc_lines} linhas, tom leve e fofo, com emoji de gato/cachorro e musica.\n"
            f"- 5 a 8 hashtags relevantes separadas por espacos.\n"
            f"Retorne APENAS JSON com chaves: title, description, hashtags."
        )
    if lang == "es":
        return (
            f"Crea metadatos en ESPANOL para un {'Short' if kind == 'short' else 'video'} "
            f"de YouTube sobre {hook} {emoji}. El canal es {channel_name} ({default_desc}), "
            f"enfocado en buscas como 'musica para gatos', 'musica relajante para perros' y "
            f"'musica para ansiedad de mascotas'. Duracion: ~{duration}s. "
            f"Reglas:\n"
            f"- Titulo tierno y acogedor, SIN clickbait, SIN palabras sensacionalistas, max {target_len} caracteres.\n"
            f"- Suena como una persona real publicando un video que le gusto, no como anuncio.\n"
            f"- Descripcion de {desc_lines} lineas, tono ligero y tierno, con emoji de gato/perro y musica.\n"
            f"- 5 a 8 hashtags relevantes separados por espacios.\n"
            f"Retorna SOLO JSON con claves: title, description, hashtags."
        )
    return (
        f"Create English YouTube metadata for a {'Short' if kind == 'short' else 'video'} "
        f"about {hook} {emoji}. The channel is {channel_name} ({default_desc}), "
        f"made for {audience}. Never mention the other animal in the title. "
        f"Target searches should match {audience}, never generic cats/dogs. "
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


def _build_batch_metadata_prompt(
    hook: str, scene: str, duration: int, kind: str, emoji: str, lang: str = "en"
) -> str:
    """B1: prompt unico que pede todos os textos do vídeo de uma vez.

    Reduz 4-5 chamadas Gemini para 1. Retorna JSON com:
    - title: título principal (EN/PT/ES conforme lang)
    - title_alt: título alternativo para A/B testing
    - description: descrição longa otimizada
    - hashtags: lista de 5-8 hashtags
    - caption_en: legenda SRT em inglês (4-6 linhas)
    - caption_pt: legenda SRT em PT-BR (4-6 linhas)
    """
    channel_name = active_channel.name
    default_desc = active_channel.default_description
    audience = _audience_for_scene(scene)
    target_len = 80 if kind == "short" else 100
    lang_instruction = {
        "pt": "Write title, title_alt, description and caption_pt in PORTUGUESE (PT-BR); caption_en in English.",
        "es": (
            "Write title, title_alt, description in SPANISH; "
            "caption_pt in PORTUGUESE (PT-BR); caption_en in English."
        ),
        "en": "Write everything in English; caption_pt in PORTUGUESE (PT-BR).",
    }.get(lang, "Write everything in English; caption_pt in PORTUGUESE (PT-BR).")
    return (
        f"Create YouTube metadata for a {duration}-second {'Short' if kind == 'short' else 'video'} "
        f"about {hook} {emoji}. The channel is {channel_name} ({default_desc}), "
        f"made for {audience}. Never mention the other animal in the title. "
        f"Target searches should match {audience}, never generic cats/dogs. "
        f"{lang_instruction} "
        f"Rules:\n"
        f"- Warm, cute tone, NO clickbait, NO sensationalist words.\n"
        f"- title: max {target_len} characters.\n"
        f"- title_alt: a DIFFERENT title (different angle/keywords) for A/B testing, max {target_len} characters.\n"
        f"- description: 3-4 lines, light and cute, with cat/dog and music emoji.\n"
        f"- hashtags: 5-8 relevant hashtags (array of strings).\n"
        f"- caption_en: 4-6 short caption lines (max 40 chars each) in SRT format "
        f"(numbered, with timestamps HH:MM:SS,mmm --> HH:MM:SS,mmm).\n"
        f"- caption_pt: 4-6 short caption lines in PORTUGUESE (PT-BR) in SRT format.\n"
        f"Return ONLY JSON with keys: title, title_alt, description, hashtags, caption_en, caption_pt."
    )


def try_batch_metadata(
    hook: str, scene: str, duration: int, kind: str, emoji: str, lang: str = "en"
) -> dict | None:
    """B1: tenta gerar todos os textos do vídeo em uma unica chamada Gemini.

    Retorna dict com keys title, title_alt, description, hashtags,
    caption_en, caption_pt - ou None se a IA falhar (circuit breaker,
    key ausente, JSON invalido). O caller trata cada key ausente como
    fallback individual.
    """
    prompt = _build_batch_metadata_prompt(hook, scene, duration, kind, emoji, lang=lang)
    data = ai_batch_metadata(prompt, task=f"{kind}_batch_{lang}")
    if not data:
        return None
    # Valida que pelo menos title esta presente e e seguro
    title = str(data.get("title", "")).strip()
    if not title or not is_safe_ai_text(title):
        return None
    return data


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
    lang: str = "en",
) -> dict[str, Any]:
    """Gera metadados completos com SEO agressivo (Operação Zeus).

    Títulos espelham palavras-chave de alto volume real, descrições são longas
    e semanticamente otimizadas, hashtags atacam problema + animal + música.

    Suporte multilingue (A3): lang="en" (default), "pt" (PT-BR) ou "es"
    (espanhol). Em PT/ES, usa HIGH_VOLUME_KEYWORDS_PT/ES para títulos e
    descrições; o pipeline visual (video, legendas) continua o mesmo - so
    o texto do upload muda, capturando publico lusofono/hispanofono sem
    custo adicional.
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

    # B1: tenta gerar tudo (título, descrição, hashtags, title_alt,
    # legendas) em uma unica chamada Gemini. Se funcionar, usa os
    # resultados e pula as chamadas individuais. Se falhar, cai no fluxo
    # individual existente. Para PT/ES, o batch e preferencial (100%);
    # para EN, usa a mesma probabilidade do fluxo individual (20%).
    batch_probability = 1.0 if lang != "en" else 0.20
    batch_data: dict | None = None
    if random.random() < batch_probability:  # noqa: S311 - nao e seguranca
        batch_data = try_batch_metadata(hook, scene, duration, kind, emoji, lang=lang)

    title_pattern = "fallback_provided"
    if batch_data and batch_data.get("title"):
        # Batch funcionou - usa os resultados diretamente
        ai_title = str(batch_data.get("title", "")).strip()[:100]
        if ai_title and is_safe_ai_text(ai_title):
            if not ai_title.startswith(active_channel.brand_prefix.removesuffix(" |")):
                ai_title = f"{active_channel.brand_prefix} {ai_title}"
            title = ai_title
            title_pattern = "ai_generated"
            # title_alt do batch
            ai_title_alt = str(batch_data.get("title_alt", "")).strip()[:100]
            if ai_title_alt and is_safe_ai_text(ai_title_alt):
                if not ai_title_alt.startswith(active_channel.brand_prefix.removesuffix(" |")):
                    ai_title_alt = f"{active_channel.brand_prefix} {ai_title_alt}"
                batch_title_alt = ai_title_alt
            else:
                batch_title_alt = ""
        else:
            # title do batch rejeitado - cai no fluxo individual
            batch_data = None
    else:
        batch_title_alt = ""

    if not batch_data:
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
    # Para PT-BR/ES (A3), a IA e preferencial (100%) porque os bancos de
    # keywords PT/ES sao menores e a IA gera frases mais naturais que
    # preencher padrões EN com keywords traduzidas.
    # B1: se o batch já funcionou acima, pula a chamada individual de IA.
    if not batch_data:
        ai_probability = 1.0 if lang != "en" else 0.20
        if random.random() < ai_probability:  # noqa: S311 - nao e seguranca
            prompt = _build_metadata_prompt(hook, scene, duration, kind, emoji, lang=lang)
            out = ai_text(prompt, json_mode=True, task=f"{kind}_metadata_{lang}")
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
                    ai_hashtags = [
                        str(h).strip() for h in raw_hashtags if isinstance(h, str) and h.strip()
                    ][:_MAX_HASHTAGS]
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
    title, description = optimize_for_search(title, description, animal=animal)

    # B1: se o batch forneceu descrição/hashtags, usa-os (sobrescrevendo
    # o fallback local) - economiza as chamadas individuais de caption.
    if batch_data:
        ai_description = str(batch_data.get("description", "")).strip()[:5000]
        if ai_description and is_safe_ai_text(ai_description):
            description = ai_description
        raw_hashtags = batch_data.get("hashtags", [])
        if isinstance(raw_hashtags, str):
            raw_hashtags = raw_hashtags.split()
        ai_hashtags = [str(h).strip() for h in raw_hashtags if isinstance(h, str) and h.strip()][:_MAX_HASHTAGS]
        if ai_hashtags:
            hashtags = list(dict.fromkeys(ai_hashtags + hashtags))[:_MAX_HASHTAGS]

    # Garante prefixo de marca. A IA e os fallbacks podem incluir a marca;
    # normalizamos antes para que ela apareca apenas uma vez no titulo final.
    brand_prefix = active_channel.brand_prefix
    title = _normalise_title_branding(title)
    if not title.startswith(brand_prefix.removesuffix(" |")):
        title = f"{brand_prefix} {title}"
    if len(title) > 100:
        title = title[:97] + "..."

    # A/B testing de título: se o batch forneceu title_alt, usa-o;
    # caso contrario, gera um local via _generate_alt_title.
    if batch_data and batch_title_alt:
        title_alt = batch_title_alt
    else:
        title_alt = _generate_alt_title(
            animal=animal,
            acao=acao,
            estilo_musical=estilo_musical,
            kind=kind,
            emoji=emoji,
            duration=duration,
            primary_title=title,
            primary_pattern=title_pattern,
        )

    # Garante que as hashtags apareçam na descrição
    if hashtags and not any(re.search(rf"{re.escape(h)}\b", description) for h in hashtags):
        description = f"{description}\n\n{' '.join(hashtags)}"

    return {
        "title": title,
        "title_alt": title_alt,
        "description": description,
        "hashtags": hashtags,
        "title_pattern": title_pattern,
        "cta": cta_used,
    }


def _generate_alt_title(
    animal: str,
    acao: str,
    estilo_musical: str,
    kind: Literal["short"],
    emoji: str,
    duration: int,
    primary_title: str,
    primary_pattern: str,
) -> str:
    """Gera um título alternativo para A/B testing de título.

    Estratégia: re-sorteia um PADRÃO diferente do usado no título principal
    e formata com os mesmos inputs SEO. Se o novo título colidir com o
    título principal (mesmas palavras, Jaccard alto) ou com títulos
    recentes (anti-repeat), tenta ate 5 vezes. Se nao conseguir um título
    distinto, retorna string vazia (caller trata como sem alt).

    Mantem prefixo de marca e limite de 100 chars igual ao título principal.
    """
    brand_prefix = active_channel.brand_prefix
    for _attempt in range(5):
        alt_title, alt_pattern = generate_title_with_pattern(
            animal=animal,
            acao=acao,
            estilo_musical=estilo_musical,
            kind=kind,
            emoji=emoji,
            duracao=round(duration / 60) if kind != "short" else None,
        )
        # Tem que ser um PADRAO diferente do principal para que o alt
        # realmente teste uma hipotese de CTR diferente.
        if alt_pattern == primary_pattern:
            continue
        # Distinto do título principal (Jaccard < 0.5 para que o alt
        # teste uma hipotese de CTR realmente diferente - compartilhar
        # menos da metade das palavras significativas)
        from utils.seo_keywords import title_is_too_repetitive, title_similarity

        if title_similarity(alt_title, primary_title) >= 0.5:
            continue
        if title_is_too_repetitive(alt_title):
            continue
        # Garante prefixo de marca + limite
        if not alt_title.startswith(brand_prefix.removesuffix(" |")):
            alt_title = f"{brand_prefix} {alt_title}"
        if len(alt_title) > 100:
            alt_title = alt_title[:97] + "..."
        return alt_title
    return ""


def clean_title(title: str) -> str:
    """Remove aspas duplas e excesso de espaços do título."""
    cleaned = title.replace('"', "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned
