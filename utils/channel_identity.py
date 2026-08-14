"""utils/channel_identity.py — atualizador de identidade (about/keywords) do canal.

Um canal confiavel precisa manter a pagina Sobre consistente. Esta unidade
aplica a descricao e keywords canônicas versionadas para o canal, com uma
trava de estado que evita atualizacoes redundantes e gasto de quota.

A atualizacao usa ``brandingSettings.channel`` via ``channels.update`` (custo
50 de quota, como videos.insert). Como o update substitui o objeto inteiro,
reenviamos os campos que nao mexemos (country, etc.) preservados do fetch.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from utils.channel_config import active_channel
from utils.paths import data_dir
from utils.state_lock import state_lock

log = logging.getLogger(__name__)

# Limites da API do YouTube para brandingSettings.channel.
_DESCRIPTION_LIMIT = 1000
_KEYWORDS_LIMIT = 500

# ---------------------------------------------------------------------------
# Estado persistente (1x por semana)
# ---------------------------------------------------------------------------


def _state_file() -> Path:
    return data_dir() / "identity.json"


def _load_state() -> dict:
    try:
        data = json.loads(_state_file().read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception as exc:
        log.debug("identity.json ausente/corrompido: %s", exc)
    return {}


def _save_state(state: dict) -> None:
    try:
        _state_file().parent.mkdir(parents=True, exist_ok=True)
        _state_file().write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning("Falha ao salvar identity.json: %s", exc)


# ---------------------------------------------------------------------------
# Geração da identidade-alvo (IA com fallback local)
# ---------------------------------------------------------------------------


def identity_targets(iso_week: int) -> dict:
    """Descricao e keywords canônicas do canal.

    A identidade publica nao deve mudar com o calendario nem com uma resposta
    estocastica da IA. A fonte e sempre a configuracao versionada.
    """
    del iso_week  # A assinatura preserva a compatibilidade com o state semanal.
    description = active_channel.default_description
    extras = ["generative art", "procedural music", "ambient visuals", "wireframe art"]
    keywords = list(dict.fromkeys([*active_channel.base_tags, *extras]))
    return {
        "description": str(description)[:_DESCRIPTION_LIMIT],
        "keywords": ", ".join(keywords)[:_KEYWORDS_LIMIT],
    }


# ---------------------------------------------------------------------------
# Aplicação na YouTube Data API
# ---------------------------------------------------------------------------


def _current_branding(channel: dict) -> dict:
    """Extrai (description, keywords) atuais do brandingSettings do canal."""
    bs = (channel.get("brandingSettings") or {}).get("channel") or {}
    return {
        "description": str(bs.get("description") or ""),
        "keywords": str(bs.get("keywords") or ""),
    }


def needs_update(current: dict, target: dict) -> bool:
    """True se a identidade atual do canal difere da alvo da semana."""
    return (
        current.get("description", "").strip() != target.get("description", "").strip()
        or current.get("keywords", "").strip() != target.get("keywords", "").strip()
    )


def apply_update(service, channel_id: str, channel: dict, target: dict, *, retry_call) -> None:
    """Aplica description/keywords via channels.update (part=brandingSettings).

    O update substitui brandingSettings.channel inteiro; preservamos os campos
    que nao mexemos (country, etc.) copiando o objeto atual.
    """
    bs = channel.get("brandingSettings") or {}
    bs_channel = dict(bs.get("channel") or {})
    bs_channel["description"] = target["description"]
    bs_channel["keywords"] = target["keywords"]
    body = {"id": channel_id, "brandingSettings": {**bs, "channel": bs_channel}}
    retry_call(service.channels().update(part="brandingSettings", body=body).execute)


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------


def run_identity_update(
    service,
    channel_id: str,
    *,
    dry_run: bool = False,
    force: bool = False,
    retry_call=None,
    now: datetime | None = None,
) -> dict:
    """Executa o ciclo completo e retorna um relatorio.

    Etapas: buscar branding do canal -> gerar alvo da semana -> comparar ->
    atualizar (se mudou e nao atualizou nesta semana) -> persistir estado.

    Retorna {"dry_run", "changed", "updated", "iso_week", "description",
    "keywords", "current_description", "current_keywords"}.
    """
    if retry_call is None:
        from utils.youtube_retry import retry_youtube_call as _retry

        retry_call = _retry

    now = now or datetime.now(UTC)
    iso_week = now.isocalendar().week

    response = retry_call(service.channels().list(part="brandingSettings", mine=True).execute)
    items = response.get("items") or []
    if not items:
        raise RuntimeError("Nenhum canal encontrado para as credenciais atuais.")
    channel = items[0]

    current = _current_branding(channel)
    target = identity_targets(iso_week)
    changed = needs_update(current, target)

    report = {
        "dry_run": bool(dry_run),
        "changed": changed,
        "updated": False,
        "iso_week": iso_week,
        "description": target["description"],
        "keywords": target["keywords"],
        "current_description": current["description"],
        "current_keywords": current["keywords"],
    }

    state_file = _state_file()
    with state_lock(state_file):
        state = _load_state()
        same_target = state.get("description") == target["description"] and state.get("keywords") == target["keywords"]

        if dry_run:
            log.info(
                "[DRY-RUN] %s (semana ISO %d)",
                "atualizaria a identidade" if changed else "identidade ja em dia",
                iso_week,
            )
            return report

        if not (changed and (force or not same_target)):
            log.info(
                "Identidade ja em dia (semana ISO %d, changed=%s, mesmo_alvo=%s).",
                iso_week,
                changed,
                same_target,
            )
            return report

        apply_update(service, channel_id, channel, target, retry_call=retry_call)
        report["updated"] = True
        _save_state(
            {
                "variant_week": iso_week,
                "updated_at": now.isoformat(),
                "description": target["description"],
                "keywords": target["keywords"],
            }
        )
        log.info("Identidade do canal atualizada (semana ISO %d).", iso_week)
        return report
