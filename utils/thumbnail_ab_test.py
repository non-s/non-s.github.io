"""
utils/thumbnail_ab_test.py — A/B testing de thumbnails com 3 variantes.

Fluxo:
1. generate_thumbnail_variants() gera as 3 variantes (A, B, C) usando o
   thumbnail_engine existente e registra o experimento em
   _data/thumbnail_experiments.json.
2. check_thumbnail_swap_needed() cruza dados de analytics
   (_data/analytics.json) com o experimento para decidir se a variante
   vencedora difere da atual apos 48h de postagem.
3. swap_thumbnail() troca a thumbnail ativa no YouTube via
   thumbnails.set (MediaFileUpload) e atualiza o experimento.
4. run_thumbnail_optimization() percorre todos os experimentos ativos,
   verificando e trocando conforme necessario.
5. record_thumbnail_ctr() registra o CTR observado por variante para
   alimentar a comparacao.

A YouTube Data API v3 suporta apenas 1 thumbnail por video (sem A/B
nativo); este modulo alterna a thumbnail ativa conforme performance
observada, mantendo o historico de variantes e CTR no arquivo de
experimento para auditoria.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from utils.paths import data_dir
from utils.state_lock import state_lock

log = logging.getLogger(__name__)

# Janela minima desde a postagem antes de considerar troca. 48h da o
# tempo suficiente para a thumbnail A acumular impressoes comparaveis.
_SWAP_WINDOW = timedelta(hours=48)

# Numero minimo de amostras de CTR por variante para confiar na
# comparacao. Abaixo disso, retorna None (sem dados suficientes).
_MIN_CTR_SAMPLES = 1

# Path do arquivo de experimentos de thumbnail.
_EXPERIMENTS_FILE: Path = data_dir() / "thumbnail_experiments.json"

# Path do analytics.json (escrito por scripts/collect_analytics.py).
_ANALYTICS_FILE: Path = data_dir() / "analytics.json"

# Limite da YouTube Data API v3 para upload de thumbnail (thumbnails.set).
# thumbnail_engine ja garante <2 MB, mas defendemos aqui para evitar um
# erro 400 da API se o arquivo foi alterado apos a geracao.
_YOUTUBE_THUMBNAIL_MAX_BYTES = 2 * 1024 * 1024  # 2 MB


def _experiments_file() -> Path:
    """Expoe o path do arquivo de experimentos para testes poderem
    monkeypatchar sem reimportar o modulo."""
    return _EXPERIMENTS_FILE


def _analytics_file() -> Path:
    """Expoe o path do analytics.json para testes poderem monkeypatchar."""
    return _ANALYTICS_FILE


def _load_experiments() -> dict:
    """Carrega thumbnail_experiments.json de forma segura (retorna {} se
    ausente ou corrompido)."""
    path = _experiments_file()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("_load_experiments: falha ao ler %s: %s", path, exc)
        return {}


def _save_experiments(experiments: dict) -> None:
    """Persiste thumbnail_experiments.json atomicamente (state_lock)."""
    path = _experiments_file()
    with state_lock(path):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(experiments, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            log.warning("_save_experiments: falha ao salvar %s: %s", path, exc)


def _normalize_variant(variant: str) -> str:
    """Normaliza a variante para lowercase ('a'/'b'/'c'). Default 'a'."""
    v = str(variant or "a").strip().lower()
    return v if v in ("a", "b", "c") else "a"


def _load_analytics() -> dict:
    """Carrega analytics.json de forma segura (retorna {} se ausente)."""
    path = _analytics_file()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("_load_analytics: falha ao ler %s: %s", path, exc)
        return {}


def _ctr_from_experiment(experiment: dict, variant: str) -> list[float]:
    """Extrai a lista de CTRs observados para uma variante no experimento.

    O experimento pode registrar CTRs em
    ``experiment['ctr'][variant]`` (lista de floats) ou em
    ``experiment['variants'][variant]['ctr_observations']``. Aceita ambos
    os formatos para compatibilidade com dados legados.
    """
    v = _normalize_variant(variant)
    ctr_block = experiment.get("ctr")
    if isinstance(ctr_block, dict):
        observations = ctr_block.get(v)
        if isinstance(observations, list):
            return [f for f in (_to_float(o) for o in observations) if f is not None]
    # Formato alternativo: variantes com sub-dict.
    variants_block = experiment.get("variants")
    if isinstance(variants_block, dict):
        variant_entry = variants_block.get(v)
        if isinstance(variant_entry, dict):
            observations = variant_entry.get("ctr_observations")
            if isinstance(observations, list):
                return [f for f in (_to_float(o) for o in observations) if f is not None]
    return []


def _to_float(value) -> float | None:
    """Converte value para float de forma segura (retorna None se invalido).

    Usado em filtro de listas de observacoes de CTR: ao inves de combinar
    ``_is_number`` + ``float`` (que o mypy nao estreita apos o guard), esta
    funcao devolve None para descartar valores invalidos via comprehensions.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_number(value) -> bool:
    """Retorna True se o valor pode ser convertido para float."""
    return _to_float(value) is not None


