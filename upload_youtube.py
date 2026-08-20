"""
upload_youtube.py — faz upload de videos gravados no YouTube.

Depende do token OAuth em youtube_token.json ou das variaveis YOUTUBE_TOKEN / YOUTUBE_CLIENT_SECRET.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from utils import ffmpeg_helpers
from utils.atomic_state import atomic_write_json
from utils.channel_config import active_channel
from utils.chapter_markers import prepend_chapters
from utils.content_funnel import append_related_video_cta, record_funnel_candidate
from utils.log_config import configure_logging, log_exception_to_file
from utils.metadata_audit import audit_description, audit_title
from utils.notifier import send_alert
from utils.paths import data_dir
from utils.pipeline_metrics import record_pipeline_run
from utils.publication_ledger import video_tag_record, write_receipt
from utils.quota_tracker import (
    ALERT_THRESHOLD,
    UPLOAD_ALERT_THRESHOLD,
    UPLOAD_DAILY_LIMIT,
    daily_call_count,
    daily_total,
)
from utils.seo_keywords import record_used_title
from utils.state_lock import state_lock
from utils.youtube_oauth import get_youtube_service
from utils.youtube_post_upload import add_to_playlists, apply_captions, apply_thumbnail
from utils.youtube_retry import retry_youtube_call as _retry_youtube_call

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"

log = logging.getLogger(__name__)


def _production_contract_issues(meta: dict) -> list[str]:
    """Require evidence that every published asset came from the active engine."""
    issues: list[str] = []
    if meta.get("visual_source") != "procedural_python":
        issues.append("visual_source_not_procedural")
    if meta.get("audio_source") != "synthetic_python":
        issues.append("audio_source_not_procedural")
    quality = meta.get("quality_report")
    if not isinstance(quality, dict) or quality.get("passed") is not True:
        issues.append("quality_gate_not_approved")
    elif quality.get("issues"):
        issues.append("quality_report_has_issues")
    profile = meta.get("generator_profile")
    version = str(profile.get("engine_version", "")) if isinstance(profile, dict) else ""
    try:
        version_parts = tuple(int(part) for part in version.split("."))
    except ValueError:
        version_parts = ()
    if version_parts < (2, 1):
        issues.append("engine_version_below_2_1")
    if version_parts >= (4, 1):
        issues.extend(f"metadata:{issue}" for issue in audit_title(str(meta.get("title", ""))))
        issues.extend(
            f"metadata:{issue}"
            for issue in audit_description(str(meta.get("title", "")), str(meta.get("description", "")))
        )
        if not meta.get("content_id") or not isinstance(meta.get("genome"), dict):
            issues.append("autonomous_identity_missing")
        if not isinstance(meta.get("visual_dna"), dict) or not isinstance(meta.get("audio_dna"), dict):
            issues.append("observed_dna_missing")
        readiness = meta.get("publication_readiness")
        if not isinstance(readiness, dict) or readiness.get("passed") is not True:
            issues.append("publication_policy_not_approved")
        autonomy = meta.get("autonomy_state")
        if isinstance(autonomy, dict) and autonomy.get("publication_allowed") is not True:
            issues.append("publication_kill_switch_active")
    fingerprint = quality.get("fingerprint") if isinstance(quality, dict) else None
    # Frente E expandiu o fingerprint perceptual de 20 para 32 dim. Aceitamos
    # ambas: 32 (engine atual) ou 20 (legacy, pre-Frente E). O proprio
    # liquid_wire_quality.py ja normaliza legacy 20->32 via zero-padding
    # antes de comparar, entao um video novo sempre traz 32 dims.
    if not isinstance(fingerprint, list) or len(fingerprint) not in (20, 32):
        issues.append("perceptual_fingerprint_missing")
    return issues


def _latest_video_meta(prefix: str = "") -> tuple[Path, dict] | None:
    pattern = f"{prefix}*.mp4" if prefix else "*.mp4"
    candidates = sorted(OUTPUT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not prefix:
        candidates = [p for p in candidates if p.name.startswith("liquid_wire_")]
    skipped = 0
    for video in candidates:
        meta_path = video.with_suffix(".json")
        if meta_path.exists():
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                if skipped:
                    log.warning("Video mais recente (%d) sem metadata foi pulado; usando %s.", skipped, video.name)
                return video, data
            except Exception:
                continue
        skipped += 1
    return None


def _meta_path(meta: dict, key: str) -> Path | None:
    """Path(meta.get(key, "")) para uma chave ausente/vazia vira Path("") ==
    Path(".") - e .exists() no diretorio atual e sempre True, entao codigo
    como MediaFileUpload(str(thumbnail)) tenta abrir um diretorio como
    arquivo e explode com IsADirectoryError em vez de so pular o upload
    opcional. So constroi o Path se o valor for realmente uma string nao-vazia.
    """
    value = meta.get(key)
    return Path(value) if value else None


def _build_tags(scene: str, hashtags: list[str] | None = None) -> list[str]:
    base = list(active_channel.base_tags)
    if scene:
        base.extend(word for word in scene.replace("-", " ").split() if len(word) > 2)
    if hashtags:
        # Remove o # para normalizar e junta com as tags base
        cleaned = [h.lstrip("#") for h in hashtags]
        base.extend(cleaned)
    return list(dict.fromkeys(base))[:15]


_MAX_VIDEO_TAGS = 500


def _video_tags_file() -> Path:
    """Retorna o path do video_tags.json isolado por canal.

    Expoe como atributo de modulo (`_VIDEO_TAGS_FILE`) para testes poderem
    monkeypatchar o path sem reimportar o modulo.
    """
    return _VIDEO_TAGS_FILE


_VIDEO_TAGS_FILE: Path = data_dir() / "video_tags.json"


def _record_video_tags(video_id: str, meta: dict) -> None:
    """Persiste scene/hook/mood/title_pattern do video enviado, indexado por video_id.

    collect_analytics.py so tinha views agregadas sem nenhuma pista de qual
    cena/hook/padrao de titulo gerou qual video - o "feedback loop"
    mencionado no docstring daquele modulo nunca existiu de verdade. Esse
    mapeamento e o que falta pra cruzar performance real (views) com o que
    gerou cada video.
    """
    scene = meta.get("scene", "")
    if not scene:
        return
    tags_file = _video_tags_file()
    with state_lock(tags_file):
        try:
            existing = json.loads(tags_file.read_text(encoding="utf-8")) if tags_file.exists() else {}
        except Exception:
            existing = {}
        existing[video_id] = video_tag_record(meta, datetime.now(UTC).isoformat())
        # Mantem so as N mais recentes (por ordem de insercao) pra nao crescer pra sempre.
        if len(existing) > _MAX_VIDEO_TAGS:
            for old_key in list(existing.keys())[: len(existing) - _MAX_VIDEO_TAGS]:
                del existing[old_key]
        try:
            tags_file.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(tags_file, existing)
        except Exception as exc:
            log.warning("Falha ao salvar video_tags: %s", exc)



def wait_for_content_id_check(
    service, video_id: str, max_wait_minutes: int = 12, poll_seconds: int = 20
) -> dict:
    """Poll YouTube API until video processing is complete.

    Checks ``videos.list`` every ``poll_seconds`` and models every terminal
    YouTube processing state. Only ``succeeded`` without a rejection/failure
    is publishable; ``failed`` and ``terminated`` fail closed.
    Returns dict with:
    - "processing_complete": bool
    - "has_claims": bool (if any content claims detected)
    - "safe_to_publish": bool (processing complete AND no claims)

    If max_wait_minutes is reached, returns processing_complete=False.
    """
    import time
    from datetime import UTC, datetime, timedelta

    deadline = datetime.now(UTC) + timedelta(minutes=max_wait_minutes)

    while datetime.now(UTC) < deadline:
        try:
            response = _retry_youtube_call(
                service.videos().list(
                    part="processingDetails,contentRating,status",
                    id=video_id,
                ).execute
            )
            items = response.get("items", [])
            if not items:
                return {"processing_complete": False, "has_claims": False, "safe_to_publish": False}

            item = items[0]
            processing = item.get("processingDetails", {})
            status = item.get("status", {})

            processing_status = str(processing.get("processingStatus", ""))
            processing_done = processing_status in {"succeeded", "failed", "terminated"}
            # Check for content claims (via contentRating or rejection)
            rejected = status.get("rejectionReason", "")
            has_claims = (
                bool(rejected)
                or bool(processing.get("processingFailureReason"))
                or processing_status in {"failed", "terminated"}
            )

            if processing_done:
                return {
                    "processing_complete": True,
                    "has_claims": has_claims,
                    "safe_to_publish": not has_claims,
                }
        except Exception as exc:
            log.warning("Content ID check error for %s: %s", video_id, exc)

        time.sleep(max(5, poll_seconds))

    return {"processing_complete": False, "has_claims": False, "safe_to_publish": False}


def _update_privacy_to_public(service, video_id: str) -> bool:
    """Flip a video's privacyStatus to public via videos.update.

    Returns True on success, False on failure. Best-effort: failures are
    logged but do not raise, since the video already exists on the channel.
    """
    try:
        body = {
            "id": video_id,
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
        }
        _retry_youtube_call(
            service.videos().update(part="status", body=body).execute
        )
        log.info("Video %s atualizado para public apos Content ID check.", video_id)
        return True
    except Exception as exc:
        log.error("Falha ao atualizar privacy do video %s para public: %s", video_id, exc)
        send_alert(
            f"Liquid Wire: falha ao publicar video {video_id} apos Content ID check: {exc}",
            level="error",
        )
        return False


def upload_video(
    language: str = "en",
    privacy: str = "public",
    prefix: str = "",
    publish_at: str | None = None,
    publish_after_check: bool = False,
) -> str | None:
    start_time = time.time()
    success = False
    remote_attempted = False
    try:
        candidate = _resolve_upload_candidate(prefix)
        if candidate is None:
            return None
        remote_attempted = True
        video_id = _upload_video_inner(
            language=language,
            privacy=privacy,
            prefix=prefix,
            publish_at=publish_at,
            publish_after_check=publish_after_check,
            candidate=candidate,
        )
        if video_id is not None:
            success = True
        return video_id
    finally:
        kind = prefix.rstrip("_") or "liquid_wire"
        record_pipeline_run(
            stage="upload",
            success=success,
            duration_seconds=time.time() - start_time,
            kind=kind,
            details={"remote_attempted": remote_attempted},
        )



def _resolve_upload_candidate(prefix: str) -> tuple[Path, dict] | None:
    """Find the latest video+meta pair and run pre-upload validations.

    Returns ``(video_path, meta)`` or ``None`` if no candidate is viable
    (missing, contract rejected, zero duration, quota exhausted).
    """
    found = _latest_video_meta(prefix=prefix)
    if not found:
        log.error("Nenhum video com metadata encontrado em %s", OUTPUT_DIR)
        return None
    video_path, meta = found

    if prefix.startswith("liquid_wire_"):
        contract_issues = _production_contract_issues(meta)
        if contract_issues:
            log.error("Contrato de producao rejeitou %s: %s", video_path.name, ", ".join(contract_issues))
            return None

    # Sanity check antes de gastar quota da API: um .mp4 com duracao 0 (ffprobe
    # nao consegue ler, encode truncado, etc) sempre indica arquivo corrompido -
    # nunca um video legitimo de 0s. Aborta cedo em vez de subir lixo pro canal.
    duration = ffmpeg_helpers.get_video_duration(str(video_path))
    if duration <= 0:
        log.error("Video %s com duracao invalida (%.1fs) - upload abortado.", video_path.name, duration)
        return None

    # videos.insert usa bucket granular proprio de 100 chamadas/dia. O pool
    # geral continua protegido separadamente para playlists, captions etc.
    upload_count = daily_call_count("videos", "insert")
    if upload_count >= UPLOAD_ALERT_THRESHOLD:
        log.error(
            "Bucket de uploads em %d/%d chamadas (limite operacional=%d) - upload abortado.",
            upload_count,
            UPLOAD_DAILY_LIMIT,
            UPLOAD_ALERT_THRESHOLD,
        )
        return None
    if daily_total() >= ALERT_THRESHOLD:
        log.error(
            "Quota do dia ja em %d/%d unidades (alerta em %d) - upload abortado para nao estourar.",
            daily_total(),
            10000,
            ALERT_THRESHOLD,
        )
        return None
    return video_path, meta


def _build_description(meta: dict) -> tuple[str, str | None]:
    """Assemble the final description (CTA + chapter markers).

    Returns ``(description, related_long_id)``.
    """
    description, related_long_id = append_related_video_cta(str(meta.get("description", "")), meta)
    profile = meta.get("generator_profile") or {}
    timeline = profile.get("timeline") if isinstance(profile, dict) else None
    if isinstance(timeline, list) and timeline:
        from utils.liquid_wire_timeline import CreativeEvent

        events = [CreativeEvent(**item) for item in timeline if isinstance(item, dict)]
        description = prepend_chapters(description, float(meta.get("duration", 0.0)), events)
    return description[:5000], related_long_id


def _build_upload_body(
    meta: dict,
    description: str,
    language: str,
    privacy: str,
    publish_at: str | None,
    publish_after_check: bool,
) -> tuple[dict, str, str]:
    """Build the ``videos().insert()`` body and resolve effective privacy.

    Returns ``(body, effective_privacy, target_privacy)`` where
    ``target_privacy`` is non-empty when a Content-ID-check flip is pending.
    """
    title = str(meta.get("title", active_channel.name))[:100]
    tags = _build_tags(meta.get("scene", ""), meta.get("hashtags"))
    meta_lang = str(meta.get("lang", "")).strip()
    effective_language = meta_lang if meta_lang else language

    status: dict = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
    if publish_at:
        status["publishAt"] = publish_at
        privacy = "private"  # agendado exige privacy private no upload
        status["privacyStatus"] = privacy
    # Frente F: when --publish-after-check is requested the video is uploaded
    # as private regardless of the requested privacy. After processing finishes
    # and the Content ID pre-check clears, the privacy is flipped to the
    # requested value (only "public" is actionable; unlisted/private stay as-is).
    target_privacy = ""
    requires_private_validation = meta.get("publication_readiness", {}).get("required_privacy") == "private"
    if (publish_after_check or requires_private_validation) and privacy == "public":
        target_privacy = "public" if publish_after_check else ""
        privacy = "private"
        status["privacyStatus"] = privacy

    # Music (10) is the safest default for ambient audio/visual sessions.
    category_id = str(meta.get("category_id", "10"))

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
            "defaultLanguage": effective_language,
            "defaultAudioLanguage": effective_language,
        },
        "status": status,
    }
    return body, privacy, target_privacy


def _post_upload(
    service,
    video_id: str,
    meta: dict,
    thumbnail: Path | None,
    publish_after_check: bool,
    target_privacy: str,
) -> None:
    """Run all post-upload steps: tags/funnel, thumbnail, captions, playlists,
    and the optional Content ID pre-check → public flip."""
    _record_video_tags(video_id, meta)
    record_funnel_candidate(video_id, meta)

    apply_thumbnail(service, video_id, thumbnail, _retry_youtube_call)
    apply_captions(service, video_id, meta, _retry_youtube_call)
    add_to_playlists(service, video_id, meta)

    # Frente F — Content ID pre-check: only flip to public after processing
    # completes with no claims/rejections. On claims or timeout the video
    # stays private and an alert is sent so a human can review it.
    if publish_after_check and target_privacy == "public":
        result = wait_for_content_id_check(service, video_id)
        if result["safe_to_publish"]:
            _update_privacy_to_public(service, video_id)
        elif result["has_claims"]:
            log.error(
                "Video %s ficou private: Content ID detectou claims/rejection.", video_id
            )
            send_alert(
                f"Liquid Wire: video {video_id} mantido private - Content ID claims detectadas.",
                level="error",
            )
        else:
            log.error(
                "Video %s ficou private: processamento nao concluiu apos tempo limite.",
                video_id,
            )
            send_alert(
                f"Liquid Wire: video {video_id} mantido private - processamento pendente apos timeout.",
                level="error",
            )


def _upload_video_inner(
    language: str = "en",
    privacy: str = "public",
    prefix: str = "",
    publish_at: str | None = None,
    publish_after_check: bool = False,
    candidate: tuple[Path, dict] | None = None,
) -> str | None:
    candidate = candidate or _resolve_upload_candidate(prefix)
    if candidate is None:
        return None
    video_path, meta = candidate

    description, related_long_id = _build_description(meta)
    if related_long_id:
        meta["related_long_video_id"] = related_long_id
        meta["description"] = description

    body, effective_privacy, target_privacy = _build_upload_body(
        meta, description, language, privacy, publish_at, publish_after_check
    )
    thumbnail = _meta_path(meta, "thumbnail")

    service = get_youtube_service()
    request = service.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=MediaFileUpload(str(video_path), chunksize=-1, resumable=True),
    )
    response = _retry_youtube_call(request.execute)
    video_id = response["id"]
    log.info("Video enviado: https://youtu.be/%s", video_id)

    # A resposta do insert() ja inclui "status" (pedido no part= acima) - da
    # pra conferir se o vídeo saiu mesmo com o privacyStatus pedido sem gastar
    # outra chamada. Vídeo preso em "private"/"processing" quando devia ser
    # público some do canal em silêncio; melhor logar alto do que descobrir
    # dias depois.
    actual_privacy = response.get("status", {}).get("privacyStatus")
    if actual_privacy != effective_privacy:
        log.error(
            "Video %s saiu com privacyStatus=%r, esperado %r - confira manualmente.",
            video_id,
            actual_privacy,
            effective_privacy,
        )

    write_receipt(OUTPUT_DIR, video_id, meta)
    record_used_title(str(meta.get("title", "")))
    _post_upload(service, video_id, meta, thumbnail, publish_after_check, target_privacy)
    return video_id



def main() -> int:
    parser = argparse.ArgumentParser(description="Upload Liquid Wire para YouTube")
    parser.add_argument("--mode", choices=["upload"], default="upload")
    parser.add_argument("--language", default="en")
    parser.add_argument(
        "--privacy", default=os.environ.get("YOUTUBE_PRIVACY", "public"), choices=["public", "unlisted", "private"]
    )
    parser.add_argument("--prefix", default="liquid_wire_", help="Prefixo dos arquivos de video a enviar")
    parser.add_argument(
        "--publish-at",
        default=None,
        help="ISO 8601 UTC para agendamento do vídeo no YouTube (opcional).",
    )
    parser.add_argument(
        "--publish-after-check",
        action="store_true",
        help="Upload as private, run Content ID pre-check, then flip to public if safe.",
    )
    args = parser.parse_args()

    configure_logging()

    try:
        video_id = upload_video(
            language=args.language,
            privacy=args.privacy,
            prefix=args.prefix,
            publish_at=args.publish_at,
            publish_after_check=args.publish_after_check,
        )
        if not video_id:
            return 1
        # video_id e publico (esta na URL publica do YouTube), seguro de imprimir.
        print(video_id)
        return 0
    except HttpError as exc:
        log.exception("Erro da YouTube API: %s", exc)
        log_exception_to_file(exc, OUTPUT_DIR)
        return 1
    except Exception as exc:
        log.exception("Falha no upload: %s", exc)
        log_exception_to_file(exc, OUTPUT_DIR)
        return 1


if __name__ == "__main__":
    sys.exit(main())
