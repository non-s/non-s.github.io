"""
utils/captions.py â€” Word-level captions for burned-in Shorts subtitles.

Why captions matter for Shorts
------------------------------
Many YouTube Shorts are viewed muted in the first 2 seconds
(autoplay starts before the user taps unmute). Captions burned into
the frame are the single biggest retention lever for AI-narrated
Shorts: Zebracat's 2025 data shows +18 % watch time when the hook
appears as on-screen text.

Provider order (free-tier first, paid never)
--------------------------------------------
  1. Groq Whisper API     â€” free, 2000 req/day, word-level timestamps,
                            sub-second latency. Needs GROQ_API_KEY,
                            same key the AI fallback chain uses.
  2. faster-whisper local â€” CPU-only on GitHub Actions runner, no
                            external dependency, accurate but ~5-15 s
                            per 50 s audio. Hard fallback.

Output shape
------------
Both providers return a `Caption` list â€” one entry per word, with
absolute start/end seconds. FFmpeg's drawtext filter consumes them
via the SRT writer below.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import math
import os
import re
import subprocess
from pathlib import Path
from typing import Iterable

import requests

from utils.retry import retry_call

log = logging.getLogger(__name__)


@dataclasses.dataclass
class Caption:
    """One spoken word + its position on the audio timeline."""

    word: str
    start: float
    end: float


# â”€â”€ Groq Whisper provider â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#
# Endpoint:  POST https://api.groq.com/openai/v1/audio/transcriptions
# Free tier: 2000 req/day, word-level timestamps supported.
# Docs:      https://console.groq.com/docs/speech-to-text

_GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
_GROQ_MODEL = os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

# A single 429 retry recovers ~80 % of Groq blips without forcing the
# ~10Ã— slower local faster-whisper fallback.
_GROQ_RETRY_DELAY_S = 2.0


def _whisper_language(lang: str | None = None) -> str:
    """Map the active LANGUAGE env to a Whisper-compatible 2-char code.

    Whisper accepts ISO-639-1 codes (`en`, `pt`, `es`, `fr`, â€¦). Our
    sibling-channels convention is `pt-BR` / `es-MX` / `fr-FR` style.
    Unknown locales return "" so the caller drops the hint and lets
    Whisper auto-detect â€” better than poisoning the request with an
    invalid language code.
    """
    locale = (lang or os.environ.get("LANGUAGE", "en") or "en").strip().lower()
    if not locale:
        return "en"
    base = locale.split("-", 1)[0].split("_", 1)[0]
    # The set Whisper definitely supports per its model card. Anything
    # outside this set falls through to auto-detect.
    known = {
        "en",
        "pt",
        "es",
        "fr",
        "de",
        "it",
        "ja",
        "ko",
        "zh",
        "ru",
        "ar",
        "hi",
        "tr",
        "pl",
        "nl",
        "sv",
        "id",
        "vi",
    }
    return base if base in known else ""


def _groq_whisper_request(audio_path: Path, key: str, data: dict) -> requests.Response:
    """One Groq Whisper attempt. Raises on transient (retryable) failure."""
    with audio_path.open("rb") as fh:
        r = requests.post(
            _GROQ_STT_URL,
            headers={"Authorization": f"Bearer {key}"},
            files={"file": (audio_path.name, fh, "audio/mpeg")},
            data=data,
            timeout=60,
        )
    if r.status_code in (429, 500, 502, 503, 504):
        raise requests.exceptions.HTTPError(f"groq whisper transient status {r.status_code}", response=r)
    return r


def transcribe_groq(audio_path: Path, lang: str | None = None) -> list[Caption] | None:
    """Word-level transcribe via Groq Whisper. None on any failure."""
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return None
    if not audio_path.exists():
        return None
    lang = _whisper_language(lang)
    data = {
        "model": _GROQ_MODEL,
        "response_format": "verbose_json",
        "timestamp_granularities[]": "word",
        "temperature": "0",
    }
    if lang:
        data["language"] = lang

    r = retry_call(
        _groq_whisper_request,
        audio_path,
        key,
        data,
        max_attempts=2,
        base_delay=_GROQ_RETRY_DELAY_S,
        jitter=0,
        default=None,
    )
    if r is None:
        return None
    if r.status_code != 200:
        log.debug("groq whisper %d: %s", r.status_code, r.text[:200])
        return None
    try:
        data = r.json()
    except Exception as exc:
        log.debug("groq whisper error: %s", exc)
        return None

    words = data.get("words") or []
    out: list[Caption] = []
    for w in words:
        text = (w.get("word") or "").strip()
        if not text:
            continue
        try:
            start = float(w.get("start", 0))
            end = float(w.get("end", start + 0.3))
        except (TypeError, ValueError):
            continue
        out.append(Caption(word=text, start=start, end=end))
    return out or None


# â”€â”€ faster-whisper local fallback â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#
# Pip: faster-whisper >= 1.0. We DON'T pin it in requirements.txt â€” it
# pulls in CTranslate2 (~200 MB) which would inflate the cold-start of
# every CI run. Instead, install it on-demand inside the workflow that
# wants captions, and import inside this function so unrelated code
# isn't impacted.


def transcribe_faster_whisper(
    audio_path: Path, model_name: str | None = None, lang: str | None = None
) -> list[Caption] | None:
    """Local CPU transcription on the GitHub Actions runner. ~5-15s per 50s audio."""
    if not audio_path.exists():
        return None
    if model_name is None:
        wlang = _whisper_language(lang)
        model_name = "tiny" if wlang and wlang != "en" else "tiny.en"
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception:
        log.info(
            "faster-whisper not installed; captions will fall back to skip. " "`pip install faster-whisper` to enable."
        )
        return None
    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        # Empty `language` lets faster-whisper auto-detect â€” same fallback
        # policy as the Groq path for unknown locales.
        lang = _whisper_language(lang) or None
        segments, _info = model.transcribe(
            str(audio_path),
            beam_size=1,
            word_timestamps=True,
            language=lang,
            condition_on_previous_text=False,
        )
        out: list[Caption] = []
        for seg in segments:
            for w in seg.words or []:
                text = (w.word or "").strip()
                if not text:
                    continue
                try:
                    out.append(Caption(word=text, start=float(w.start), end=float(w.end)))
                except (TypeError, ValueError):
                    continue
        return out or None
    except Exception as exc:
        log.warning("faster-whisper failed: %s", exc)
        return None


# â”€â”€ Unified entry point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def transcribe(audio_path: Path, lang: str | None = None) -> list[Caption] | None:
    """Try Groq first, faster-whisper second. None if both fail."""
    if not audio_path.exists():
        log.warning("captions: audio file missing: %s", audio_path)
        return None
    out = transcribe_groq(audio_path, lang=lang)
    if out:
        log.info("📌 Captions: %d words via Groq Whisper", len(out))
        return out
    wlang = _whisper_language(lang)
    model_name = "tiny" if wlang and wlang != "en" else "tiny.en"
    out = transcribe_faster_whisper(audio_path, model_name=model_name, lang=lang)
    if out:
        log.info("📌 Captions: %d words via faster-whisper", len(out))
        return out
    return None


# ——————————————————————————————————————————————————————————————————————————————
#
# FFmpeg's `subtitles=` filter consumes SRT, but we use ASS because
# Shorts captions need bigger fonts, drop shadows, and per-word
# highlighting â€” all of which ASS does cleanly. The .ass file is
# fed to FFmpeg via `-vf "ass=captions.ass"`.


def _format_ass_time(seconds: float) -> str:
    """`0:00:01.23` for ASS." A small bias clamps tiny negatives."""
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