def _aggregate_ctr(experiment: dict, variant: str) -> float | None:
    """Retorna o CTR medio de uma variante, ou None se sem amostras."""
    observations = _ctr_from_experiment(experiment, variant)
    if len(observations) < _MIN_CTR_SAMPLES:
        return None
    return sum(observations) / len(observations)


def _enrich_ctr_from_analytics(experiment: dict, video_id: str) -> dict:
    """Cruza o experimento com analytics.json para derivar CTRs proxy
    quando o experimento nao tem CTR observado diretamente.

    analytics.json::all_videos[].thumbnail_variant indica qual variante
    estava ativa no momento da coleta, e o campo ``ctr`` (quando
    presente) traz o CTR real do video. Usamos o CTR do video como
    estimativa para a variante ativa, complementando as observacoes
    registradas via record_thumbnail_ctr.

    Retorna um novo dict de experimento com ``ctr`` preenchido para cada
    variante que tinha dados (nao muta o original).
    """
    analytics = _load_analytics()
    all_videos = analytics.get("all_videos") if isinstance(analytics, dict) else None
    if not isinstance(all_videos, list):
        return experiment

    ctr_block = experiment.get("ctr")
    if not isinstance(ctr_block, dict):
        ctr_block = {}
    # Copia para nao mutar o experimento recebido.
    ctr_block = {k: list(v) if isinstance(v, list) else [] for k, v in ctr_block.items()}

    # Procura o video_id em all_videos e, se houver CTR, adiciona a
    # variante ativa registrada no experimento (current_variant).
    for video in all_videos:
        if not isinstance(video, dict):
            continue
        if str(video.get("video_id")) != video_id:
            continue
        ctr_raw = video.get("ctr")
        ctr_val = _to_float(ctr_raw)
        if ctr_val is None:
            continue
        current = _normalize_variant(experiment.get("current_variant", "a"))
        observations = ctr_block.get(current, [])
        if not isinstance(observations, list):
            observations = []
        observations.append(ctr_val)
        ctr_block[current] = observations
        break

    enriched = dict(experiment)
    enriched["ctr"] = ctr_block
    return enriched


