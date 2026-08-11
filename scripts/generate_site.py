"""
scripts/generate_site.py — gera um site estático SEO (schema.org) a partir dos
dados de analytics e video_tags.

Lê _data/video_tags.json + _data/analytics.json e gera em _site/:
- uma página index.html listando todos os vídeos com thumbnails (link youtu.be)
- uma página por vídeo (video_{id}.html) com título, descrição, thumbnail,
  upload date e <script type="application/ld+json"> com VideoObject.

O site é estático (sem backend) e pode ser deployado junto ao dashboard no
GitHub Pages. A geração nunca quebra: arquivos ausentes produzem um site
mínimo (aviso) em vez de erro.
"""

from __future__ import annotations

import json
import logging
import sys
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.paths import data_dir

log = logging.getLogger(__name__)

_THUMB_URL = "https://img.youtube.com/vi/{vid}/hqdefault.jpg"
_WATCH_URL = "https://youtu.be/{vid}"
_CHANNEL_URL = "https://www.youtube.com/@PataJazz-n5n"
_CHANNEL_ID = "UCYAxnaW6H8g3XJMntkDXZjg"
_FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={_CHANNEL_ID}"
_ATOM_NS = "{http://www.w3.org/2005/Atom}"
_YT_NS = "{http://www.youtube.com/xml/schemas/2015}"
_MEDIA_NS = "{http://search.yahoo.com/mrss/}"


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def _build_video_entries(video_tags: dict, analytics: dict) -> list[dict]:
    """Cruza video_tags.json (cena/description) com analytics.json (views/
    published_at) numa lista de entradas prontas para renderização."""
    all_videos_raw = analytics.get("all_videos") if analytics else []
    all_videos = all_videos_raw if isinstance(all_videos_raw, list) else []
    by_id = {str(v.get("video_id")): v for v in all_videos if isinstance(v, dict) and v.get("video_id")}

    entries: list[dict] = []
    seen: set[str] = set()
    for vid, tag in (video_tags or {}).items():
        if not isinstance(tag, dict) or not vid or vid in seen:
            continue
        seen.add(vid)
        stat = by_id.get(vid, {})
        description = str(tag.get("description") or stat.get("title") or "Cute cats and dogs with relaxing jazz music.")
        entry = {
            "video_id": vid,
            "title": str(stat.get("title") or tag.get("title") or f"Pata Jazz video {vid}"),
            "description": description,
            "published_at": str(stat.get("published_at") or tag.get("uploaded_at") or ""),
            "views": int(stat.get("views", 0) or 0),
            "likes": int(stat.get("likes", 0) or 0),
            "thumbnail": str(tag.get("thumbnail_url") or _THUMB_URL.format(vid=vid)),
            "watch_url": _WATCH_URL.format(vid=vid),
            "scene": str(tag.get("scene") or ""),
        }
        entries.append(entry)
    # Vídeos em analytics que não estão em video_tags (sem tags) — ainda aparecem.
    for vid, stat in by_id.items():
        if vid in seen:
            continue
        seen.add(vid)
        entries.append(
            {
                "video_id": vid,
                "title": str(stat.get("title") or f"Pata Jazz video {vid}"),
                "description": "Cute cats and dogs with relaxing jazz music.",
                "published_at": str(stat.get("published_at") or ""),
                "views": int(stat.get("views", 0) or 0),
                "likes": int(stat.get("likes", 0) or 0),
                "thumbnail": _THUMB_URL.format(vid=vid),
                "watch_url": _WATCH_URL.format(vid=vid),
                "scene": "",
            }
        )
    entries.sort(key=lambda e: e["views"], reverse=True)
    return entries


def _youtube_feed_entries(limit: int = 12) -> list[dict]:
    """Lê o feed público oficial como fallback quando o cache ainda está vazio."""
    try:
        request = Request(_FEED_URL, headers={"User-Agent": "PataJazzSite/1.0"})
        with urlopen(request, timeout=15) as response:  # nosec B310 - URL fixa do feed oficial do YouTube.
            root = ET.fromstring(response.read())
    except Exception as exc:
        log.warning("Feed público do YouTube indisponível: %s", exc)
        return []

    entries: list[dict] = []
    for item in root.findall(f"{_ATOM_NS}entry")[:limit]:
        video_id = (item.findtext(f"{_YT_NS}videoId") or "").strip()
        title = (item.findtext(f"{_ATOM_NS}title") or "").strip()
        if not video_id or not title:
            continue
        link = next(
            (
                node.get("href", "")
                for node in item.findall(f"{_ATOM_NS}link")
                if node.get("rel") == "alternate"
            ),
            _WATCH_URL.format(vid=video_id),
        )
        thumbnail_node = item.find(f".//{_MEDIA_NS}thumbnail")
        entries.append(
            {
                "video_id": video_id,
                "title": title,
                "description": "A gentle Pata Jazz pet moment with soft jazz music.",
                "published_at": (item.findtext(f"{_ATOM_NS}published") or "").strip(),
                "views": 0,
                "likes": 0,
                "thumbnail": (thumbnail_node.get("url", "") if thumbnail_node is not None else "")
                or _THUMB_URL.format(vid=video_id),
                "watch_url": link,
                "scene": "",
            }
        )
    return entries


