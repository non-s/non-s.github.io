#!/usr/bin/env python3
"""Generates search-index.json with full post content for client-side search."""
import json
import re
from pathlib import Path

POSTS_DIR = Path(__file__).parent / "_posts"
OUT = Path(__file__).parent / "search-index.json"

_HTML_TAG_RE = re.compile(r'<[^>]+>')
_CODE_BLOCK_RE = re.compile(r'```.*?```', re.DOTALL)
_INLINE_CODE_RE = re.compile(r'`[^`]+`')
_IMAGE_RE = re.compile(r'!\[.*?\]\(.*?\)')
_LINK_RE = re.compile(r'\[([^\]]+)\]\([^\)]+\)')
_HEADING_RE = re.compile(r'#{1,6}\s+')
_BOLD_RE = re.compile(r'[*_]{1,2}([^*_]+)[*_]{1,2}')
_LIST_RE = re.compile(r'^\s*[-*+]\s+', re.MULTILINE)
_WHITESPACE_RE = re.compile(r'\n+')


def strip_markdown(text: str) -> str:
    text = _CODE_BLOCK_RE.sub('', text)
    text = _INLINE_CODE_RE.sub('', text)
    text = _IMAGE_RE.sub('', text)
    text = _LINK_RE.sub(r'\1', text)
    text = _HEADING_RE.sub('', text)
    text = _BOLD_RE.sub(r'\1', text)
    text = _LIST_RE.sub('', text)
    text = _HTML_TAG_RE.sub(' ', text)
    text = _WHITESPACE_RE.sub(' ', text).strip()
    return text


def parse_post(path: Path) -> dict | None:
    text = path.read_text(encoding='utf-8', errors='replace')
    if not text.startswith('---'):
        return None
    parts = text.split('---', 2)
    if len(parts) < 3:
        return None
    fm_text, body = parts[1], parts[2]
    fm: dict = {}
    for line in fm_text.splitlines():
        if ':' not in line:
            continue
        k, _, v = line.partition(':')
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if v.startswith('[') and v.endswith(']'):
            fm[k] = [x.strip().strip('"').strip("'") for x in v[1:-1].split(',') if x.strip()]
        else:
            fm[k] = v

    # Extract YYYY-MM-DD and slug — take first 3 dash-parts as date, rest as slug
    stem = path.stem
    date_parts = stem.split('-', 3)
    if len(date_parts) < 4:
        return None
    year, month, day = date_parts[0], date_parts[1], date_parts[2]
    slug = date_parts[3]  # everything after YYYY-MM-DD- is the slug (may contain dashes)

    # Validate date parts
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        return None

    cats = fm.get('categories', [])
    category = (cats[0] if isinstance(cats, list) and cats else 'news').strip()
    url = f"/{category}/{year}/{month}/{day}/{slug}/"
    content_clean = strip_markdown(body)[:600]

    return {
        'title':       fm.get('title', '').strip('"').strip("'"),
        'url':         url,
        'date':        fm.get('date', '')[:10],  # YYYY-MM-DD only
        'category':    category,
        'tags':        fm.get('tags', []),
        'description': fm.get('description', '').strip('"').strip("'"),
        'content':     content_clean,
        'image':       fm.get('image', ''),
        'sentiment':   fm.get('sentiment', 'neutral'),
        'source':      fm.get('source_name', ''),
    }


index = []
for path in sorted(POSTS_DIR.glob('*.md'), reverse=True):
    try:
        item = parse_post(path)
        if item and item['title']:
            index.append(item)
    except Exception as e:
        print(f"Warning: skipping {path.name} — {e}")

OUT.write_text(json.dumps(index, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print(f"search-index.json: {len(index)} posts indexed")
