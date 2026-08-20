"""utils/pipeline_metrics.py — metricas de execucao do pipeline de conteudo.

Registra cada execucao de um estagio (geracao de Short, upload) em
_data/pipeline_metrics.json com status (sucesso/falha), duracao, tipo
(kind) e timestamp. Mantem no maximo as ultimas 500 entradas para nao crescer
indefinidamente. pipeline_summary() agrega por estagio: taxa de sucesso,
numero de runs, duracao media, etc.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from utils.paths import data_dir
from utils.state_lock import state_lock

log = logging.getLogger(__name__)

_MAX_ENTRIES = 500


def _metrics_file() -> Path:
    return data_dir() / "pipeline_metrics.json"


def record_pipeline_run(
    stage: str,
    success: bool,
    duration_seconds: float = 0,
    kind: str = "",
    details: dict | None = None,
) -> None:
    """Acrescenta uma entrada de metrica ao arquivo de metricas de pipeline.

    Args:
        stage: nome do estagio (ex: "generate_short", "upload").
        success: True se a execucao foi bem-sucedida.
        duration_seconds: tempo gasto em segundos (default 0).
        kind: tipo/subcategoria livre (ex: "short").
    """
    entry = {
        "stage": stage,
        "success": bool(success),
        "duration_seconds": float(duration_seconds),
        "kind": kind,
        "at": datetime.now(UTC).isoformat(),
        "details": details or {},
    }
    path = _metrics_file()
    with state_lock(path):
        try:
            existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        except Exception:
            existing = []
        if not isinstance(existing, list):
            existing = []
        existing.append(entry)
        existing = existing[-_MAX_ENTRIES:]
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning("Falha ao salvar metricas de pipeline: %s", exc)


def pipeline_summary() -> dict:
    """Le o arquivo de metricas e retorna um resumo agregado por estagio.

    Retorna um dict com:
        - "total_runs": int (total de entradas)
        - "stages": {stage: {"runs": int, "successes": int, "failures": int,
                              "success_rate": float, "avg_duration_seconds": float}}
    """
    path = _metrics_file()
    if not path.exists():
        return {"total_runs": 0, "stages": {}}
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"total_runs": 0, "stages": {}}
    if not isinstance(entries, list):
        return {"total_runs": 0, "stages": {}}

    stages: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        stage = entry.get("stage", "")
        if not stage:
            continue
        agg = stages.setdefault(
            stage,
            {
                "runs": 0,
                "successes": 0,
                "failures": 0,
                "total_duration": 0.0,
            },
        )
        agg["runs"] += 1
        if entry.get("success"):
            agg["successes"] += 1
        else:
            agg["failures"] += 1
        agg["total_duration"] += float(entry.get("duration_seconds", 0) or 0)

    for agg in stages.values():
        runs = agg["runs"]
        agg["success_rate"] = agg["successes"] / runs if runs else 0.0
        agg["avg_duration_seconds"] = agg["total_duration"] / runs if runs else 0.0
        del agg["total_duration"]

    return {"total_runs": len(entries), "stages": stages}