def generate_thumbnail_variants(
    video_path: Path,
    output_dir: Path,
    video_id: str,
    title: str,
    *,
    emoji: str = "✨",
    kind: str = "short",
    brand: str = "Liquid Wire",
) -> dict:
    """Gera 3 thumbnails (A, B, C) usando o thumbnail_engine existente.

    Salva em ``output_dir`` como ``{video_id}_variant_a.jpg``,
    ``{video_id}_variant_b.jpg`` e ``{video_id}_variant_c.jpg``. Registra
    o experimento em ``_data/thumbnail_experiments.json``:
    ``{video_id, variants: {a: path, b: path, c: path}, posted_at:
    timestamp, current_variant: "a", swap_count: 0}``.

    Retorna um dict com os paths das variantes:
    ``{"a": Path, "b": Path, "c": Path}``.
    """
    from utils.thumbnail_engine import create_all_variants

    output_dir.mkdir(parents=True, exist_ok=True)

    variants_paths: dict[str, str] = {}
    # create_all_variants gera thumb_A.jpg, thumb_B.jpg, thumb_C.jpg em
    # output_dir. Renomeamos para o padrao {video_id}_variant_{x}.jpg.
    raw_paths = create_all_variants(
        hook=title,
        emoji=emoji,
        output_dir=output_dir,
        brand=brand,
        video_path=video_path,
        kind=kind,
    )
    label_for_index = {0: "a", 1: "b", 2: "c"}
    for idx, raw_path in enumerate(raw_paths):
        label = label_for_index.get(idx, "a")
        final_path = output_dir / f"{video_id}_variant_{label}.jpg"
        if raw_path != final_path and raw_path.exists():
            raw_path.replace(final_path)
        variants_paths[label] = str(final_path)

    experiments = _load_experiments()
    experiments[video_id] = {
        "video_id": video_id,
        "title": title,
        "variants": variants_paths,
        "posted_at": datetime.now(UTC).isoformat(),
        "current_variant": "a",
        "swap_count": 0,
        "ctr": {},
    }
    _save_experiments(experiments)

    log.info(
        "Experimento de thumbnail criado para %s: variantes A=%s B=%s C=%s",
        video_id,
        variants_paths.get("a"),
        variants_paths.get("b"),
        variants_paths.get("c"),
    )
    return variants_paths


def check_thumbnail_swap_needed(video_id: str) -> str | None:
    """Verifica se o video precisa trocar de thumbnail.

    Le o experimento do ``video_id``. Se passaram mais de 48h desde a
    postagem (``posted_at``) e ha dados de analytics/CTR suficientes,
    compara o CTR das variantes. Retorna a variante vencedora (lowercase)
    se ela for diferente da atual, senao retorna None.

    Retorna None quando:
    - nao existe experimento para o video_id;
    - menos de 48h desde a postagem;
    - dados insuficientes para comparar (menos que _MIN_CTR_SAMPLES por
      variante, ou nenhuma variante com CTR agregado).
    """
    experiments = _load_experiments()
    experiment = experiments.get(video_id)
    if not isinstance(experiment, dict):
        log.debug("check_thumbnail_swap_needed: sem experimento para %s", video_id)
        return None

    posted_at_raw = experiment.get("posted_at")
    if not posted_at_raw:
        log.debug("check_thumbnail_swap_needed: sem posted_at para %s", video_id)
        return None
    try:
        posted_at = datetime.fromisoformat(str(posted_at_raw))
    except ValueError as exc:
        log.warning("check_thumbnail_swap_needed: posted_at invalido para %s: %s", video_id, exc)
        return None

    now = datetime.now(UTC)
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=UTC)
    if now - posted_at < _SWAP_WINDOW:
        log.debug(
            "check_thumbnail_swap_needed: %s postado ha menos de 48h (posted_at=%s)",
            video_id,
            posted_at_raw,
        )
        return None

    # Enriquece CTRs a partir do analytics.json (proxy via variante ativa)
    # antes de comparar.
    enriched = _enrich_ctr_from_analytics(experiment, video_id)
    current_variant = _normalize_variant(experiment.get("current_variant", "a"))

    ctrs: dict[str, float] = {}
    for variant in ("a", "b", "c"):
        agg = _aggregate_ctr(enriched, variant)
        if agg is not None:
            ctrs[variant] = agg

    # Precisamos de pelo menos uma variante diferente da atual com CTR
    # para ter algo a comparar.
    if not ctrs:
        log.debug(
            "check_thumbnail_swap_needed: sem CTR para %s (aguardando dados de analytics)",
            video_id,
        )
        return None

    # Se so a atual tem CTR, nao ha comparacao possivel.
    candidates = {v: c for v, c in ctrs.items() if v != current_variant}
    if not candidates:
        log.debug(
            "check_thumbnail_swap_needed: so a variante atual (%s) tem CTR para %s",
            current_variant,
            video_id,
        )
        return None

    winner = max(candidates, key=candidates.get)  # type: ignore[arg-type]
    current_ctr = ctrs.get(current_variant)
    if current_ctr is not None and candidates[winner] <= current_ctr:
        log.debug(
            "check_thumbnail_swap_needed: vencedora %s (%.4f) nao supera atual %s (%.4f) para %s",
            winner,
            candidates[winner],
            current_variant,
            current_ctr,
            video_id,
        )
        return None

    log.info(
        "check_thumbnail_swap_needed: troca sugerida para %s: %s -> %s (CTR %.4f vs %.4f)",
        video_id,
        current_variant,
        winner,
        current_ctr if current_ctr is not None else 0.0,
        candidates[winner],
    )
    return winner


