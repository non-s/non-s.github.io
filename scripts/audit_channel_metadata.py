"""Audita títulos públicos pelo feed oficial do YouTube sem alterar o canal."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from defusedxml import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.metadata_audit import audit_description, audit_title
from utils.paths import data_dir
from utils.youtube_oauth import get_youtube_service
from utils.youtube_retry import retry_youtube_call

CHANNEL_ID = "UCYAxnaW6H8g3XJMntkDXZjg"
FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
YT_NS = "{http://www.youtube.com/xml/schemas/2015}"
MRSS_NS = "{http://search.yahoo.com/mrss/}"
MAX_AUDIT_VIDEOS = 500

log = logging.getLogger(__name__)


def _audit_entries(entries: list[dict[str, str]]) -> list[dict[str, object]]:
    report: list[dict[str, object]] = []
    for entry in entries:
        video_id = entry["video_id"]
        title = entry["title"]
        description = entry["description"]
        issues = [*audit_title(title), *audit_description(title, description)]
        if issues:
            report.append({"video_id": video_id, "title": title, "description": description, "issues": issues})
    return report


def fetch_uploads_audit(service) -> list[dict[str, object]]:
    """Audit every upload visible to the authenticated channel owner."""
    channels = retry_youtube_call(service.channels().list(part="contentDetails", mine=True).execute)
    items = channels.get("items") or []
    if not items:
        raise RuntimeError("Nenhum canal encontrado para a credencial atual.")
    uploads = ((items[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
    if not uploads:
        raise RuntimeError("Playlist de uploads nao encontrada.")

    video_ids: list[str] = []
    page_token = ""
    while len(video_ids) < MAX_AUDIT_VIDEOS:
        response = retry_youtube_call(
            service.playlistItems()
            .list(part="contentDetails", playlistId=uploads, maxResults=50, pageToken=page_token)
            .execute
        )
        video_ids.extend(
            str((item.get("contentDetails") or {}).get("videoId") or "")
            for item in response.get("items", [])
        )
        video_ids = [video_id for video_id in video_ids if video_id]
        page_token = str(response.get("nextPageToken") or "")
        if not page_token:
            break

    entries: list[dict[str, str]] = []
    for start in range(0, len(video_ids), 50):
        response = retry_youtube_call(
            service.videos().list(part="snippet", id=",".join(video_ids[start : start + 50])).execute
        )
        for item in response.get("items", []):
            snippet = item.get("snippet") or {}
            entries.append(
                {
                    "video_id": str(item.get("id") or ""),
                    "title": str(snippet.get("title") or "").strip(),
                    "description": str(snippet.get("description") or "").strip(),
                }
            )
    return _audit_entries(entries)


def fetch_title_audit() -> list[dict[str, object]]:
    request = Request(FEED_URL, headers={"User-Agent": "PataJazzMetadataAudit/1.0"})
    with urlopen(request, timeout=15) as response:  # nosec B310 - feed oficial fixo do YouTube.
        root = ET.fromstring(response.read())

    entries: list[dict[str, str]] = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        entries.append(
            {
                "video_id": (entry.findtext(f"{YT_NS}videoId") or "").strip(),
                "title": (entry.findtext(f"{ATOM_NS}title") or "").strip(),
                "description": (entry.findtext(f"{MRSS_NS}group/{MRSS_NS}description") or "").strip(),
            }
        )
    return _audit_entries(entries)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audita metadados publicos do canal Pata Jazz.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="retorna erro quando encontrar metadados inconsistentes",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        token_path = ROOT / "youtube_token.json"
        issues = fetch_uploads_audit(get_youtube_service()) if token_path.exists() else fetch_title_audit()
    except Exception as exc:
        log.error("Falha ao auditar feed público: %s", exc)
        return 1

    output = data_dir() / "channel_metadata_audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"audited_at": datetime.now(UTC).isoformat(), "issues": issues}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("Auditoria concluída: %d títulos com inconsistências.", len(issues))
    for issue in issues:
        raw_issues = issue.get("issues", [])
        issue_text = ", ".join(raw_issues) if isinstance(raw_issues, list) else str(raw_issues)
        log.warning("%s: %s", str(issue.get("video_id", "")), issue_text)
    if args.strict and issues:
        log.error("Auditoria estrita falhou: corrija os metadados publicos antes da proxima publicacao.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
