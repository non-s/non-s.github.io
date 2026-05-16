#!/usr/bin/env python3
"""Translate latest English posts to PT-BR via Mistral."""
from __future__ import annotations

import logging
import os
import re
import time
from datetime import date, timedelta
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

POSTS_DIR     = Path("_posts")
PT_DIR        = POSTS_DIR / "pt"
LOOKBACK_DAYS = 3
MAX_PER_RUN   = 10

MISTRAL_KEY  = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

_TRANSLATE_SYS = (
    "Traduza o texto a seguir para Português do Brasil (PT-BR). "
    "Mantenha o tom jornalístico, preserve nomes próprios, siglas e termos "
    "técnicos em inglês quando apropriado. Retorne apenas o texto traduzido, "
    "sem comentários adicionais."
)


def _translate_mistral(text: str) -> str | None:
    if not MISTRAL_KEY or not text.strip():
        return None
    try:
        r = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {MISTRAL_KEY}", "Content-Type": "application/json"},
            json={
                "model": MISTRAL_MODEL,
                "messages": [
                    {"role": "system", "content": _TRANSLATE_SYS},
                    {"role": "user",   "content": text},
                ],
                "temperature": 0.3,
                "max_tokens": 4000,
            },
            timeout=45,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        log.warning("Mistral %d: %s", r.status_code, r.text[:100])
    except Exception as e:
        log.warning("Mistral translate error: %s", e)
    return None


def translate_text(text: str) -> str:
    """Translate via Mistral, fall back to original text on failure (never loses content)."""
    result = _translate_mistral(text)
    return result if result else text


def _replace_fm_field(fm_text: str, key: str, original: str, translated: str) -> str:
    """Safely replace a frontmatter value, handling quoted and unquoted forms."""
    if not original or original == translated:
        return fm_text
    escaped = re.escape(original)
    # Try quoted forms first
    fm_text = re.sub(
        rf'^({key}:\s*["\'])({escaped})(["\'])\s*$',
        lambda m: f'{m.group(1)}{translated}{m.group(3)}',
        fm_text, flags=re.MULTILINE,
    )
    # Then unquoted
    fm_text = re.sub(
        rf'^({key}:\s*)({escaped})\s*$',
        lambda m: f'{m.group(1)}"{translated}"',
        fm_text, flags=re.MULTILINE,
    )
    return fm_text


def main() -> None:
    PT_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = date.today() - timedelta(days=LOOKBACK_DAYS)
    translated = 0

    for post_path in sorted(POSTS_DIR.glob("*.md"), reverse=True)[:50]:
        if translated >= MAX_PER_RUN:
            log.info("Reached %d post limit for this run", MAX_PER_RUN)
            break

        fname = post_path.name
        pt_path = PT_DIR / fname

        if pt_path.exists():
            continue

        try:
            date_str = "-".join(fname.split("-")[:3])
            post_date = date.fromisoformat(date_str)
            if post_date < cutoff:
                continue
        except Exception:
            continue

        try:
            content = post_path.read_text(encoding="utf-8", errors="replace")
            if not content.startswith("---"):
                continue
            parts = content.split("---", 2)
            if len(parts) < 3:
                continue

            fm_text = parts[1]
            body    = parts[2].strip()

            # Extract fields to translate
            title_m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', fm_text, re.MULTILINE)
            desc_m  = re.search(r'^description:\s*["\']?(.+?)["\']?\s*$', fm_text, re.MULTILINE)
            original_title = title_m.group(1).strip() if title_m else ""
            original_desc  = desc_m.group(1).strip()  if desc_m  else ""

            log.info("Translating: %s", fname)

            pt_title = translate_text(original_title) if original_title else original_title
            pt_desc  = translate_text(original_desc)  if original_desc  else original_desc

            # Translate FULL body (no truncation)
            pt_body = translate_text(body) if body else body

            # Build PT-BR frontmatter
            new_fm = fm_text
            new_fm = _replace_fm_field(new_fm, "title",       original_title, pt_title)
            new_fm = _replace_fm_field(new_fm, "description", original_desc,  pt_desc)

            # Set lang field
            new_fm = re.sub(r'^lang:.*$', 'lang: "pt-br"', new_fm, flags=re.MULTILINE)
            if "lang:" not in new_fm:
                new_fm += '\nlang: "pt-br"'

            # Force a unique /pt/ permalink so Jekyll doesn't overwrite the
            # English post's URL. Without this, _posts/pt/...md collides
            # with _posts/...md at the same /:categories/:year/:month/:day/
            # slot and only one wins.
            cat_m = re.search(r'^categories:\s*\[([^\]]+)\]', new_fm, re.MULTILINE)
            cat = "news"
            if cat_m:
                first = cat_m.group(1).split(",")[0].strip().strip('"').strip("'")
                if first:
                    cat = first
            year, month, day = fname.split("-")[:3]
            slug = fname.removesuffix(".md").split("-", 3)[3] if fname.count("-") >= 3 else fname.removesuffix(".md")
            pt_permalink = f"/pt/{cat}/{year}/{month}/{day}/{slug}/"
            new_fm = re.sub(r'^permalink:.*$', f'permalink: "{pt_permalink}"', new_fm, flags=re.MULTILINE)
            if "permalink:" not in new_fm:
                new_fm = new_fm.rstrip("\n") + f'\npermalink: "{pt_permalink}"\n'

            # Tag the translation so consumers (sitemap, Bluesky) can filter.
            if "translated_from:" not in new_fm:
                new_fm = new_fm.rstrip("\n") + f'\ntranslated_from: "{fname}"\n'

            # Guarantee the closing --- starts on its own line, otherwise
            # Jekyll's YAML parser dies on "value"--- and the post never
            # ships. (This is what blew up the pages-build-deployment for
            # the entire PT batch on 2026-05-15.)
            if not new_fm.endswith("\n"):
                new_fm += "\n"

            pt_content = f"---{new_fm}---\n\n{pt_body}\n"
            pt_path.write_text(pt_content, encoding="utf-8")

            translated += 1
            log.info("Translated → %s", pt_path)

            time.sleep(1)   # polite to APIs

        except Exception as e:
            log.error("Error translating %s: %s", fname, e)

    log.info("Done: %d post(s) translated", translated)


if __name__ == "__main__":
    main()
