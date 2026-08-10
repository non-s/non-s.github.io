"""scripts/sync_trending.py — descobre termos de busca em alta no nicho pet/jazz.

Usa a YouTube Data API v3 search.list para encontrar vídeos recentes
populares no nicho "pet + relaxation + jazz" e extrair os termos de busca
mais frequentes dos títulos. Esses termos sao injetados em
_data/trending_keywords.json e lidos por utils.seo_keywords para compor
HIGH_VOLUME_KEYWORDS["trending"] dinamicamente - os títulos do canal
passam a refletir o que esta bombando em busca real do YouTube, nao so
um banco estatico.

Custo de quota: search.list custa 100 unidades por chamada. Roda 2x por
semana com ~5 queries (pet, cat, dog, jazz, relaxing) = ~500 unidades/run,
bem dentro do limite de 10000/dia (e do alerta em 8000).

Sem YOUTUBE_TOKEN configurado, loga warning e sai sem erro (nao derruba
o workflow de sync).
"""

from __future__ import annotations

import json
import logging
import re
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.log_config import configure_logging
from utils.paths import data_dir, ensure_data_dir
from utils.state_lock import state_lock

log = logging.getLogger(__name__)

DATA_DIR = data_dir()
ensure_data_dir()
TRENDING_FILE = DATA_DIR / "trending_keywords.json"

# Queries base para descobrir vídeos populares do nicho. Cada query custa
# 100 unidades de quota no search.list; mantemos poucas para nao estourar
# o budget diario.
_DISCOVERY_QUERIES = [
    "pet relaxation music",
    "cat sleeping music",
    "dog anxiety music",
    "calming jazz for pets",
    "cute cat shorts",
]

# Palavras que nao sao uteis como keywords (stop words do nicho + marca).
_STOP_WORDS = frozenset({
    "the", "a", "an", "to", "for", "of", "in", "on", "and", "or", "with",
    "your", "my", "this", "that", "is", "are", "was", "will", "can",
    "you", "we", "they", "it", "be", "more", "best", "top",
    "pata", "jazz", "music", "video", "short", "shorts", "youtube",
    "watch", "full", "hd", "4k", "ep", "feat", "ft",
})

# Janela de busca: vídeos publicados nos ultimos 30 dias.
_SEARCH_WINDOW_DAYS = 30
# Max resultados por query.
_MAX_RESULTS_PER_QUERY = 25
# Max keywords a salvar no final (top N mais frequentes).
_MAX_TRENDING_KEYWORDS = 20
# Min frequencia para uma keyword ser considerada trending.
_MIN_FREQUENCY = 2


def _extract_keywords_from_title(title: str) -> list[str]:
    """Extrai palavras-chave candidatas de um título de vídeo.

    Normaliza para lowercase, remove pontuacao, filtra stop words e palavras
    muito curtas (<3 chars). Retorna lista de palavras individuais mais
    bigrams comuns (pares de palavras adjacentes).
    """
    if not title:
        return []
    # Normaliza: lowercase, remove pontuacao excao espacos
    cleaned = re.sub(r"[^a-z0-9\s]", " ", title.lower())
    words = [w for w in cleaned.split() if len(w) >= 3 and w not in _STOP_WORDS]
    keywords: list[str] = []
    # Palavras individuais
    keywords.extend(words)
    # Bigrams (pares de palavras adjacentes) - captura "pet anxiety",
    # "sleep music", "home alone", etc.
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i + 1]}"
        keywords.append(bigram)
    return keywords


def _search_youtube(service, query: str, published_after: str, max_results: int) -> list[dict]:
    """Executa search.list na YouTube Data API e retorna items com título.

    Retorna lista de dicts com pelo menos {"title": ...}. Em erro, loga e
    retorna [] - uma query que falha nao derruba o sync inteiro.
    """
    from utils.youtube_retry import retry_youtube_call

    try:
        resp = retry_youtube_call(
            service.search()
            .list(
                part="snippet",
                q=query,
                type="video",
                order="viewCount",
                publishedAfter=published_after,
                maxResults=max_results,
                videoCategoryId="15",  # Pets & Animals
            )
            .execute
        )
        items = resp.get("items", []) if isinstance(resp, dict) else []
        return [
            {"title": item.get("snippet", {}).get("title", "")}
            for item in items
            if isinstance(item, dict)
        ]
    except Exception as exc:
        log.warning("search.list falhou para query=%r: %s", query, exc)
        return []


def _compute_trending_keywords(videos: list[dict]) -> list[str]:
    """Conta frequencia de keywords extraidas dos títulos e retorna top N."""
    counter: Counter[str] = Counter()
    for video in videos:
        title = video.get("title", "")
        for kw in _extract_keywords_from_title(title):
            counter[kw] += 1
    # Filtra por min frequency e pega top N
    trending = [kw for kw, count in counter.most_common() if count >= _MIN_FREQUENCY]
    return trending[:_MAX_TRENDING_KEYWORDS]


def collect_trending_keywords(service) -> list[str]:
    """Busca vídeos populares do nicho e extrai keywords trending.

    Retorna lista de keywords (strings) ordenadas por frequencia decrescente.
    """
    published_after = (datetime.now(UTC) - timedelta(days=_SEARCH_WINDOW_DAYS)).isoformat()
    all_videos: list[dict] = []
    for query in _DISCOVERY_QUERIES:
        videos = _search_youtube(service, query, published_after, _MAX_RESULTS_PER_QUERY)
        all_videos.extend(videos)
        log.info("Query %r: %d vídeos encontrados.", query, len(videos))
    if not all_videos:
        log.warning("Nenhum vídeo encontrado nas queries de trending.")
        return []
    trending = _compute_trending_keywords(all_videos)
    log.info("Trending keywords extraidas: %d (de %d vídeos).", len(trending), len(all_videos))
    return trending


def save_trending_keywords(keywords: list[str]) -> None:
    """Salva keywords trending em _data/trending_keywords.json com timestamp."""
    payload = {
        "keywords": keywords,
        "collected_at": datetime.now(UTC).isoformat(),
        "queries": _DISCOVERY_QUERIES,
    }
    with state_lock(TRENDING_FILE):
        try:
            TRENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
            TRENDING_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            log.info("Trending keywords salvas: %s (%d keywords)", TRENDING_FILE, len(keywords))
        except Exception as exc:
            log.warning("Falha ao salvar trending keywords: %s", exc)


def load_trending_keywords() -> list[str]:
    """Le trending_keywords.json e retorna a lista de keywords (ou [] se
    ausente/corrompido). Usado por utils.seo_keywords para injetar trending
    em HIGH_VOLUME_KEYWORDS dinamicamente."""
    try:
        data = json.loads(TRENDING_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            kws = data.get("keywords", [])
            return [str(k) for k in kws if isinstance(k, str)] if isinstance(kws, list) else []
        return []
    except Exception:
        return []


def main() -> int:
    configure_logging()
    try:
        from utils.youtube_oauth import get_youtube_service

        service = get_youtube_service()
    except Exception as exc:
        log.warning("YouTube OAuth indisponivel, pulando sync de trending: %s", exc)
        return 0
    keywords = collect_trending_keywords(service)
    if keywords:
        save_trending_keywords(keywords)
    return 0


if __name__ == "__main__":
    sys.exit(main())
