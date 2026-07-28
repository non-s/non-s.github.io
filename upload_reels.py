"""
upload_reels.py — cross-posting de Shorts para o Instagram Reels (scaffolding).

A Instagram Graph API (Content Publishing API) requer credenciais OAuth
que ainda nao configuramos para o canal. Este modulo implementa o esqueleto
do cross-posting: lê o video + metadata, monta o multipart upload da API
e delega para `upload_to_reels`. Sem `INSTAGRAM_ACCESS_TOKEN` no ambiente,
loga e retorna None (no-op) - assim o workflow de cross-posting pode rodar
em CI sem credenciais sem falhar.

Quando as credenciais estiverem disponiveis, basta substituir o bloco
try/except marcado como scaffolding pela chamada HTTP real (requests.post
multipart) - a assinatura de `upload_to_reels` ja esta no formato final.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from utils.log_config import configure_logging

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"

_INSTAGRAM_API_URL = "https://graph.facebook.com/v19.0/"


def upload_to_reels(
    video_path: Path,
    meta: dict,
    credentials: dict | None = None,
) -> str | None:
    """Faz upload de um video para o Instagram Reels via Content Publishing API.

    Args:
        video_path: caminho do arquivo .mp4 a enviar.
        meta: metadata do video (title, description, hashtags, etc).
        credentials: dict com access_token/etc; se None, le do ambiente.

    Retorna o id do Reel em caso de sucesso, ou None quando:
    - INSTAGRAM_ACCESS_TOKEN ausente (cross-posting desligado)
    - a chamada real ainda nao foi implementada (scaffolding)
    """
    creds = credentials or {}
    access_token = creds.get("access_token") or os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    if not access_token:
        log.info("Instagram cross-posting not configured (set INSTAGRAM_ACCESS_TOKEN)")
        return None

    caption = str(meta.get("title", "Pata Jazz"))
    description = str(meta.get("description", ""))
    hashtags = meta.get("hashtags") or []
    hashtag_text = " ".join(f"#{h.lstrip('#')}" for h in hashtags)
    full_caption = f"{caption}\n\n{description}\n\n{hashtag_text}".strip()[:2200]
    post_body = {
        "caption": full_caption,
        "media_type": "REELS",
        "video_url": str(video_path),
        "access_token": access_token,
    }

    try:
        # Scaffolding: a chamada HTTP real (requests.post multipart com o
        # arquivo aberto em modo binario) fica aqui. Levanta NotImplementedError
        # para sinalizar que o cross-posting real ainda nao esta ligado.
        raise NotImplementedError("Instagram Reels upload not yet implemented (scaffolding)")
    except NotImplementedError as exc:
        log.info(str(exc))
        log.debug("post_body=%s", post_body)
        return None


def cross_post_all_unpublished(prefix: str = "pata_jazz_") -> list[str]:
    """Encontra videos ainda nao cross-postados para o Instagram e tenta envia-los.

    Reaproveita a logica de `publish_weekly_batch._find_unpublished_videos`
    (videos sem `published=True`/`video_id`) e chama `upload_to_reels` para
    cada um. Marca `instagram_id` no metadata quando o upload tem sucesso.

    Retorna a lista de ids dos Reels enviados (vazia sem credenciais).
    """
    from scripts.publish_weekly_batch import _find_unpublished_videos

    unpublished = _find_unpublished_videos(prefix=prefix)
    if not unpublished:
        log.info("Nenhum video aguardando cross-posting para o Instagram.")
        return []

    posted: list[str] = []
    for video_path, meta in unpublished:
        reel_id = upload_to_reels(video_path, meta)
        if reel_id:
            meta["instagram_id"] = reel_id
            video_path.with_suffix(".json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            posted.append(reel_id)
    return posted


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-posting Pata Jazz para Instagram Reels")
    parser.add_argument("--video", default="", help="Caminho do arquivo .mp4 a enviar")
    parser.add_argument("--meta", default="", help="Caminho do .json de metadata do video")
    parser.add_argument("--prefix", default="pata_jazz_", help="Prefixo dos arquivos para cross_post_all")
    parser.add_argument(
        "--all", action="store_true",
        help="Cross-posta todos os nao publicados (ignora --video/--meta)",
    )
    args = parser.parse_args()

    configure_logging()

    if args.all:
        posted = cross_post_all_unpublished(prefix=args.prefix)
        log.info("Cross-posting Instagram concluido: %d videos enviados.", len(posted))
        return 0

    if not args.video or not args.meta:
        log.error("--video e --meta sao obrigatorios (ou use --all)")
        return 1

    video_path = Path(args.video)
    if not video_path.exists():
        log.error("Video nao encontrado: %s", video_path)
        return 1

    try:
        meta = json.loads(Path(args.meta).read_text(encoding="utf-8"))
    except Exception as exc:
        log.error("Metadata invalida em %s: %s", args.meta, exc)
        return 1

    reel_id = upload_to_reels(video_path, meta)
    if reel_id:
        print(reel_id)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