def swap_thumbnail(video_id: str, new_variant: str) -> bool:
    """Troca a thumbnail do video no YouTube via thumbnails.set.

    Usa a YouTube Data API v3 com ``MediaFileUpload`` para enviar a
    imagem da variante ``new_variant`` registrada no experimento. Em
    sucesso, atualiza ``current_variant`` e incrementa ``swap_count`` em
    ``_data/thumbnail_experiments.json``.

    Retorna True em sucesso, False em falha (experimento ausente,
    variante invalida, arquivo de thumbnail ausente, ou erro da API).
    """
    new_variant = _normalize_variant(new_variant)

    experiments = _load_experiments()
    experiment = experiments.get(video_id)
    if not isinstance(experiment, dict):
        log.warning("swap_thumbnail: sem experimento para %s", video_id)
        return False

    variants = experiment.get("variants")
    if not isinstance(variants, dict):
        log.warning("swap_thumbnail: sem variantes registradas para %s", video_id)
        return False

    thumbnail_path_str = variants.get(new_variant)
    if not thumbnail_path_str:
        log.warning(
            "swap_thumbnail: variante %s nao encontrada no experimento de %s",
            new_variant,
            video_id,
        )
        return False

    thumbnail_path = Path(thumbnail_path_str)
    if not thumbnail_path.exists():
        log.warning(
            "swap_thumbnail: arquivo de thumbnail ausente para %s variante %s: %s",
            video_id,
            new_variant,
            thumbnail_path,
        )
        return False

    old_variant = _normalize_variant(experiment.get("current_variant", "a"))
    # Import dentro da funcao para evitar dependencia circular com
    # upload_youtube / youtube_oauth (que importam outros modulos de
    # utils que poderiam importar este).
    try:
        from googleapiclient.http import MediaFileUpload

        from utils.youtube_oauth import get_youtube_service
    except ImportError as exc:
        log.error("swap_thumbnail: dependencias do YouTube indisponiveis: %s", exc)
        return False

    # Verificacao defensiva de tamanho (limite da YouTube API: 2 MB).
    # thumbnail_engine ja garante <2 MB, mas se o arquivo foi alterado
    # manualmente ou trocado, falhamos cedo e evitamos um erro 400 da API.
    try:
        size_bytes = os.path.getsize(str(thumbnail_path))
    except OSError as exc:
        log.warning("swap_thumbnail: nao foi possivel stat %s: %s", thumbnail_path, exc)
        return False
    if size_bytes > _YOUTUBE_THUMBNAIL_MAX_BYTES:
        log.warning(
            "swap_thumbnail: %s excede 2 MB (%d bytes) para %s variante %s",
            thumbnail_path,
            size_bytes,
            video_id,
            new_variant,
        )
        return False

    try:
        service = get_youtube_service()
        start = time.monotonic()
        service.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg"),
        ).execute()
        elapsed = time.monotonic() - start
    except Exception as exc:
        log.warning(
            "swap_thumbnail: falha ao trocar thumbnail de %s (%s->%s): %s",
            video_id,
            old_variant,
            new_variant,
            exc,
        )
        return False

    log.info(
        "swap_thumbnail: %s trocou %s->%s em %.1fs (swap_count=%d)",
        video_id,
        old_variant,
        new_variant,
        elapsed,
        int(experiment.get("swap_count", 0)) + 1,
    )

    experiment["current_variant"] = new_variant
    experiment["swap_count"] = int(experiment.get("swap_count", 0)) + 1
    experiment["last_swap_at"] = datetime.now(UTC).isoformat()
    experiments[video_id] = experiment
    _save_experiments(experiments)

    return True