EMPHASIS_WORDS_BY_LANG = {
    "en": {
        "ancient",
        "atom",
        "aurora",
        "because",
        "breathe",
        "burst",
        "bursts",
        "cell",
        "coral",
        "crystal",
        "deadly",
        "earth",
        "escape",
        "explode",
        "fast",
        "first",
        "forest",
        "fungi",
        "giant",
        "glacier",
        "glow",
        "gravity",
        "hidden",
        "lava",
        "lightning",
        "locked",
        "molecule",
        "moon",
        "mushroom",
        "mycelium",
        "ocean",
        "one",
        "planet",
        "prism",
        "rare",
        "reef",
        "repeating",
        "river",
        "roots",
        "second",
        "secret",
        "shock",
        "signal",
        "slow",
        "space",
        "spin",
        "spins",
        "star",
        "storm",
        "strike",
        "strikes",
        "survive",
        "talk",
        "third",
        "three",
        "tiny",
        "tornado",
        "tree",
        "two",
        "volcano",
        "watch",
        "wave",
        "why",
    },
    "pt": {
        "porque",
        "primeiro",
        "segundo",
        "terceiro",
        "unico",
        "olhe",
        "veja",
        "planeta",
        "terra",
        "oceano",
        "segredo",
        "revelado",
        "incrivel",
        "surpreendente",
        "escondido",
        "misterioso",
        "gigante",
        "minusculo",
        "como",
        "porquê",
        "por que",
        "vida",
        "selvagem",
        "natureza",
        "sobrevive",
    },
    "es": {
        "porque",
        "primero",
        "segundo",
        "tercero",
        "unico",
        "mira",
        "vea",
        "planeta",
        "tierra",
        "oceano",
        "secreto",
        "revelado",
        "increible",
        "sorprendente",
        "oculto",
        "misterioso",
        "gigante",
        "diminuto",
        "como",
        "por que",
        "por qué",
        "vida",
        "salvaje",
        "naturaleza",
        "sobrevive",
    },
}


def _escape_ass(text: str) -> str:
    """Curly braces are ASS override markers; escape them."""
    return (text or "").replace("{", "(").replace("}", ")")


