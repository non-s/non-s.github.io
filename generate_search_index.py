#!/usr/bin/env python3
"""Generates search-index.json with full post content for client-side search."""
import json, re
from pathlib import Path

POSTS_DIR = Path(__file__).parent / "_posts"
OUT = Path(__file__).parent / "search-index.json"

def strip_markdown(text):
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'`[^`]+`', '', text)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'#{1,6}\s+', '', text)
    text = re.sub(r'[*_]{1,2}([^*_]+)[*_]{1,2}', r'\1', text)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n+', ' ', text).strip()
    return text

def parse_post(path):
    text = path.read_text(encoding='utf-8', errors='replace')
    if not text.startswith('---'):
        return None
    parts = text.split('---', 2)
    if len(parts) < 3:
        return None
    fm_text, body = parts[1], parts[2]
    fm = {}
    for line in fm_text.splitlines():
        if ':' not in line:
            continue
        k, _, v = line.partition(':')
        k = k.strip(); v = v.strip().strip('"').strip("'")
        if v.startswith('[') and v.endswith(']'):
            fm[k] = [x.strip().strip('"').strip("'") for x in v[1:-1].split(',') if x.strip()]
        else:
            fm[k] = v
    stem = path.stem
    parts2 = stem.split('-', 3)
    if len(parts2) < 4:
        return None
    year, month, day, slug = parts2
    cats = fm.get('categories', [])
    category = (cats[0] if isinstance(cats, list) and cats else 'news').strip()
    url = f"/{category}/{year}/{month}/{day}/{slug}/"
    content_clean = strip_markdown(body)[:500]  # first 500 chars for search
    return {
        'title': fm.get('title', '').strip('"').strip("'"),
        'url': url,
        'date': fm.get('date', ''),
        'category': category,
        'tags': fm.get('tags', []),
        'description': fm.get('description', '').strip('"').strip("'"),
        'content': content_clean,
        'image': fm.get('image', ''),
    }

index = []
for path in sorted(POSTS_DIR.glob('*.md'), reverse=True):
    item = parse_post(path)
    if item and item['title']:
        index.append(item)

OUT.write_text(json.dumps(index, ensure_ascii=False, indent=None), encoding='utf-8')
print(f"search-index.json: {len(index)} posts")
