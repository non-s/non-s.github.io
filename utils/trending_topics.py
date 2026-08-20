"""
utils/trending_topics.py — assuntos em alta como inspiracao para titulos/descricoes.

Busca trending topics relacionados a arte generativa, ambient music e
procedural art via Gemini (com Google Search grounding) e os usa como
inspiracao para titulos e descricoes evocativos. Nenhum trending topic
vira clickbait: o prompt explicita o tom poetico/evocativo do Liquid Wire
e proibe claims medicos ou sensacionalistas. Todo o modulo e defensivo
— se o Gemini falhar, o caller recebe metadados inalterados e o canal
continua operando com titulos/descricoes normais.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from utils.ai_helper import ai_grounded_research, ai_text, is_safe_ai_text
from utils.paths import data_dir
from utils.state_lock import state_lock

log = logging.getLogger(__name__)

_CACHE_FILE = "trending_cache.json"
_CACHE_TTL_SECONDS = 6 * 3600  # 6 horas
_TITLE_MAX = 70


def _cache_path() -> Path:
    return data_dir() / _CACHE_FILE


def load_trending_cache() -> dict | None:
    """Le _data/trending_cache.json se existir e for <6h. None se expirou/ausente."""
    path = _cache_path()
    try:
        if not path.exists():
            return None
        with state_lock(path):
            data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        ts = data.get("saved_at")
        if not isinstance(ts, (int, float)):
            return None
        if time.time() - float(ts) > _CACHE_TTL_SECONDS:
            return None
        topics = data.get("topics")
        if not isinstance(topics, list):
            return None
        return data
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        log.debug("trending_cache.json ausente/corrompido: %s", exc)
        return None


def save_trending_cache(data: dict) -> None:
    """Salva o cache de trending topics com timestamp em _data/trending_cache.json."""
    path = _cache_path()
    payload = {
        "saved_at": time.time(),
        "saved_at_iso": datetime.now(UTC).isoformat(),
        "topics": data.get("topics", []) if isinstance(data, dict) else [],
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with state_lock(path):
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except OSError as exc:
        log.warning("Falha ao salvar trending_cache.json: %s", exc)


def fetch_trending_topics(category: str = "art") -> list[dict]:
    """Busca trending topics via Gemini com Google Search grounding.

    Retorna lista de dicts: {"topic": str, "relevance": float (0-1),
    "source": str}. Usa cache de 6h para evitar chamadas repetidas. Em
    falha (key ausente, circuit breaker, JSON invalido), retorna [].
    """
    cached = load_trending_cache()
    if cached is not None:
        topics = cached.get("topics")
        if isinstance(topics, list):
            log.info("trending_topics: cache valido (%d topics)", len(topics))
            return topics

    prompt = (
        "Search the web for currently trending topics in generative art, "
        "procedural visuals, ambient music, algorithmic art, creative coding, "
        "and related visual-arts sources (YouTube and established art publications). "
        "Return a JSON object with key \"topics\": a list of 5 to 10 objects, each "
        "with keys \"topic\" (short phrase, max 4 words), \"relevance\" (float 0-1, "
        "how relevant it is to inspiring evocative generative-art video titles), "
        "and \"source\" (a short label like 'YouTube trends' or 'Reddit r/generative'). "
        "Only include topics actually trending now, not evergreen generalities. "
        "Do not include medical, therapeutic, or outcome-related topics. "
        "Do not include clickbait-style phrases. Output JSON only."
    )
    research = ai_grounded_research(prompt, task="trending_topics", timeout=60)
    text = (research.get("text") or "").strip()
    sources = research.get("sources") or []

    if not text:
        log.info("trending_topics: Gemini grounded research vazio; fallback [].")
        return []

    topics = _parse_topics(text, sources)
    if not topics:
        log.info("trending_topics: nenhum topic parseado; fallback [].")
        return []

    save_trending_cache({"topics": topics})
    log.info("trending_topics: %d topics salvos no cache.", len(topics))
    return topics


def _parse_topics(text: str, sources: list[dict]) -> list[dict]:
    """Extrai a lista de topics de uma resposta JSON do Gemini.

    Aceita JSON puro ou JSON embutido em cercado de markdown/texto. Cada
    topic e normalizado para {"topic": str, "relevance": float, "source": str}.
    """
    candidates = _extract_json_objects(text)
    for raw in candidates:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        items = data.get("topics") if isinstance(data, dict) else None
        if not isinstance(items, list):
            continue
        topics: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            topic = str(item.get("topic", "")).strip()
            if not topic:
                continue
            try:
                relevance = float(item.get("relevance", 0.5))
            except (TypeError, ValueError):
                relevance = 0.5
            relevance = max(0.0, min(1.0, relevance))
            source = str(item.get("source", "")).strip()
            topics.append({"topic": topic, "relevance": relevance, "source": source})
        if topics:
            return topics

    if not topics and sources:
        fallback_source = str(sources[0].get("title") or "web")[:60] if sources else ""
        return [
            {"topic": str(s.get("title", ""))[:80], "relevance": 0.3, "source": fallback_source}
            for s in sources[:5]
            if s.get("title")
        ]
    return []


def _extract_json_objects(text: str) -> list[str]:
    """Retorna substrings JSON candidatas encontradas no texto.

    Procura por blocos ```json ... ``` e por chaves balanceadas. Best-effort:
    se nada for encontrado, retorna o texto inteiro como unica candidata.
    """
    import re

    out: list[str] = []
    for match in re.finditer(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE):
        out.append(match.group(1))
    if not out:
        start = text.find("{")
        if start != -1:
            depth = 0
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        out.append(text[start : i + 1])
                        break
    if not out:
        out.append(text)
    return out


def _topics_brief(topics: list[dict]) -> str:
    """Compacta os topics em uma string legivel para o prompt de titulo/descricao."""
    if not topics:
        return ""
    lines = []
    for item in topics[:8]:
        topic = str(item.get("topic", "")).strip()
        if not topic:
            continue
        lines.append(f"- {topic}")
    return "\n".join(lines)


def trending_inspired_title(
    video_description: str,
    family: str,
    genre: str,
    *,
    is_short: bool = False,
) -> str:
    """Gera um titulo evocativo inspirado nos trending topics.

    Combina os trending topics com o contexto do video (familia visual e
    genero musical). Nunca clickbait, nunca claims medicos. Max 70 chars
    (+ " #Shorts" se short). Em falha retorna "" — o caller usa o titulo
    normal.
    """
    topics = fetch_trending_topics()
    brief = _topics_brief(topics)
    if not brief:
        return ""

    max_len = _TITLE_MAX - (len(" #Shorts") if is_short else 0)
    prompt = (
        "You write evocative, poetic titles for a YouTube channel of original "
        "procedural generative art with procedural ambient music. The titles are "
        "calm, evocative, never clickbait, never sensationalist.\n\n"
        f"Visual family: {family}\n"
        f"Music genre: {genre}\n"
        f"Video context: {video_description[:300]}\n\n"
        "Current trending topics in the generative-art / ambient-music niche "
        "(for inspiration only — do NOT copy them verbatim and do NOT chase trends):\n"
        f"{brief}\n\n"
        "Write ONE single title inspired by the mood of these topics but in the "
        f"channel's own poetic voice. Maximum {max_len} characters. Plain text, "
        "no quotes, no hashtags, no em-dashes as dramatic pauses, no emoji. "
        "Do not make medical, therapeutic, or outcome claims. "
        "Do not use words like 'shocking', 'must-see', 'amazing'. "
        "Return only the title text."
    )
    raw = ai_text(prompt, json_mode=False, task="trending_title")
    title = _clean_title(raw, max_len, is_short)
    if not title or not is_safe_ai_text(title):
        log.info("trending_title: rejeitado (vazio ou inseguro).")
        return ""
    return title


def _clean_title(raw: str, max_len: int, is_short: bool) -> str:
    if not raw:
        return ""
    title = raw.strip().strip('"').strip("'").strip()
    title = title.splitlines()[0].strip() if title else ""
    title = " ".join(title.split())
    if not title:
        return ""
    if len(title) > max_len:
        cut = title[:max_len].rsplit(" ", 1)[0].strip()
        title = cut or title[:max_len].strip()
    if is_short:
        if not title.endswith("#Shorts"):
            title = f"{title} #Shorts"
    return title


def trending_inspired_description(title: str, family: str, genre: str) -> str:
    """Gera uma descricao de 2 paragrafos inspirada nos trending topics.

    Menciona que e arte generativa procedural original. Em falha retorna "".
    """
    topics = fetch_trending_topics()
    brief = _topics_brief(topics)
    if not brief:
        return ""

    prompt = (
        "You write natural, warm YouTube descriptions for a channel of original "
        "procedural generative art with procedural ambient music. The tone is "
        "genuine, like texting a friend about a video you just posted — not a "
        "marketing department.\n\n"
        f"Title: {title}\n"
        f"Visual family: {family}\n"
        f"Music genre: {genre}\n\n"
        "Current trending topics in the generative-art / ambient-music niche "
        "(for inspiration only — do NOT chase trends verbatim):\n"
        f"{brief}\n\n"
        "Write exactly two short paragraphs in natural English. The first "
        "paragraph should evoke what the viewer sees and hears, nodding to the "
        "mood of the trending topics without naming them. The second paragraph "
        "should mention that this is original procedural generative art — the "
        "visuals and the music are both made with code, no stock footage, no "
        "samples. Do not make medical, therapeutic, or outcome claims. Do not "
        "use words like 'shocking', 'must-see', 'amazing'. No hashtags, no links, "
        "no emoji. Return only the description text."
    )
    raw = ai_text(prompt, json_mode=False, task="trending_description")
    desc = _clean_description(raw)
    if not desc or not is_safe_ai_text(desc):
        log.info("trending_description: rejeitada (vazia ou insegura).")
        return ""
    if "generative" not in desc.lower() and "procedural" not in desc.lower():
        log.info("trending_description: rejeitada (sem mencao a generative/procedural).")
        return ""
    return desc


def _clean_description(raw: str) -> str:
    if not raw:
        return ""
    desc = raw.strip().strip('"').strip("'").strip()
    desc = "\n\n".join(
        " ".join(line.split()) for line in desc.split("\n\n") if line.strip()
    ).strip()
    return desc


def enrich_metadata(metadata: dict, family: str, genre: str, preset: str) -> dict:
    """Funcao principal: busca trending topics e gera titulo + descricao.

    Se sucesso, substitui ``title`` e ``description`` no metadata. Se falha,
    retorna o metadata inalterado (graceful). Loga se usou trending ou nao.
    """
    if os.environ.get("LIQUID_WIRE_TREND_METADATA", "0") != "1":
        metadata["trending_inspired"] = False
        metadata["trending_policy"] = "disabled_by_default_for_authenticity"
        return metadata
    try:
        topics = fetch_trending_topics()
        if not topics:
            log.info("enrich_metadata: sem trending topics; mantendo metadata.")
            return metadata

        current_title = str(metadata.get("title", ""))
        current_desc = str(metadata.get("description", ""))
        is_short = preset == "short"

        new_title = trending_inspired_title(
            current_desc or current_title,
            family,
            genre,
            is_short=is_short,
        )
        new_desc = trending_inspired_description(new_title or current_title, family, genre)

        used_trending = False
        if new_title:
            metadata["title"] = new_title
            used_trending = True
        if new_desc:
            metadata["description"] = new_desc
            used_trending = True

        if used_trending:
            metadata["trending_inspired"] = True
            log.info(
                "enrich_metadata: titulo/descricao enriquecidos com %d trending topics.",
                len(topics),
            )
        else:
            log.info("enrich_metadata: trending topics disponiveis mas geracao falhou; mantendo metadata.")
        return metadata
    except Exception as exc:
        log.warning("enrich_metadata: erro inesperado, mantendo metadata: %s", exc)
        return metadata
