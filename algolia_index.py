#!/usr/bin/env python3
"""Index posts to Algolia search"""
import os, json, glob, re
import requests

def main():
    app_id = os.getenv("ALGOLIA_APP_ID")
    admin_key = os.getenv("ALGOLIA_ADMIN_KEY")
    index_name = os.getenv("ALGOLIA_INDEX_NAME", "globalbr_news")

    if not app_id or not admin_key:
        print("ALGOLIA_APP_ID/ALGOLIA_ADMIN_KEY not set — skipping")
        return

    records = []
    for path in glob.glob("_posts/*.md"):
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
            # parse frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    fm_text = parts[1]
                    body = parts[2]
                    # simple yaml parse
                    fm = {}
                    for line in fm_text.strip().split("\n"):
                        if ": " in line and not line.startswith(" "):
                            k, v = line.split(": ", 1)
                            fm[k.strip()] = v.strip().strip('"')

                    slug = os.path.basename(path).replace(".md", "")
                    date_parts = slug.split("-")[:3]
                    category = fm.get("categories", "").strip("[]").split(",")[0].strip()
                    url = f"/{category}/{'/'.join(date_parts)}/{'-'.join(slug.split('-')[3:])}/"

                    records.append({
                        "objectID": slug,
                        "title": fm.get("title", ""),
                        "description": fm.get("description", ""),
                        "date": "-".join(date_parts),
                        "url": url,
                        "image": fm.get("image", ""),
                        "source_name": fm.get("source_name", ""),
                        "categories": category,
                        "tags": fm.get("tags", ""),
                        "sentiment": fm.get("sentiment", ""),
                        "body_excerpt": re.sub(r'[#*\[\]`]', '', body[:500]).strip(),
                    })
        except Exception as e:
            print(f"Error processing {path}: {e}")

    if not records:
        print("No records to index")
        return

    # Batch upload to Algolia
    url = f"https://{app_id}.algolia.net/1/indexes/{index_name}/batch"
    headers = {"X-Algolia-Application-Id": app_id, "X-Algolia-API-Key": admin_key, "Content-Type": "application/json"}

    # Upload in batches of 1000
    for i in range(0, len(records), 1000):
        batch = records[i:i+1000]
        r = requests.post(url, headers=headers, json={"requests": [{"action": "updateObject", "body": rec} for rec in batch]})
        print(f"Indexed {len(batch)} records: {r.status_code}")

if __name__ == "__main__":
    main()