def run_thumbnail_optimization() -> list[dict]:
    """Funcao principal: verifica todos os experimentos ativos e troca
    a thumbnail para a variante vencedora quando necessario.

    Para cada video com experimento registrado em
    ``_data/thumbnail_experiments.json``:
      1. Verifica se precisa trocar (check_thumbnail_swap_needed).
      2. Se sim, troca (swap_thumbnail) e registra o CTR antes/depois.

    Retorna uma lista de swaps feitos, cada um como:
    ``{video_id, old_variant, new_variant, ctr_improvement}``.
    ``ctr_improvement`` e a diferenca entre o CTR da nova variante e o da
    antiga (0.0 se indisponivel).
    """
    experiments = _load_experiments()
    swaps: list[dict] = []
    if not experiments:
        log.info("run_thumbnail_optimization: nenhum experimento ativo.")
        return swaps

    for video_id, experiment in list(experiments.items()):
        if not isinstance(experiment, dict):
            continue
        try:
            winner = check_thumbnail_swap_needed(video_id)
        except Exception as exc:
            log.warning("run_thumbnail_optimization: erro ao verificar %s: %s", video_id, exc)
            continue
        if winner is None:
            continue

        old_variant = _normalize_variant(experiment.get("current_variant", "a"))
        # Captura CTRs antes da troca para calcular a melhoria.
        enriched = _enrich_ctr_from_analytics(experiment, video_id)
        old_ctr = _aggregate_ctr(enriched, old_variant)
        new_ctr = _aggregate_ctr(enriched, winner)
        ctr_improvement = 0.0
        if old_ctr is not None and new_ctr is not None:
            ctr_improvement = new_ctr - old_ctr
        elif new_ctr is not None:
            ctr_improvement = new_ctr

        success = swap_thumbnail(video_id, winner)
        if not success:
            log.warning(
                "run_thumbnail_optimization: troca falhou para %s (%s->%s)",
                video_id,
                old_variant,
                winner,
            )
            continue

        swaps.append(
            {
                "video_id": video_id,
                "old_variant": old_variant,
                "new_variant": winner,
                "ctr_improvement": ctr_improvement,
            }
        )

    if swaps:
        log.info("run_thumbnail_optimization: %d troca(s) realizada(s).", len(swaps))
    else:
        log.info("run_thumbnail_optimization: nenhuma troca necessaria.")
    return swaps


def record_thumbnail_ctr(video_id: str, variant: str, ctr: float) -> None:
    """Registra o CTR observado para uma variante no experimento.

    Salva em ``_data/thumbnail_experiments.json`` sob
    ``experiment['ctr'][variant]`` (lista de observacoes de CTR). Isso
    alimenta check_thumbnail_swap_needed e run_thumbnail_optimization na
    comparacao de variantes.

    Se nao existe experimento para o video_id, cria um esqueleto minimo
    apenas com o CTR registrado (sem variantes/posted_at) para que os
    dados nao sejam perdidos.
    """
    variant = _normalize_variant(variant)
    try:
        ctr_val = float(ctr)
    except (TypeError, ValueError) as exc:
        log.warning("record_thumbnail_ctr: CTR invalido para %s: %s", video_id, exc)
        return

    path = _experiments_file()
    with state_lock(path):
        try:
            if path.exists():
                experiments = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(experiments, dict):
                    experiments = {}
            else:
                experiments = {}
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("record_thumbnail_ctr: falha ao ler %s: %s", path, exc)
            experiments = {}

        experiment = experiments.get(video_id)
        if not isinstance(experiment, dict):
            experiment = {
                "video_id": video_id,
                "variants": {},
                "posted_at": None,
                "current_variant": variant,
                "swap_count": 0,
                "ctr": {},
            }

        ctr_block = experiment.get("ctr")
        if not isinstance(ctr_block, dict):
            ctr_block = {}
        observations = ctr_block.get(variant)
        if not isinstance(observations, list):
            observations = []
        observations.append(ctr_val)
        ctr_block[variant] = observations
        experiment["ctr"] = ctr_block
        experiments[video_id] = experiment

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(experiments, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            log.warning("record_thumbnail_ctr: falha ao salvar %s: %s", path, exc)
            return

    log.info(
        "record_thumbnail_ctr: %s variante=%s ctr=%.4f (total de amostras=%d)",
        video_id,
        variant,
        ctr_val,
        len(observations),
    )
