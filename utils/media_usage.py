"""Ledger permanente e transacional de midia usada pelo Pata Jazz.

O contrato deste modulo e deliberadamente estrito: depois que uma faixa ou
clipe participa de uma producao validada, o asset nunca volta ao pool elegivel.
Identidades canonicas da origem (Jamendo/Pixabay) impedem que o mesmo item seja
rebaixado com outro nome; SHA-256 cobre duplicatas de conteudo e assets legados.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from utils.paths import data_dir
from utils.state_lock import state_lock

MediaKind = Literal["audio", "video"]
_SCHEMA_VERSION = 1


class MediaAlreadyUsedError(RuntimeError):
    """Um asset ou assinatura foi reservado/usado por outra producao."""


def _usage_file() -> Path:
    return data_dir() / "media_usage.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_metadata(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def source_identity(kind: MediaKind, metadata: dict[str, Any]) -> str:
    """Retorna uma identidade canonica da origem quando disponivel."""
    raw_id = metadata.get("id")
    if raw_id not in (None, ""):
        provider = "jamendo" if kind == "audio" else "pixabay"
        return f"{provider}:{raw_id}"
    source_url = metadata.get("source_url") or metadata.get("pageURL") or metadata.get("shorturl")
    if source_url:
        normalized = " ".join(str(source_url).split())
        return f"source:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"
    return ""


def asset_descriptor(path: Path, kind: MediaKind, *, ensure_hash: bool = False) -> dict[str, str]:
    """Descreve um asset com identidade de origem e hash de conteudo."""
    metadata = _load_metadata(path)
    identity = source_identity(kind, metadata)
    content_hash = str(metadata.get("content_sha256") or "").lower()
    is_real_file = isinstance(path, Path) and path.is_file()
    if ensure_hash and not content_hash and is_real_file:
        content_hash = sha256_file(path)
    if not identity:
        if not content_hash and is_real_file:
            content_hash = sha256_file(path)
        # Caminhos inexistentes so aparecem em testes/mocks ou numa corrida em
        # que o arquivo sumiu. A identidade nominal mantem a operacao fail-safe;
        # o render real falhara e a reserva sera liberada.
        identity = f"sha256:{content_hash}" if content_hash else f"legacy-name:{path.name}"
    return {
        "identity": identity,
        "sha256": content_hash,
        "name": path.name,
        "path": str(path),
    }


def _empty_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "version": _SCHEMA_VERSION,
        "used": {"audio": {}, "video": {}},
        "hashes": {"audio": {}, "video": {}},
        "pending": {},
        "productions": {},
        "legacy_names": {"audio": [], "video": []},
    }
    # Migra conservadoramente a janela antiga: tudo que era recente passa a
    # ser considerado usado. Nao recupera o historico completo anterior a
    # este ledger, mas evita repeticao imediata durante a transicao.
    recent = data_dir() / "recent_media.json"
    try:
        old = json.loads(recent.read_text(encoding="utf-8"))
        ledger["legacy_names"]["audio"] = list(dict.fromkeys(old.get("audio", [])))
        ledger["legacy_names"]["video"] = list(dict.fromkeys(old.get("videos", [])))
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return ledger


def _load_ledger() -> dict[str, Any]:
    path = _usage_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("ledger nao e objeto")
    except (OSError, ValueError, TypeError):
        return _empty_ledger()
    base = _empty_ledger()
    for key in ("used", "hashes", "pending", "productions", "legacy_names"):
        if isinstance(data.get(key), dict):
            base[key] = data[key]
    # Normaliza ledgers parciais ou editados manualmente. Estruturas ausentes
    # ficam vazias, mantendo o restante do historico utilizavel sem KeyError.
    for key in ("used", "hashes"):
        if not isinstance(base[key], dict):
            base[key] = {}
        for kind in ("audio", "video"):
            if not isinstance(base[key].get(kind), dict):
                base[key][kind] = {}
    if not isinstance(base["legacy_names"], dict):
        base["legacy_names"] = {}
    for kind in ("audio", "video"):
        if not isinstance(base["legacy_names"].get(kind), list):
            base["legacy_names"][kind] = []
    for key in ("pending", "productions"):
        if not isinstance(base[key], dict):
            base[key] = {}
    base["version"] = _SCHEMA_VERSION
    return base


def _save_ledger(ledger: dict[str, Any]) -> None:
    path = _usage_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".json.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _pending_assets(ledger: dict[str, Any], kind: MediaKind) -> tuple[set[str], set[str]]:
    identities: set[str] = set()
    hashes: set[str] = set()
    for reservation in ledger["pending"].values():
        for asset in reservation.get(kind, []):
            identities.add(str(asset.get("identity", "")))
            if asset.get("sha256"):
                hashes.add(str(asset["sha256"]))
    return identities, hashes


def descriptor_is_unavailable(descriptor: dict[str, str], kind: MediaKind, ledger: dict[str, Any]) -> bool:
    identity = descriptor["identity"]
    content_hash = descriptor.get("sha256", "")
    if descriptor.get("name") in set(ledger["legacy_names"].get(kind, [])):
        return True
    if identity in ledger["used"][kind]:
        return True
    if content_hash and content_hash in ledger["hashes"][kind]:
        return True
    pending_ids, pending_hashes = _pending_assets(ledger, kind)
    return identity in pending_ids or bool(content_hash and content_hash in pending_hashes)


def filter_unused(paths: list[Path], kind: MediaKind) -> list[Path]:
    """Remove permanentemente usados e reservas pendentes do pool."""
    path = _usage_file()
    with state_lock(path):
        ledger = _load_ledger()
    return [p for p in paths if not descriptor_is_unavailable(asset_descriptor(p, kind), kind, ledger)]


def used_source_identities(kind: MediaKind) -> set[str]:
    """Snapshot de IDs usados/reservados para os sincronizadores."""
    path = _usage_file()
    with state_lock(path):
        ledger = _load_ledger()
    identities = set(ledger["used"][kind])
    pending, _ = _pending_assets(ledger, kind)
    return identities | pending


def used_hashes(kind: MediaKind) -> set[str]:
    path = _usage_file()
    with state_lock(path):
        ledger = _load_ledger()
    hashes = set(ledger["hashes"][kind])
    _, pending = _pending_assets(ledger, kind)
    return hashes | pending


def production_signature(audio: dict[str, str], videos: list[dict[str, str]]) -> str:
    payload = {
        "audio": audio["identity"],
        "videos": [video["identity"] for video in videos],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def reserve_media(audio_path: Path, video_paths: list[Path]) -> tuple[str, dict[str, Any]]:
    """Reserva atomica de uma faixa e todos os clipes da producao."""
    audio = asset_descriptor(audio_path, "audio", ensure_hash=True)
    videos = [asset_descriptor(path, "video", ensure_hash=True) for path in video_paths]
    signature = production_signature(audio, videos)
    reservation_id = uuid.uuid4().hex
    ledger_path = _usage_file()
    with state_lock(ledger_path):
        ledger = _load_ledger()
        if descriptor_is_unavailable(audio, "audio", ledger):
            raise MediaAlreadyUsedError(f"Musica indisponivel: {audio['identity']}")
        for video in videos:
            if descriptor_is_unavailable(video, "video", ledger):
                raise MediaAlreadyUsedError(f"Clipe indisponivel: {video['identity']}")
        if signature in ledger["productions"]:
            raise MediaAlreadyUsedError(f"Combinacao ja produzida: {signature}")
        if any(item.get("signature") == signature for item in ledger["pending"].values()):
            raise MediaAlreadyUsedError(f"Combinacao ja reservada: {signature}")
        reservation = {
            "created_at": datetime.now(UTC).isoformat(),
            "audio": [audio],
            "video": videos,
            "signature": signature,
        }
        ledger["pending"][reservation_id] = reservation
        _save_ledger(ledger)
    return reservation_id, reservation


def commit_reservation(reservation_id: str, output: Path) -> dict[str, Any]:
    """Marca definitivamente os assets depois que o video passa na validacao."""
    ledger_path = _usage_file()
    with state_lock(ledger_path):
        ledger = _load_ledger()
        reservation = ledger["pending"].pop(reservation_id, None)
        if reservation is None:
            raise KeyError(f"Reserva desconhecida: {reservation_id}")
        committed_at = datetime.now(UTC).isoformat()
        for kind in ("audio", "video"):
            for asset in reservation[kind]:
                record = {**asset, "reservation_id": reservation_id, "committed_at": committed_at}
                ledger["used"][kind][asset["identity"]] = record
                if asset.get("sha256"):
                    ledger["hashes"][kind][asset["sha256"]] = asset["identity"]
        ledger["productions"][reservation["signature"]] = {
            "reservation_id": reservation_id,
            "output": str(output),
            "committed_at": committed_at,
        }
        _save_ledger(ledger)
    return reservation


def release_reservation(reservation_id: str) -> None:
    """Libera assets quando a geracao nao chegou a produzir video valido."""
    ledger_path = _usage_file()
    with state_lock(ledger_path):
        ledger = _load_ledger()
        if ledger["pending"].pop(reservation_id, None) is not None:
            _save_ledger(ledger)
