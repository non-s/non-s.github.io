"""Audita títulos públicos pelo feed oficial do YouTube sem alterar o canal."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from defusedxml import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.metadata_audit import audit_title
from utils.paths import data_dir

CHANNEL_ID = "UCYAxnaW6H8g3XJMntkDXZjg"
FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
YT_NS = "{http://www.youtube.com/xml/schemas/2015}"

log = logging.getLogger(__name__)


def fetch_title_audit() -> list[dict[str, object]]:
    request = Request(FEED_URL, headers={"User-Agent": "PataJazzMetadataAudit/1.0"})
    with urlopen(request, timeout=15) as response:  # nosec B310 - feed oficial fixo do YouTube.
        root = ET.fromstring(response.read())

    report: list[dict[str, object]] = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        video_id = (entry.findtext(f"{YT_NS}videoId") or "").strip()
        title = (entry.findtext(f"{ATOM_NS}title") or "").strip()
        issues = audit_title(title)
        if issues:
            report.append({"video_id": video_id, "title": title, "issues": issues})
    return report


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        issues = fetch_title_audit()
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
