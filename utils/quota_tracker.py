"""utils/quota_tracker.py — rastreia unidades de quota da YouTube Data API v3.

A YouTube API tem um limite diario de 10.000 unidades por projeto (default).
Cada endpoint custa um numero fixo de unidades (videos.insert=1600,
videos.list=1, etc). Sem rastreio, um workflow que sobe 7 videos/dia
(7 x 1600 = 11.200) passa do limite e falha com quotaExceeded sem aviso
previo - este modulo loga o consumo acumulado em _data/quota_usage.json
e emite alerta quando passa de 8000/dia (margem antes do teto).

Custos por endpoint (documentacao oficial:
https://developers.google.com/youtube/v3/determine_quota_cost):
    videos.insert        = 1600
    videos.list          = 1
    videos.update        = 50
    videos.delete        = 50
    playlists.insert     = 50
    playlists.list       = 1
    playlistItems.insert = 50
    playlistItems.list   = 1
    liveBroadcasts.insert= 1600
    liveBroadcasts.list  = 1
    liveBroadcasts.bind  = 50
    liveStreams.list     = 1
    liveChatMessages.list= 1
    search.list          = 100
    captions.insert      = 50
    captions.list        = 50
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import UTC, datetime
from pathlib import Path

from utils.state_lock import state_lock

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "_data"
QUOTA_FILE = DATA_DIR / "quota_usage.json"

_LOCK = threading.Lock()

QUOTA_COSTS: dict[str, int] = {
    "videos.insert": 1600,
    "videos.list": 1,
    "videos.update": 50,
    "videos.delete": 50,
    "playlists.insert": 50,
    "playlists.list": 1,
    "playlistItems.insert": 50,
    "playlistItems.list": 1,
    "liveBroadcasts.insert": 1600,
    "liveBroadcasts.list": 1,
    "liveBroadcasts.bind": 50,
    "liveStreams.list": 1,
    "liveChatMessages.list": 1,
    "search.list": 100,
    "captions.insert": 50,
    "captions.list": 50,
}

ALERT_THRESHOLD = 8000
DAILY_LIMIT = 10000


def infer_cost(method_name: str | None, resource: str | None) -> int:
    """Infer e o custo em unidades de uma chamada a partir do nome do metodo
    (videos.insert, playlists.list, etc). Retorna 0 se desconhecido - nenhum
    custo atribuido em vez de falhar."""
    if resource and method_name:
        key = f"{resource}.{method_name}"
        if key in QUOTA_COSTS:
            return QUOTA_COSTS[key]
    if method_name and method_name in QUOTA_COSTS:
        return QUOTA_COSTS[method_name]
    return 0


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _load(file: Path | None = None) -> dict:
    path = file if file is not None else QUOTA_FILE
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        log.warning("Falha ao ler %s; recomecando contagem do zero.", path)
    return {}


def _save(data: dict, file: Path | None = None) -> None:
    path = file if file is not None else QUOTA_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with state_lock(path):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def record_usage(resource: str, method: str, units: int | None = None, *, file: Path | None = None) -> int:
    """Registra uma chamada de API. Se units nao for passado, infere do
    custo por endpoint (QUOTA_COSTS). Retorna o total do dia apos registrar.

    Thread-safe via lock interno (concorrencia dentro do mesmo processo) e
    state_lock (concorrencia entre processos/jobs)."""
    if units is None:
        units = infer_cost(method, resource)
    if units <= 0:
        return daily_total(file=file)

    with _LOCK:
        data = _load(file)
        today = _today()
        day_entry = data.setdefault(today, {"total": 0, "calls": []})
        day_entry["total"] = day_entry.get("total", 0) + units
        day_entry.setdefault("calls", []).append({
            "resource": resource,
            "method": method,
            "units": units,
            "at": datetime.now(UTC).isoformat(),
        })
        # Mantem so os ultimos 14 dias (evita crescimento ilimitado do arquivo).
        keys = sorted(data.keys())
        for old in keys[:-14]:
            if old != today:
                del data[old]
        try:
            _save(data, file)
        except OSError as exc:
            log.warning("Falha ao salvar quota_usage.json: %s", exc)

        total = day_entry["total"]
        if total >= ALERT_THRESHOLD and total - units < ALERT_THRESHOLD:
            log.warning(
                "ALERTA de quota: %d unidades usadas hoje (limite diario=%d, alerta em %d).",
                total, DAILY_LIMIT, ALERT_THRESHOLD,
            )
        return total


def daily_total(*, file: Path | None = None) -> int:
    """Retorna o total de unidades consumidas hoje (0 se nada registrado)."""
    with _LOCK:
        data = _load(file)
        today = _today()
        entry = data.get(today)
        return int(entry["total"]) if entry else 0


def reset_today(*, file: Path | None = None) -> None:
    """Zera a contagem do dia (util em testes)."""
    with _LOCK:
        data = _load(file)
        today = _today()
        data[today] = {"total": 0, "calls": []}
        try:
            _save(data, file)
        except OSError as exc:
            log.warning("Falha ao salvar quota_usage.json: %s", exc)


def should_alert(*, file: Path | None = None) -> bool:
    """Retorna True se o consumo do dia ja passou do limiar de alerta."""
    return daily_total(file=file) >= ALERT_THRESHOLD


def log_final_total(*, file: Path | None = None) -> int:
    """Loga o total final do dia e retorna-o. Chamar no fim de cada workflow."""
    total = daily_total(file=file)
    env = os.environ.get("GITHUB_OUTPUT")
    log.info("Quota YouTube acumulada hoje: %d/%d unidades (alerta em %d).", total, DAILY_LIMIT, ALERT_THRESHOLD)
    if env:
        try:
            with open(env, "a", encoding="utf-8") as f:
                f.write(f"quota_used_today={total}\n")
        except OSError:
            pass
    return total
