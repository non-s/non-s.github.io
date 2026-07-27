"""
scripts/predict_views.py — analytics preditivo: prevê views nos primeiros
7 dias após o upload de um short, por cena / padrão de título / horário.

Treina um modelo de regressão linear simples (mínimos quadrados em Python
puro — sem numpy/scikit-learn, que não estão nas dependências do projeto)
sobre os dados já coletados por collect_analytics.py (analytics.json +
analytics_history.json + video_tags.json).

Features (todas escaláveis para one-hot ou escalares):
    - bias (1.0)
    - scene one-hot (uma coluna por cena vista nos dados)
    - title_pattern one-hot (uma coluna por padrão visto nos dados)
    - hour_of_day (0..23) — hora UTC do upload
    - day_of_week (0..6, segunda=0)

Alvo (y): "views projetadas no dia 7 após o upload". Como não temos
snapshots diários por vídeo, usamos o proxy
    views_at_now / dias_desde_upload * 7
cruzando analytics.json::all_videos[].published_at + views com
video_tags.json::[video_id].scene/title_pattern/uploaded_at.

O modelo treinado é salvo em _data/view_predictor.json (pesos por feature),
lido de volta por predict_views() para previsões em produção (dashboard).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.log_config import configure_logging
from utils.state_lock import state_lock

log = logging.getLogger(__name__)

DATA_DIR = ROOT / "_data"
ANALYTICS_FILE = DATA_DIR / "analytics.json"
VIDEO_TAGS_FILE = DATA_DIR / "video_tags.json"
MODEL_FILE = DATA_DIR / "view_predictor.json"

# Slots de cron dos shorts (UTC) — usado pelo dashboard para enumerar os
# próximos agendamentos. Definido aqui (e não no workflow) para que o
# dashboard não dependa de parsing de YAML do workflow.
SHORTS_CRON_HOURS_UTC: tuple[int, ...] = (1, 10, 16, 21)


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def _parse_iso(dt_str: str) -> datetime | None:
    """Converte timestamp ISO (com 'Z' ou offset) para datetime UTC."""
    if not dt_str:
        return None
    try:
        s = dt_str.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception:
        return None


def _collect_training_samples() -> list[dict]:
    """Cruza analytics.json (views/published_at atuais) com video_tags.json
    (scene/title_pattern por video_id) e calcula o alvo (views projetadas
    no dia 7) para cada vídeo tagueado.

    Sem snapshots diários por vídeo, o proxy
        views_at_now / dias_desde_upload * 7
    aproxima a taxa de views diária extrapolada para a primeira semana.
    Vídeos com menos de 1 dia desde o upload são descartados (taxa instável).
    """
    analytics = _load_json(ANALYTICS_FILE, {})
    all_videos = analytics.get("all_videos") if analytics else None
    if not all_videos:
        return []

    video_tags = _load_json(VIDEO_TAGS_FILE, {})
    if not video_tags:
        return []

    now = datetime.now(UTC)
    samples: list[dict] = []
    for video in all_videos:
        vid = video.get("video_id")
        tag = video_tags.get(vid) if vid else None
        if not tag:
            continue
        scene = (tag.get("scene") or "").strip().lower()
        title_pattern = (tag.get("title_pattern") or "").strip()
        if not scene or not title_pattern:
            continue

        published = _parse_iso(str(video.get("published_at", ""))) or _parse_iso(str(tag.get("uploaded_at", "")))
        if published is None:
            continue
        days_since = (now - published).total_seconds() / 86400.0
        if days_since < 1.0:
            continue

        views_now = int(video.get("views", 0) or 0)
        views_at_day7 = views_now / days_since * 7.0
        if views_at_day7 <= 0:
            continue

        samples.append({
            "scene": scene,
            "title_pattern": title_pattern,
            "hour_of_day": published.hour,
            "day_of_week": published.weekday(),
            "y": views_at_day7,
        })
    return samples


def _build_vocab(samples: list[dict]) -> tuple[list[str], list[str]]:
    """Extrai vocabulário ordenado de cenas e padrões de título das amostras."""
    scenes = sorted({s["scene"] for s in samples})
    title_patterns = sorted({s["title_pattern"] for s in samples})
    return scenes, title_patterns


def _feature_names(scenes: list[str], title_patterns: list[str]) -> list[str]:
    """Nomes das features. A PRIMEIRA cena e o PRIMEIRO padrão são omitidos
    (categoria de referência) para evitar a 'dummy variable trap': com o
    bias, as colunas one-hot completas são linearmente dependentes
    (scene:cat + scene:dog = 1.0 sempre) e tornam o sistema singular.

    A cena/padrão omitidos têm peso implícito no bias; os pesos das demais
    representam o desvio relativo à referência."""
    names = ["bias"]
    names += [f"scene:{c}" for c in scenes[1:]]
    names += [f"title_pattern:{p}" for p in title_patterns[1:]]
    names += ["hour_of_day", "day_of_week"]
    return names


def _featurize(
    scene: str, title_pattern: str, hour: int, day_of_week: int,
    scenes: list[str], title_patterns: list[str],
) -> list[float]:
    """Constrói o vetor de features para uma amostra/previsão. A primeira
    cena/padrão são a referência (não ganham coluna) — ver _feature_names."""
    vec = [1.0]  # bias
    scene_l = scene.strip().lower()
    for c in scenes[1:]:  # primeira = referência, omitida
        vec.append(1.0 if c == scene_l else 0.0)
    for p in title_patterns[1:]:  # primeiro = referência, omitido
        vec.append(1.0 if p == title_pattern else 0.0)
    vec.append(float(hour))
    vec.append(float(day_of_week))
    return vec


def _solve_normal_equation(X: list[list[float]], y: list[float], ridge: float = 1e-6) -> list[float] | None:
    """Resolve mínimos quadrados via equação normal (X^T X + ridge·I) w = X^T y
    usando eliminação de Gauss-Jordan com pivoteamento parcial.

    Uma pequena regularização ridge (ridge · I) evita a singularidade das
    'dummy variable trap': com cenas e padrões de título correlacionados
    (ex.: um padrão que só aparece com uma cena), as colunas one-hot ficam
    colineares e o sistema puro é insolúvel. O ridgeλ=1e-6 é minúsculo e
    não distorce os pesos, mas torna o sistema sempre invertível —
    evitando o fallback de média geral em dados reais onde a colinearidade
    é inevitável (cenas/padrões que só aparecem juntos).

    Retorna None apenas se não houver amostras/features.
    """
    n = len(X[0]) if X else 0
    if n == 0 or len(X) != len(y):
        return None

    # A = X^T X + ridge·I (n x n), b = X^T y (n)
    A = [[0.0] * n for _ in range(n)]
    b = [0.0] * n
    for row, yi in zip(X, y, strict=True):
        for i in range(n):
            ri = row[i]
            if ri == 0.0:
                continue
            b[i] += ri * yi
            for j in range(n):
                A[i][j] += ri * row[j]
    for i in range(n):
        A[i][i] += ridge

    # Gauss-Jordan com pivoteamento parcial. Com o ridge, o sistema é
    # sempre não-singular (autovalores >= ridge), então a detecção de
    # pivot~0 aqui é só um guard defensivo contra instabilidade numérica
    # extrema (ex.: overflow com features não escaladas).
    for col in range(n):
        pivot = col
        for r in range(col + 1, n):
            if abs(A[r][col]) > abs(A[pivot][col]):
                pivot = r
        if abs(A[pivot][col]) < 1e-15:
            return None
        A[col], A[pivot] = A[pivot], A[col]
        b[col], b[pivot] = b[pivot], b[col]
        pivot_val = A[col][col]
        for j in range(n):
            A[col][j] /= pivot_val
        b[col] /= pivot_val
        for r in range(n):
            if r == col:
                continue
            factor = A[r][col]
            if factor == 0.0:
                continue
            for j in range(n):
                A[r][j] -= factor * A[col][j]
            b[r] -= factor * b[col]
    return b


def train_model() -> dict:
    """Treina o modelo de regressão linear a partir dos dados coletados e
    retorna o payload serializável a ser salvo em MODEL_FILE.

    Sem amostras suficientes (ou sistema singular), ainda grava um modelo
    "vazio" com overall_avg — predict_views cai no fallback da média geral.
    """
    samples = _collect_training_samples()
    if not samples:
        log.info("Sem amostras tagueadas para treinar; modelo vazio (fallback = média geral 0).")
        return {
            "features": _feature_names([], []),
            "weights": [],
            "scenes": [],
            "title_patterns": [],
            "overall_avg": 0.0,
            "trained_at": datetime.now(UTC).isoformat(),
            "n_samples": 0,
        }

    scenes, title_patterns = _build_vocab(samples)
    X = [
        _featurize(s["scene"], s["title_pattern"], s["hour_of_day"], s["day_of_week"], scenes, title_patterns)
        for s in samples
    ]
    y = [float(s["y"]) for s in samples]
    overall_avg = sum(y) / len(y) if y else 0.0

    weights = _solve_normal_equation(X, y)
    if weights is None:
        log.warning("Sistema singular (features colineares); modelo cai no fallback da média geral.")
        return {
            "features": _feature_names(scenes, title_patterns),
            "weights": [],
            "scenes": scenes,
            "title_patterns": title_patterns,
            "overall_avg": overall_avg,
            "trained_at": datetime.now(UTC).isoformat(),
            "n_samples": len(samples),
        }

    return {
        "features": _feature_names(scenes, title_patterns),
        "weights": weights,
        "scenes": scenes,
        "title_patterns": title_patterns,
        "overall_avg": overall_avg,
        "trained_at": datetime.now(UTC).isoformat(),
        "n_samples": len(samples),
    }


def save_model(model: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with state_lock(MODEL_FILE):
        try:
            MODEL_FILE.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
            log.info("Modelo de previsão salvo: %s (%d amostras)", MODEL_FILE, model.get("n_samples", 0))
        except Exception as exc:
            log.warning("Falha ao salvar modelo de previsão: %s", exc)


def load_model() -> dict:
    return _load_json(MODEL_FILE, {})


def predict_views(scene: str, title_pattern: str, hour: int, day_of_week: int) -> float:
    """Prevê views nos primeiros 7 dias após o upload de um short com a
    cena/padrão/horário dados, lendo o modelo salvo em MODEL_FILE.

    Sem modelo treinado (ou modelo vazio/n_samples==0) retorna a média
    geral (overall_avg), que é 0.0 quando nunca houve dados.
    """
    model = load_model()
    if not model:
        return 0.0
    weights = model.get("weights") or []
    if not weights:
        return float(model.get("overall_avg", 0.0))
    scenes = model.get("scenes", [])
    title_patterns = model.get("title_patterns", [])
    vec = _featurize(scene, title_pattern, hour, day_of_week, scenes, title_patterns)
    if len(vec) != len(weights):
        # Vocabulário mudou desde o treino — fallback seguro.
        return float(model.get("overall_avg", 0.0))
    result = sum(w * v for w, v in zip(weights, vec, strict=True))
    return max(0.0, result)


def expected_views_for_slot(hour: int, day_of_week: int) -> float:
    """Esperança de views de um short sorteado (cena/padrão uniformes) num
    dado horário. Usado pelo dashboard para prever os próximos slots de cron
    sem depender de qual cena/padrão exato será gerado.

    Sem modelo treinado, cai no fallback de overall_avg via predict_views.
    """
    model = load_model()
    if not model:
        return 0.0
    weights = model.get("weights") or []
    if not weights:
        return float(model.get("overall_avg", 0.0))
    scenes = model.get("scenes", [])
    title_patterns = model.get("title_patterns", [])
    if not scenes or not title_patterns:
        return float(model.get("overall_avg", 0.0))
    total = 0.0
    count = 0
    for scene in scenes:
        for pattern in title_patterns:
            total += predict_views(scene, pattern, hour, day_of_week)
            count += 1
    return total / count if count else 0.0


def next_cron_slots(now: datetime | None = None, n: int = 4) -> list[tuple[int, int]]:
    """Enumera os próximos n slots de cron de shorts (UTC) a partir de now,
    retornando (hour, day_of_week) para cada um.

    day_of_week segue datetime.weekday(): 0=segunda .. 6=domingo.
    """
    if now is None:
        now = datetime.now(UTC)
    result: list[tuple[int, int]] = []
    day_offset = 0
    while len(result) < n and day_offset < 14:
        base = (now.replace(hour=0, minute=0, second=0, microsecond=0))
        from datetime import timedelta
        base = base + timedelta(days=day_offset)
        for h in SHORTS_CRON_HOURS_UTC:
            slot_dt = base.replace(hour=h)
            if slot_dt > now:
                result.append((h, slot_dt.weekday()))
                if len(result) >= n:
                    break
        day_offset += 1
    return result


def main() -> int:
    configure_logging()
    model = train_model()
    save_model(model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