def _caption_text_with_emphasis(text: str) -> str:
    """ASS text with key words punched up for Shorts readability."""
    tokens = re.findall(r"[A-Za-z0-9']+|[^A-Za-z0-9']+", text or "")
    out: list[str] = []
    lang = _whisper_language() or "en"
    emphasis = EMPHASIS_WORDS_BY_LANG.get(lang, EMPHASIS_WORDS_BY_LANG["en"])
    for token in tokens:
        key = token.lower().strip("'")
        safe = _escape_ass(token.upper())
        if key in emphasis or (token.isalpha() and len(token) >= 9):
            out.append(r"{\c&H00FFFFFF&\3c&H00000000&\fscx108\fscy108}" + safe + r"{\rShorts}")
        else:
            out.append(safe)
    return "".join(out)


def group_words_into_phrases(
    words: list[Caption], max_words: int = 4, max_gap_s: float = 0.6, max_duration_s: float = 2.5
) -> list[list[Caption]]:
    """Group word-level captions into chunks of 2-4 words that fit on screen.

    Preserves individual word Captions so the ASS writer can apply Karaoke
    word-by-word timing effects.
    """
    if not words:
        return []
    groups: list[list[Caption]] = []
    buf: list[Caption] = []
    for w in words:
        if buf:
            gap = w.start - buf[-1].end
            phrase_dur = w.end - buf[0].start
            if len(buf) >= max_words or gap > max_gap_s or phrase_dur > max_duration_s:
                groups.append(list(buf))
                buf = []
        buf.append(w)
    if buf:
        groups.append(list(buf))
    return groups


def write_ass(
    captions: list[list[Caption]],
    path: Path,
    video_w: int = 1080,
    video_h: int = 1920,
    font_size: int = 88,
    primary_colour: str = "&H0000F2FF",
    outline_colour: str = "&H00000000",
    shadow_colour: str = "&H00000000",
    margin_v: int = 360,
) -> bool:
    """Write a Shorts-tuned ASS subtitle file with Karaoke word highlighting.

    Default style: bold modern yellow (active), white (inactive), thick black outline,
    dropped shadow, positioned in the upper-middle (margin_v from bottom).
    Returns True on success.
    """
    if not captions:
        return False

    # SecondaryColour sets the inactive word color (White) before Karaoke hits it
    secondary_colour = "&H00FFFFFF"

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {video_w}\nPlayResY: {video_h}\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        # Alignment 2 = bottom-centre, MarginV from bottom.
        f"Style: Shorts,Arial,{font_size},{primary_colour},{secondary_colour},"
        f"{outline_colour},{shadow_colour},1,0,0,0,100,100,0,0,1,6,3,2,"
        f"60,60,{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n"
    )
    lines: list[str] = []
    for phrase_words in captions:
        if not phrase_words:
            continue
        phrase_start = phrase_words[0].start
        phrase_end = phrase_words[-1].end
        start_str = _format_ass_time(phrase_start)
        end_str = _format_ass_time(phrase_end)

        # Build the karaoke text. Each word gets one override block that
        # opens with its (optional) leading-gap \k tag immediately
        # followed by its own \k tag and text — never a separate,
        # standalone gap block. That keeps every `{` paired with its
        # `}` so libass always parses the tag instead of printing it
        # as literal text, while still rendering exactly one visible
        # space between words (attached as a plain-text prefix, not
        # inside the override block).
        text_parts = []
        current_time = phrase_start
        for i, w in enumerate(phrase_words):
            tag = ""
            if w.start > current_time:
                gap_cs = int((w.start - current_time) * 100)
                if gap_cs > 0:
                    tag += f"\\k{gap_cs}"

            word_cs = max(1, int((w.end - w.start) * 100))
            tag += f"\\k{word_cs}"
            tag = "{" + tag + "}"

            word_text = _caption_text_with_emphasis(w.word)
            prefix = " " if i > 0 else ""
            text_parts.append(f"{prefix}{tag}{word_text}")
            current_time = w.end

        text = "".join(text_parts)

        # A tiny pop-in scale feels like CapCut captions
        text = r"{\fad(45,60)\t(0,90,\fscx106\fscy106)}" + text
        lines.append(f"Dialogue: 0,{start_str},{end_str},Shorts,,0,0,0,,{text}")
    try:
        path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
        return True
    except Exception as exc:
        log.warning("write_ass failed: %s", exc)
        return False


def find_leaked_override_codes(ass_path: Path) -> list[str]:
    """Safety-net check: scan a written .ass file's [Events] text for ASS
    override codes (`\\k12`, stray `{`/`}`) that would render as literal
    on-screen text instead of being consumed as formatting. Returns a
    list of problem codes, empty if the caption text is clean.

    This is a belt-and-suspenders check for `write_ass` bugs — the
    generator should never emit unbalanced braces, but a pre-publish
    scan catches any regression before the Short ships.
    """
    try:
        body = ass_path.read_text(encoding="utf-8")
    except Exception:
        return []
    if "[Events]" not in body:
        return []
    events = body.split("[Events]", 1)[1]
    visible = re.sub(r"\{[^}]*\}", "", events)
    issues: list[str] = []
    if re.search(r"\\[kK]\d", visible):
        issues.append("leaked_karaoke_tag")
    if "{" in visible or "}" in visible:
        issues.append("unbalanced_ass_braces")
    return issues
