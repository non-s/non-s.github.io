"""
utils/content_strategy.py — estratégia de conteúdo Pata Jazz (mood/cena por horário).

Mapeia horário do dia -> mood para escolher cenas apropriadas:
  Manhã (06-12): diversao (energia, gatos brincando)
  Tarde  (12-18): fofura (fofo, gatinhos dormindo)
  Noite  (18-24): relax (relaxamento, cachorros dormindo)
  Madrugada (00-06): relax
"""

from __future__ import annotations

import json
import logging
import os
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from utils.paths import data_dir

log = logging.getLogger(__name__)


def _scene_performance_file() -> Path:
    """Caminho de scene_performance.json no diretorio de dados do canal ativo."""
    return data_dir() / "scene_performance.json"


def _viral_signals_file() -> Path:
    """Caminho de viral_signals.json no diretorio de dados do canal ativo."""
    return data_dir() / "viral_signals.json"


# Boost conservador aplicado a cenas que apareceram em virais recentes
# (ultimos _VIRAL_BOOST_WINDOW_DAYS dias). Multiplica o peso existente em vez
# de substituir: uma cena com peso 1.5 e boost 2.0 fica 3.0, mas uma cena sem
# peso (fora de scene_performance.json) nao recebe boost so por causa disso -
# precisa ja ter amostras suficientes no feedback loop normal.
_VIRAL_BOOST = 2.0
_VIRAL_BOOST_WINDOW_DAYS = 14

# Categorias de cenas
SCENE_CATEGORIES: dict[str, list[str]] = {
    "fofura": ["cat", "kitten", "puppy", "dog", "sleepy cat"],
    "diversao": ["playful dog", "cat playing", "puppy playing", "dog relaxing"],
    "relax": ["sleepy cat", "sleepy dog", "cat relaxing", "dog relaxing"],
}


# #6: cenas de alta qualidade para os primeiros uploads do canal novo.
# Antes de o feedback loop ter dados, priorizar cenas universalmente fofas
# (kitten sleeping, puppy playing) em vez de sortear uniformemente.
# Contador em _data/upload_language_counter.json (ja existe para multilingue).
_FIRST_UPLOADS_PRIORITY_SCENES = ["kitten", "puppy", "sleepy cat", "puppy playing", "cat playing"]
_FIRST_UPLOADS_THRESHOLD = 10  # primeiros N uploads usam priorizacao

# Mapeamento de faixa horaria (BRT) -> mood
# Manha = energia/diversao, Tarde = fofura, Noite/Madrugada = relax
_HOURLY_MOOD: dict[int, str] = {
    h: ("diversao" if 6 <= h < 12 else "fofura" if 12 <= h < 18 else "relax") for h in range(24)
}


def current_brt_hour() -> int:
    """Retorna a hora atual em BRT (UTC-3 por default, configuravel via
    BRT_OFFSET_HOURS)."""
    offset = float(os.environ.get("BRT_OFFSET_HOURS", "-3"))
    return (datetime.now(UTC) + timedelta(hours=offset)).hour


def mood_for_now() -> str:
    """Retorna o mood apropriado para a hora atual (BRT).

    Mood sazonal tem prioridade: se a data atual cai num periodo sazonal
    definido (ex: Natal, Ano Novo, Black Friday), o mood correspondente e
    retornado em vez do horario fixo - datas geram picos de busca por
    "relaxing pet music" e o conteudo deve refletir a sazonalidade.
    """
    seasonal = _seasonal_mood()
    if seasonal:
        return seasonal
    return _HOURLY_MOOD.get(current_brt_hour(), "fofura")


# Datas sazonais (mes, dia) -> mood. Janela de alguns dias antes para capturar
# a busca antecipada. None = sem sazonalidade ativa hoje.
_SEASONAL_MOODS: list[tuple[int, int, int, int, str]] = [
    # (mes_inicio, dia_inicio, mes_fim, dia_fim, mood)
    (12, 20, 12, 31, "relax"),  # Natal / festas de fim de ano
    (1, 1, 1, 6, "relax"),  # Ano novo
    (11, 20, 11, 30, "fofura"),  # Black Friday / Thanksgiving (fofura/volta as aulas EUA)
    (2, 10, 2, 16, "diversao"),  # Valentines Day (energia/diversao)
    (10, 28, 11, 3, "fofura"),  # Halloween
]


def _seasonal_mood() -> str | None:
    """Retorna o mood sazonal para a data atual (BRT), se houver."""
    offset = float(os.environ.get("BRT_OFFSET_HOURS", "-3"))
    now = datetime.now(UTC) + timedelta(hours=offset)
    for m1, d1, m2, d2, mood in _SEASONAL_MOODS:
        start = now.replace(month=m1, day=d1, hour=0, minute=0, second=0, microsecond=0)
        try:
            end = now.replace(month=m2, day=d2, hour=23, minute=59, second=59, microsecond=0)
        except ValueError:
            continue
        if start <= now <= end:
            log.info("Mood sazonal ativo: %s (%02d/%02d-%02d/%02d)", mood, m1, d1, m2, d2)
            return mood
    return None