def _video_object_ld(entry: dict) -> str:
    """Gera o JSON-LD schema.org VideoObject para uma entrada de vídeo."""
    ld = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": entry["title"],
        "description": entry["description"],
        "thumbnailUrl": entry["thumbnail"],
        "uploadDate": (entry["published_at"] or "")[:10],
        "contentUrl": entry["watch_url"],
        "embedUrl": f"https://www.youtube.com/embed/{entry['video_id']}",
    }
    if entry["views"]:
        ld["interactionStatistic"] = {
            "@type": "InteractionCounter",
            "interactionType": {"@type": "WatchAction"},
            "userInteractionCount": entry["views"],
        }
    return json.dumps(ld, ensure_ascii=False, indent=2)


def _render_video_page(entry: dict) -> str:
    ld_json = escape(_video_object_ld(entry), quote=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(entry["title"])} — Pata Jazz</title>
<meta name="description" content="{escape(entry["description"][:160])}">
<script type="application/ld+json">
{ld_json}
</script>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    max-width: 720px; margin: 0 auto; padding: 24px 16px;
    background: #0f0f23; color: #f8f8ff;
  }}
  h1 {{ font-size: 1.4rem; }}
  a {{ color: #f4a261; }}
  img {{ max-width: 100%; border-radius: 12px; }}
  .meta {{ color: #9a9ab8; font-size: 0.85rem; margin: 8px 0; }}
  .back {{ margin-bottom: 16px; display: inline-block; }}
</style>
</head>
<body>
  <a class="back" href="index.html">← All videos</a>
  <h1>{escape(entry["title"])}</h1>
  <p class="meta">{escape(entry["published_at"][:10] or "")} · {entry["views"]:,} views · {entry["likes"]:,} likes</p>
  <a href="{escape(entry["watch_url"])}" target="_blank" rel="noopener">
    <img src="{escape(entry["thumbnail"])}" alt="{escape(entry["title"])}" loading="lazy">
  </a>
  <p>{escape(entry["description"])}</p>
  <p><a href="{escape(entry["watch_url"])}" target="_blank" rel="noopener">Watch on YouTube →</a></p>
</body>
</html>
"""


def _render_index(entries: list[dict]) -> str:
    cards = []
    for e in entries:
        cards.append(
            f'<a class="card" href="video_{escape(e["video_id"])}.html">'
            f'<img src="{escape(e["thumbnail"])}" alt="{escape(e["title"])}" loading="lazy">'
            f"<h3>{escape(e['title'])}</h3>"
            f'<span class="views">{e["views"]:,} views</span>'
            f"</a>"
        )
    cards_html = "\n".join(cards)
    empty_state = (
        '<p class="empty">Fresh Pata Jazz videos are being indexed. '
        f'<a href="{_CHANNEL_URL}" target="_blank" rel="noopener">Watch the channel on YouTube</a>.</p>'
        if not entries
        else ""
    )
    item_list = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "Pata Jazz videos",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": e["watch_url"], "name": e["title"]}
            for i, e in enumerate(entries)
        ],
    }
    ld_json = escape(json.dumps(item_list, ensure_ascii=False, indent=2), quote=False).replace("</", "<\\/")
    desc = escape("Cute cats and dogs with relaxing jazz music."[:90])
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pata Jazz — Cute cats & dogs with relaxing music</title>
<meta name="description" content="All Pata Jazz videos: {desc}">
<script type="application/ld+json">
{ld_json}
</script>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    max-width: 960px; margin: 0 auto; padding: 24px 16px;
    background: #0f0f23; color: #f8f8ff;
  }}
  h1 {{ font-size: 1.6rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }}
  .card {{
    display: block; text-decoration: none; color: inherit;
    background: rgba(26,26,62,0.55); border: 1px solid rgba(244,162,97,0.12);
    border-radius: 12px; overflow: hidden;
  }}
  .card img {{ width: 100%; aspect-ratio: 16/9; object-fit: cover; }}
  .card h3 {{ font-size: 0.9rem; margin: 8px 12px; }}
  .card .views {{ color: #9a9ab8; font-size: 0.8rem; margin: 0 12px 12px; display: block; }}
  .channel-cta {{
    display: inline-block; margin: 8px 0 24px; padding: 10px 16px;
    border-radius: 999px; background: #f4a261; color: #17172d;
    font-weight: 700; text-decoration: none;
  }}
  .empty {{ padding: 24px; border: 1px solid rgba(244,162,97,0.2); border-radius: 12px; color: #d6d6ec; }}
  .empty a {{ color: #f4a261; }}
</style>
</head>
<body>
  <h1>🐾🎷 Pata Jazz</h1>
  <p>Soft jazz and gentle pet moments for quieter homes.</p>
  <a class="channel-cta" href="{_CHANNEL_URL}" target="_blank" rel="noopener">Watch Pata Jazz on YouTube</a>
  {empty_state}
  <div class="grid">
{cards_html}
  </div>
</body>
</html>
"""


def generate_site(output_dir: Path | None = None) -> Path:
    """Gera o site estático em output_dir (default _site/). Retorna o caminho
    do index.html."""
    out = output_dir or (ROOT / "_site")
    out.mkdir(parents=True, exist_ok=True)

    video_tags = _load_json(data_dir() / "video_tags.json", {})
    analytics = _load_json(data_dir() / "analytics.json", {})
    entries = _build_video_entries(video_tags, analytics)
    if not entries:
        entries = _youtube_feed_entries()

    index_path = out / "index.html"
    index_path.write_text(_render_index(entries), encoding="utf-8")

    for entry in entries:
        page_path = out / f"video_{entry['video_id']}.html"
        page_path.write_text(_render_video_page(entry), encoding="utf-8")

    log.info("Site gerado: %s (%d páginas)", index_path, len(entries))
    return index_path


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    generate_site()
    return 0


if __name__ == "__main__":
    sys.exit(main())
