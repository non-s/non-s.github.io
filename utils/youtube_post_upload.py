"""utils/youtube_post_upload.py — acoes pos-upload compartilhadas.

Thumbnail, legenda e adicao em playlist sao passos colaterais que aparecem
tanto em upload_youtube.py (upload diario) quanto em
scripts/publish_weekly_batch.py (lote semanal). Centralizar aqui evita
regressoes quando uma correcao e aplicada so em um dos lados.
"""

from __future__ import annotations

import logging
from pathlib import Path

from googleapiclient.http import MediaFileUpload

from utils.playlist_manager import add_video_to_playlist

log = logging.getLogger(__name__)


def _thumbnail_hint(exc: Exception) -> str:
    if "403" in str(exc):
        return " (canal sem verificacao por telefone bloqueia thumbnail customizada - confira em youtube.com/verify)"
    return ""


def apply_thumbnail(
    service,
    video_id: str,
    thumbnail: Path | None,
    retry_call,
) -> None:
    """Aplica uma thumbnail customizada, se existir, sem derrubar o upload."""
    if not thumbnail or not thumbnail.exists():
        return
    try:
        # Re-verifica existencia (TOCTOU) e instancia MediaFileUpload dentro do try.
        thumb_media = MediaFileUpload(str(thumbnail))
        retry_call(service.thumbnails().set(videoId=video_id, media_body=thumb_media).execute)
        log.info("Thumbnail aplicada.")
    except Exception as exc:
        # Nao so HttpError: _retry_youtube_call levanta RuntimeError quando
        # esgota as tentativas em erros retryable persistentes; sem o catch
        # generico o erro escaparia e derrubaria upload_video() inteiro,
        # pulando legenda e playlist apesar do video ja publicado.
        log.warning("Falha ao aplicar thumbnail: %s%s", exc, _thumbnail_hint(exc))


def _caption_mimetype(caption_path: Path) -> str:
    suffix = caption_path.suffix.lower()
    if suffix == ".vtt":
        return "text/vtt"
    if suffix == ".ass":
        return "text/x-ssa"
    return "application/x-subrip"


def apply_caption(
    service,
    video_id: str,
    caption_path: Path | None,
    retry_call,
    *,
    language: str = "en",
    name: str = "English",
) -> None:
    """Faz upload de legenda (.srt, .vtt ou .ass), se existir."""
    if not caption_path or not caption_path.exists():
        return
    try:
        caption_body = {
            "snippet": {
                "videoId": video_id,
                "language": language,
                "name": name,
                "isDraft": False,
            }
        }
        retry_call(
            service.captions()
            .insert(
                part="snippet",
                body=caption_body,
                media_body=MediaFileUpload(str(caption_path), mimetype=_caption_mimetype(caption_path)),
            )
            .execute
        )
        log.info("Legenda %s aplicada.", language)
    except Exception as exc:
        # Ver comentario equivalente no bloco de thumbnail acima.
        log.warning("Falha ao aplicar legenda %s: %s", language, exc)


def _meta_path(meta: dict, key: str) -> Path | None:
    """Path(meta.get(key, '')) para uma chave ausente/vazia vira Path('')
    == Path('.') - e .exists() no diretorio atual e sempre True, entao
    codigo tentaria abrir um diretorio. So constroi o Path se o valor for
    uma string nao-vazia."""
    value = meta.get(key)
    return Path(value) if value else None


def apply_captions(
    service,
    video_id: str,
    meta: dict,
    retry_call,
) -> None:
    """Aplica todas as caption tracks disponiveis (EN + PT).

    1.3 - Suporte a multiplas caption tracks: EN (default) + PT-BR (se
    meta['caption_pt'] existir, gerada por utils/caption_engine).
    """
    apply_caption(
        service,
        video_id,
        _meta_path(meta, "caption"),
        retry_call,
        language="en",
        name="English",
    )
    caption_pt = meta.get("caption_pt")
    if caption_pt:
        apply_caption(
            service,
            video_id,
            Path(caption_pt),
            retry_call,
            language="pt",
            name="Português",
        )


def add_to_playlists(service, video_id: str, meta: dict) -> None:
    """Adiciona o video as playlists automaticas: por formato (kind) e por mood,
    para aumentar sessao e recomendacoes.

    add_video_to_playlist so adiciona a UMA playlist por chamada (mood tem
    prioridade sobre kind), entao sao chamadas separadas para popular todas
    as playlists relevantes.
    """
    try:
        if meta.get("mood"):
            add_video_to_playlist(service, video_id, mood=meta["mood"])

        add_video_to_playlist(service, video_id, kind=meta.get("kind", ""))
    except Exception as exc:
        log.warning("Falha ao adicionar a playlist: %s", exc)
