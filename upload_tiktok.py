"""upload_tiktok.py — cross-posting de Shorts para o TikTok via browser automation.

Usa Playwright + stealth para passar pelo WAF do TikTok e fazer login +
upload por browser (sem API oficial). Login por email/senha com persistencia
de sessao via storage_state.

Env vars necessarias:
  TIKTOK_EMAIL — email da conta TikTok
  TIKTOK_PASSWORD — senha da conta TikTok
  TIKTOK_HEADLESS — "0" para modo headed (default: headless)
  TIKTOK_STATE_PATH — path do storage_state (default: tiktok_state.json)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from utils.log_config import configure_logging
from utils.tiktok_uploader import upload_to_tiktok

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "_videos"

# Se o login/sessao estiver quebrado (credenciais invalidas, captcha,
# conta bloqueada), cada video subsequente falharia do mesmo jeito -
# continuar tentando so aumenta o risco de a conta ser marcada por
# excesso de tentativas. Aborta o lote apos N falhas seguidas.
_MAX_CONSECUTIVE_FAILURES = 2


def cross_post_all_unpublished(prefix: str = "pata_jazz_") -> list[str]:
    """Encontra videos ainda nao cross-postados para o TikTok e envia.

    Reaproveita a logica de publish_weekly_batch._find_unpublished_videos.
    Marca tiktok_url no metadata quando o upload tem sucesso. Aborta cedo
    se houver `_MAX_CONSECUTIVE_FAILURES` falhas seguidas (provavel
    problema de conta/sessao, nao do video individual).
    """
    from scripts.publish_weekly_batch import _find_unpublished_videos

    unpublished = _find_unpublished_videos(prefix=prefix)
    if not unpublished:
        log.info("Nenhum video aguardando cross-posting para o TikTok.")
        return []

    posted: list[str] = []
    consecutive_failures = 0
    for video_path, meta in unpublished:
        url = upload_to_tiktok(video_path, meta)
        if url:
            consecutive_failures = 0
            meta["tiktok_url"] = url
            video_path.with_suffix(".json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            posted.append(url)
            # Rate limit: espera 60s entre uploads
            time.sleep(60)
        else:
            consecutive_failures += 1
            log.warning("Falha no upload TikTok de %s (%d/%d falhas seguidas).",
                        video_path.name, consecutive_failures, _MAX_CONSECUTIVE_FAILURES)
            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                log.error(
                    "Abortando lote apos %d falhas seguidas - provavel problema de "
                    "conta/sessao (nao de video individual). Veja _videos/tiktok_upload_state.json.",
                    consecutive_failures,
                )
                break
    return posted


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-posting Pata Jazz para TikTok")
    parser.add_argument("--video", default="", help="Caminho do arquivo .mp4 a enviar")
    parser.add_argument("--meta", default="", help="Caminho do .json de metadata do video")
    parser.add_argument("--prefix", default="pata_jazz_", help="Prefixo dos arquivos para cross_post_all")
    parser.add_argument("--all", action="store_true", help="Cross-posta todos os nao publicados")
    args = parser.parse_args()

    configure_logging()

    if args.all:
        posted = cross_post_all_unpublished(prefix=args.prefix)
        log.info("Cross-posting TikTok concluido: %d videos enviados.", len(posted))
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

    url = upload_to_tiktok(video_path, meta)
    if url:
        print(url)
        return 0
    log.error("Upload para o TikTok falhou (veja o log/estado acima).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
