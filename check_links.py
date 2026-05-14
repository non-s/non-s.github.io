#!/usr/bin/env python3
"""Check source URLs in recent posts for broken links."""
import glob
import json
import logging
import os
import re
from datetime import date, timedelta
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main():
    # Check posts from last 7 days
    cutoff = date.today() - timedelta(days=7)

    broken, ok, skipped = [], [], []

    for path in sorted(glob.glob("_posts/*.md"), reverse=True)[:50]:
        fname = Path(path).name
        try:
            date_str = "-".join(fname.split("-")[:3])
            if date.fromisoformat(date_str) < cutoff:
                break
        except Exception:
            continue

        try:
            content = Path(path).read_text(encoding="utf-8")
            m = re.search(r"^source_url:\s*(.+)$", content, re.MULTILINE)
            if not m:
                continue

            url = m.group(1).strip().strip('"').strip("'")
            if not url.startswith("http"):
                continue

            try:
                r = requests.head(
                    url,
                    timeout=10,
                    allow_redirects=True,
                    headers={"User-Agent": "Mozilla/5.0 GlobalBRNews/1.0"},
                )
                if r.status_code < 400:
                    ok.append({"file": fname, "url": url, "status": r.status_code})
                else:
                    broken.append({"file": fname, "url": url, "status": r.status_code})
                    logging.warning(f"Broken: {url} ({r.status_code})")
            except Exception as e:
                skipped.append({"file": fname, "url": url, "error": str(e)[:100]})

        except Exception as e:
            logging.warning(f"Error reading {path}: {e}")

    report = {
        "date": date.today().isoformat(),
        "checked": len(ok) + len(broken),
        "ok": len(ok),
        "broken": len(broken),
        "broken_list": broken,
        "skipped": len(skipped),
    }

    os.makedirs("_data", exist_ok=True)
    with open("_data/link_report.json", "w") as f:
        json.dump(report, f, indent=2)

    logging.info(f"Done: {len(ok)} OK, {len(broken)} broken, {len(skipped)} skipped")


if __name__ == "__main__":
    main()
