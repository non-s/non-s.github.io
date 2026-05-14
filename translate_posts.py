#!/usr/bin/env python3
"""Translate latest English posts to PT-BR using DeepL or Groq fallback"""
import os, glob, re, logging
from datetime import date, timedelta
import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

DEEPL_KEY = os.getenv("DEEPL_API_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

def translate_deepl(text):
    if not DEEPL_KEY or not text.strip():
        return None
    try:
        r = requests.post(
            "https://api-free.deepl.com/v2/translate",
            data={"auth_key": DEEPL_KEY, "text": text, "target_lang": "PT-BR"},
            timeout=20
        )
        if r.status_code == 200:
            return r.json()["translations"][0]["text"]
    except Exception as e:
        logging.warning(f"DeepL error: {e}")
    return None

def translate_groq(text, title=""):
    if not GROQ_KEY:
        return None
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": "Traduza o texto a seguir para Português do Brasil (PT-BR). Mantenha o tom jornalístico, preserve nomes próprios, siglas e termos técnicos em inglês quando apropriado. Retorne apenas o texto traduzido, sem comentários."},
                    {"role": "user", "content": text[:3000]}
                ],
                "max_tokens": 1500
            },
            timeout=30
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.warning(f"Groq translate error: {e}")
    return None

def translate_text(text):
    result = translate_deepl(text)
    if result:
        return result
    return translate_groq(text) or text  # fallback to original

def main():
    os.makedirs("_posts/pt", exist_ok=True)

    # Get posts from last 2 days not yet translated
    cutoff = date.today() - timedelta(days=2)
    translated = 0

    for path in sorted(glob.glob("_posts/*.md"), reverse=True)[:20]:
        fname = os.path.basename(path)
        pt_path = f"_posts/pt/{fname}"

        if os.path.exists(pt_path):
            continue

        # Check date
        try:
            date_str = "-".join(fname.split("-")[:3])
            post_date = date.fromisoformat(date_str)
            if post_date < cutoff:
                continue
        except Exception:
            continue

        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()

            if not content.startswith("---"):
                continue

            parts = content.split("---", 2)
            if len(parts) < 3:
                continue

            fm_text = parts[1]
            body = parts[2].strip()

            # Extract fields to translate
            title_m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', fm_text, re.MULTILINE)
            desc_m = re.search(r'^description:\s*["\']?(.+?)["\']?\s*$', fm_text, re.MULTILINE)

            original_title = title_m.group(1) if title_m else ""
            original_desc = desc_m.group(1) if desc_m else ""

            # Translate
            logging.info(f"Translating: {fname}")
            pt_title = translate_text(original_title) if original_title else original_title
            pt_desc = translate_text(original_desc) if original_desc else original_desc

            # Translate body (first 2000 chars to save API quota)
            body_to_translate = body[:2000]
            pt_body = translate_text(body_to_translate)
            if len(body) > 2000:
                pt_body += body[2000:]  # append untranslated rest

            # Build PT-BR frontmatter
            new_fm = fm_text
            if original_title:
                new_fm = new_fm.replace(f'title: "{original_title}"', f'title: "{pt_title}"')
                new_fm = new_fm.replace(f"title: '{original_title}'", f"title: '{pt_title}'")
                new_fm = re.sub(rf'^title:\s+{re.escape(original_title)}\s*$', f'title: "{pt_title}"', new_fm, flags=re.MULTILINE)
            if original_desc:
                new_fm = new_fm.replace(f'description: "{original_desc}"', f'description: "{pt_desc}"')
                new_fm = re.sub(rf'^description:\s+{re.escape(original_desc)}\s*$', f'description: "{pt_desc}"', new_fm, flags=re.MULTILINE)

            # Add lang: pt-br
            new_fm = re.sub(r'^lang:.*$', 'lang: "pt-br"', new_fm, flags=re.MULTILINE)
            if 'lang:' not in new_fm:
                new_fm += '\nlang: "pt-br"'

            pt_content = f"---{new_fm}---\n\n{pt_body}\n"

            with open(pt_path, "w", encoding="utf-8") as f:
                f.write(pt_content)

            translated += 1
            logging.info(f"Translated: {pt_path}")

            # Rate limit
            if translated >= 10:
                logging.info("Reached 10 post limit for this run")
                break

        except Exception as e:
            logging.error(f"Error translating {path}: {e}")

    logging.info(f"Done: {translated} post(s) translated")

if __name__ == "__main__":
    main()