def _scene_weights() -> dict[str, float]:
    """Le _data/scene_performance.json (gerado por collect_analytics.py a
    partir de views reais por cena). Ausente/corrompido = sem preferencia."""
    try:
        data = json.loads(_scene_performance_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        log.debug("scene_performance.json ausente/corrompido: %s", exc)
        return {}


def viral_boosted_scenes() -> dict[str, float]:
    """Le viral_signals.json e retorna um dict scene -> boost weight para
    cenas que apareceram em virais recentes (ultimos
    _VIRAL_BOOST_WINDOW_DAYS dias).

    O boost base continua sendo _VIRAL_BOOST (2.0), mas agora e modulado
    por engajamento: um viral com CTR alto e/ou AVP alto recebe um peso
    extra (ate +0.5 cada), refletindo que nao e so volume bruto de views
    que importa, mas tambem retencao/conversao.

    Conservador: so cenas com nome nao-vazio entram. Se o arquivo estiver
    ausente/corrompido, retorna {} (nenhum boost). A janela e medida a
    partir do campo `detected_at` de cada sinal; sinais sem detected_at ou
    com data invalida sao ignorados.
    """
    try:
        data = json.loads(_viral_signals_file().read_text(encoding="utf-8"))
    except Exception as exc:
        log.debug("viral_signals.json ausente/corrompido: %s", exc)
        return {}
    if not isinstance(data, list):
        return {}

    now = datetime.now(UTC)
    cutoff = now - timedelta(days=_VIRAL_BOOST_WINDOW_DAYS)
    boosted: dict[str, float] = {}
    for signal in data:
        if not isinstance(signal, dict):
            continue
        scene = (signal.get("scene") or "").strip()
        if not scene:
            continue
        detected_at = signal.get("detected_at")
        if not detected_at:
            continue
        try:
            s = str(detected_at).strip()
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
        except Exception:
            continue
        if dt.astimezone(UTC) < cutoff:
            continue

        # Boost modulado por engajamento: CTR/AVP altos aumentam o peso.
        boost = _VIRAL_BOOST
        try:
            ctr = float(signal.get("ctr", 0) or 0)
            avp = float(signal.get("avp", 0) or 0)
        except Exception:
            ctr, avp = 0.0, 0.0
        if ctr > 0.05:
            boost += 0.3
        if avp > 0.5:
            boost += 0.2
        boosted[scene] = boost
    return boosted


def scene_for_mood(mood: str) -> str:
    """Retorna uma cena especifica (ex: 'sleepy cat') para o mood dado.

    Quando ha dados reais de performance (scene_performance.json), a
    escolha e ponderada por eles em vez de puramente uniforme - cenas que
    historicamente tiveram mais views por video ficam mais provaveis, sem
    nunca zerar a chance das outras (ver _MIN_WEIGHT em collect_analytics.py).

    Cenas que geraram virais recentes (viral_signals.json, ultimos 14 dias)
    recebem um boost conservador multiplicado sobre o peso existente: a
    cena precisa ja estar na lista do mood (nao inventa cena nova) e o boost
    so multiplica - nunca substitui nem cria peso do nada. Assim um viral
    isolado eleva a chance da cena sem distorcer o equilibrio geral.

    #6: nos primeiros _FIRST_UPLOADS_THRESHOLD uploads do canal, prioriza
    cenas universalmente fofas (kitten, puppy, sleepy cat) em vez de sortear
    uniformemente - primeira impressao do algoritmo do YouTube e crucial.
    """
    scenes = SCENE_CATEGORIES.get(mood, SCENE_CATEGORIES["fofura"])
    weights_by_scene = _scene_weights()
    viral_boosts = viral_boosted_scenes()

    # #6: priorizar cenas fofas nos primeiros uploads
    use_priority = False
    priority_boost: dict[str, float] = {}
    try:
        from utils.paths import data_dir as _data_dir

        counter_file = _data_dir() / "upload_language_counter.json"
        if counter_file.exists():
            import json

            data = json.loads(counter_file.read_text(encoding="utf-8"))
            count = int(data.get("count", 0)) if isinstance(data, dict) else 0
            if count < _FIRST_UPLOADS_THRESHOLD:
                use_priority = True
                for s in _FIRST_UPLOADS_PRIORITY_SCENES:
                    if s in scenes:
                        priority_boost[s] = 2.5
    except Exception:
        pass

    if not weights_by_scene and not viral_boosts and not use_priority:
        return random.choice(scenes)
    weights = []
    for scene in scenes:
        w = weights_by_scene.get(scene, 1.0)
        if scene in viral_boosts:
            w *= viral_boosts[scene]
        if use_priority and scene in priority_boost:
            w *= priority_boost[scene]
        weights.append(w)
    return random.choices(scenes, weights=weights, k=1)[0]
