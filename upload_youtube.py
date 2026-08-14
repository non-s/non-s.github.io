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
from utils.channel_config import active_channel
from utils.content_funnel import append_related_video_cta, record_funnel_candidate
from utils.log_config import configure_logging, log_exception_to_file
from utils.paths import data_dir
from utils.pipeline_metrics import record_pipeline_run
from utils.quota_tracker import (
    ALERT_THRESHOLD,
    UPLOAD_ALERT_THRESHOLD,
    UPLOAD_DAILY_LIMIT,
    daily_call_count,
    daily_total,
)
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
    fingerprint = quality.get("fingerprint") if isinstance(quality, dict) else None
    if not isinstance(fingerprint, list) or len(fingerprint) != 20:
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
        existing[video_id] = {
            "scene": scene,
            "hook": meta.get("hook", ""),
            "mood": meta.get("mood", ""),
            "kind": meta.get("kind", ""),
            "title": meta.get("title", ""),
            "title_alt": meta.get("title_alt", ""),
            "title_pattern": meta.get("title_pattern", ""),
            "lang": meta.get("lang", "en"),
            "uploaded_at": datetime.now(UTC).isoformat(),
            "thumbnails": meta.get("thumbnails", []),
            "thumbnail_variant": meta.get("thumbnail_variant", "A"),
            "editorial_brief": meta.get("editorial_brief", {}),
            "visual_intelligence": meta.get("visual_intelligence", {}),
            "story_card": meta.get("story_card", {}),
            "viewer_experience": meta.get("viewer_experience", {}),
        }
        # Mantem so as N mais recentes (por ordem de insercao) pra nao crescer pra sempre.
        if len(existing) > _MAX_VIDEO_TAGS:
            for old_key in list(existing.keys())[: len(existing) - _MAX_VIDEO_TAGS]:
                del existing[old_key]
        try:
            tags_file.parent.mkdir(parents=True, exist_ok=True)
            tags_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning("Falha ao salvar video_tags: %s", exc)



def upload_video(
    language: str = "en",
    privacy: str = "public",
    prefix: str = "",
    publish_at: str | None = None,
) -> str | None:
    start_time = time.time()
    success = False
    try:
        video_id = _upload_video_inner(
            language=language, privacy=privacy, prefix=prefix, publish_at=publish_at
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
        )



def _upload_video_inner(
    language: str = "en",
    privacy: str = "public",
    prefix: str = "",
    publish_at: str | None = None,
) -> str | None:
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

    title = str(meta.get("title", active_channel.name))[:100]
    description, related_long_id = append_related_video_cta(str(meta.get("description", "")), meta)
    description = description[:5000]
    if related_long_id:
        meta["related_long_video_id"] = related_long_id
        meta["description"] = description
    tags = _build_tags(meta.get("scene", ""), meta.get("hashtags"))
    thumbnail = _meta_path(meta, "thumbnail")

    # A3: se o metadata tem "lang" (decidido no generate via
    # pick_upload_language), usa como idioma do upload defaultAudioLanguage/
    # defaultLanguage. O --language do CLI continua como override explicito.
    meta_lang = str(meta.get("lang", "")).strip()
    effective_language = meta_lang if meta_lang else language

    status: dict = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
    if publish_at:
        status["publishAt"] = publish_at
        privacy = "private"  # agendado exige privacy private no upload
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
    if actual_privacy != privacy:
        log.error(
            "Video %s saiu com privacyStatus=%r, esperado %r - confira manualmente.",
            video_id,
            actual_privacy,
            privacy,
        )

    _record_video_tags(video_id, meta)
    record_funnel_candidate(video_id, meta)

    apply_thumbnail(service, video_id, thumbnail, _retry_youtube_call)
    apply_captions(service, video_id, meta, _retry_youtube_call)
    add_to_playlists(service, video_id, meta)

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
    args = parser.parse_args()

    configure_logging()

    try:
        video_id = upload_video(
            language=args.language,
            privacy=args.privacy,
            prefix=args.prefix,
            publish_at=args.publish_at,
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
