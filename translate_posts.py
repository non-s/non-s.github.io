#!/usr/bin/env python3
"""Translate latest English posts to PT-BR via DeepL → Groq → Gemini fallback chain."""
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

DEEPL_KEY  = os.getenv("DEEPL_API_KEY", "")
GROQ_KEY   = os.getenv("GROQ_API_KEY", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")

_TRANSLATE_SYS = (
    "Traduza o texto a seguir para Português do Brasil (PT-BR). "
    "Mantenha o tom jornalístico, preserve nomes próprios, siglas e termos "
    "técnicos em inglês quando apropriado. Retorne apenas o texto traduzido, "
    "sem comentários adicionais."
)


def _translate_deepl(text: str) -> str | None:
    if not DEEPL_KEY or not text.strip():
        return None
    try:
        r = requests.post(
            "https://api-free.deepl.com/v2/translate",
            data={"auth_key": DEEPL_KEY, "text": text, "target_lang": "PT-BR"},
            timeout=30,
        )
        if r.status_code == 200:
            return r.json()["translations"][0]["text"]
        log.warning("DeepL %d: %s", r.status_code, r.text[:100])
    except Exception as e:
        log.warning("DeepL error: %s", e)
    return None


def _translate_groq(text: str) -> str | None:
    if not GROQ_KEY:
        return None
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": _TRANSLATE_SYS},
                    {"role": "user",   "content": text},
                ],
                "max_tokens": 4000,
            },
            timeout=45,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        log.warning("Groq %d: %s", r.status_code, r.text[:100])
    except Exception as e:
        log.warning("Groq translate error: %s", e)
    return None


def _translate_gemini(text: str) -> str | None:
    if not GEMINI_KEY:
        return None
    try:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
        )
        r = requests.post(
            url,
            json={
                "contents": [{"parts": [{"text": f"{_TRANSLATE_SYS}\n\n{text}"}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 4000},
            },
            timeout=45,
        )
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        log.warning("Gemini %d: %s", r.status_code, r.text[:100])
    except Exception as e:
        log.warning("Gemini translate error: %s", e)
    return None


def translate_text(text: str) -> str:
    """DeepL → Groq → Gemini → original (never loses content)."""
    for fn in (_translate_deepl, _translate_groq, _translate_gemini):
        result = fn(text)
        if result:
            return result
    return text


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
