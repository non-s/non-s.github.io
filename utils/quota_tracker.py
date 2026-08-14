"""utils/quota_tracker.py — rastreia unidades de quota da YouTube Data API v3.

A API usa um pool geral de 10.000 unidades e buckets granulares para alguns
metodos. videos.insert tem bucket proprio de 100 chamadas/dia e custa uma
unidade nesse bucket. Este modulo acompanha o pool e a contagem de uploads.

Custos por endpoint (documentacao oficial:
https://developers.google.com/youtube/v3/determine_quota_cost):
    videos.insert        = 1 (bucket proprio, 100 chamadas/dia)
    videos.list          = 1
    videos.update        = 50
    videos.delete        = 50
    playlists.insert     = 50
    playlists.list       = 1
    playlistItems.insert = 50
    playlistItems.list   = 1
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

from utils import notifier
from utils.paths import data_dir
from utils.state_lock import state_lock

log = logging.getLogger(__name__)


def _quota_file() -> Path:
    """Caminho de quota_usage.json no diretorio de dados do canal ativo."""
    return data_dir() / "quota_usage.json"


# Alias mantido por compatibilidade de testes/callers que referenciam
# QUOTA_FILE diretamente. Proxy leve: delega atributos/operacoes a
# _quota_file() (path do canal ativo) a cada acesso, exceto quando
# substituido por monkeypatch nos testes.
class _QuotaFileProxy:
    def __truediv__(self, other):
        return _quota_file() / other

    def __fspath__(self):
        return str(_quota_file())

    def __getattr__(self, name):
        return getattr(_quota_file(), name)

    def __repr__(self) -> str:
        return repr(_quota_file())

    def __str__(self) -> str:
        return str(_quota_file())

    def __eq__(self, other):
        return _quota_file() == other

    def __hash__(self):
        return hash(_quota_file())


QUOTA_FILE: Path = _QuotaFileProxy()  # type: ignore[assignment]

_LOCK = threading.Lock()

QUOTA_COSTS: dict[str, int] = {
    "videos.insert": 1,
    "videos.list": 1,
    "videos.update": 50,
    "videos.delete": 50,
    "playlists.insert": 50,
    "playlists.list": 1,
    "playlistItems.insert": 50,
    "playlistItems.list": 1,
    "search.list": 100,
    "captions.insert": 50,
    "captions.list": 50,
}

ALERT_THRESHOLD = 8000
DAILY_LIMIT = 10000
UPLOAD_ALERT_THRESHOLD = 90
UPLOAD_DAILY_LIMIT = 100


def _migrate_legacy_upload_costs(data: dict) -> dict:
    """Normalize persisted pre-2026 upload costs without losing call history."""
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        calls = entry.get("calls", [])
        if not isinstance(calls, list):
            continue
        changed = False
        for call in calls:
            if (
                isinstance(call, dict)
                and call.get("resource") == "videos"
                and call.get("method") == "insert"
                and int(call.get("units", 0)) > 1
            ):
                call["units"] = 1
                changed = True
        if changed:
            entry["total"] = sum(int(call.get("units", 0)) for call in calls if isinstance(call, dict))
    return data


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
            value = json.loads(path.read_text(encoding="utf-8"))
            return _migrate_legacy_upload_costs(value) if isinstance(value, dict) else {}
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
        day_entry.setdefault("calls", []).append(
            {
                "resource": resource,
                "method": method,
                "units": units,
                "at": datetime.now(UTC).isoformat(),
            }
        )
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
                total,
                DAILY_LIMIT,
                ALERT_THRESHOLD,
            )
            notifier.send_alert(
                f"YouTube API quota at {total} units (threshold {ALERT_THRESHOLD})",
                level="warning",
            )
        return total


def daily_total(*, file: Path | None = None) -> int:
    """Retorna o total de unidades consumidas hoje (0 se nada registrado)."""
    with _LOCK:
        data = _load(file)
        today = _today()
        entry = data.get(today)
        return int(entry["total"]) if entry else 0


def daily_call_count(resource: str, method: str, *, file: Path | None = None) -> int:
    """Count calls in the current UTC day, including migrated legacy entries."""
    with _LOCK:
        entry = _load(file).get(_today(), {})
        calls = entry.get("calls", []) if isinstance(entry, dict) else []
        return sum(
            1
            for call in calls
            if isinstance(call, dict) and call.get("resource") == resource and call.get("method") == method
        )


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
