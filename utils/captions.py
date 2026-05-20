"""
utils/captions.py — Word-level captions for burned-in Shorts subtitles.

Why captions matter for Shorts
------------------------------
~80 % of TikTok Shorts are viewed muted in the first 2 seconds
(autoplay starts before the user taps unmute). Captions burned into
the frame are the single biggest retention lever for AI-narrated
Shorts: Zebracat's 2025 data shows +18 % watch time when the hook
appears as on-screen text.

Provider order (free-tier first, paid never)
--------------------------------------------
  1. Groq Whisper API     — free, 2000 req/day, word-level timestamps,
                            sub-second latency. Needs GROQ_API_KEY,
                            same key the AI fallback chain uses.
  2. faster-whisper local — CPU-only on GitHub Actions runner, no
                            external dependency, accurate but ~5-15 s
                            per 50 s audio. Hard fallback.

Output shape
------------
Both providers return a `Caption` list — one entry per word, with
absolute start/end seconds. FFmpeg's drawtext filter consumes them
via the SRT writer below.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import math
import os
import subprocess
from pathlib import Path
from typing import Iterable

import requests

log = logging.getLogger(__name__)


@dataclasses.dataclass
class Caption:
    """One spoken word + its position on the audio timeline."""
    word: str
    start: float
    end: float


# ── Groq Whisper provider ─────────────────────────────────────────
#
# Endpoint:  POST https://api.groq.com/openai/v1/audio/transcriptions
# Free tier: 2000 req/day, word-level timestamps supported.
# Docs:      https://console.groq.com/docs/speech-to-text

_GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
_GROQ_MODEL   = os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

# A single 429 retry recovers ~80 % of Groq blips without forcing the
# ~10× slower local faster-whisper fallback.
_GROQ_RETRY_DELAY_S = 2.0


def _whisper_language() -> str:
    """Map the active LANGUAGE env to a Whisper-compatible 2-char code.

    Whisper accepts ISO-639-1 codes (`en`, `pt`, `es`, `fr`, …). Our
    sibling-channels convention is `pt-BR` / `es-MX` / `fr-FR` style.
    Unknown locales return "" so the caller drops the hint and lets
    Whisper auto-detect — better than poisoning the request with an
    invalid language code.
    """
    locale = (os.environ.get("LANGUAGE", "en") or "en").strip().lower()
    if not locale:
        return "en"
    base = locale.split("-", 1)[0].split("_", 1)[0]
    # The set Whisper definitely supports per its model card. Anything
    # outside this set falls through to auto-detect.
    known = {
        "en", "pt", "es", "fr", "de", "it", "ja", "ko", "zh",
        "ru", "ar", "hi", "tr", "pl", "nl", "sv", "id", "vi",
    }
    return base if base in known else ""


def transcribe_groq(audio_path: Path) -> list[Caption] | None:
    """Word-level transcribe via Groq Whisper. None on any failure."""
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return None
    if not audio_path.exists():
        return None
    lang = _whisper_language()
    for attempt in range(2):
        try:
            with audio_path.open("rb") as fh:
                data = {
                    "model": _GROQ_MODEL,
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": "word",
                    "temperature": "0",
                }
                if lang:
                    data["language"] = lang
                r = requests.post(
                    _GROQ_STT_URL,
                    headers={"Authorization": f"Bearer {key}"},
                    files={"file": (audio_path.name, fh, "audio/mpeg")},
                    data=data,
                    timeout=60,
                )
        except (requests.ConnectionError, requests.Timeout) as exc:
            if attempt == 0:
                log.debug("groq whisper transient %s; retrying", type(exc).__name__)
                import time as _time
                _time.sleep(_GROQ_RETRY_DELAY_S)
                continue
            return None
        if r.status_code == 200:
            break
        if r.status_code in (429, 500, 502, 503, 504) and attempt == 0:
            log.debug("groq whisper %d; retrying once", r.status_code)
            import time as _time
            _time.sleep(_GROQ_RETRY_DELAY_S)
            continue
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


# ── faster-whisper local fallback ─────────────────────────────────
#
# Pip: faster-whisper >= 1.0. We DON'T pin it in requirements.txt — it
# pulls in CTranslate2 (~200 MB) which would inflate the cold-start of
# every CI run. Instead, install it on-demand inside the workflow that
# wants captions, and import inside this function so unrelated code
# isn't impacted.

def transcribe_faster_whisper(audio_path: Path,
                              model_name: str = "tiny.en") -> list[Caption] | None:
    """Local CPU transcription on the GitHub Actions runner. ~5-15s per 50s audio."""
    if not audio_path.exists():
        return None
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception:
        log.info(
            "faster-whisper not installed; captions will fall back to skip. "
            "`pip install faster-whisper` to enable."
        )
        return None
    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        # Empty `language` lets faster-whisper auto-detect — same fallback
        # policy as the Groq path for unknown locales.
        lang = _whisper_language() or None
        segments, _info = model.transcribe(
            str(audio_path),
            beam_size=1,
            word_timestamps=True,
            language=lang,
            condition_on_previous_text=False,
        )
        out: list[Caption] = []
        for seg in segments:
            for w in (seg.words or []):
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


# ── Unified entry point ───────────────────────────────────────────

def transcribe(audio_path: Path) -> list[Caption] | None:
    """Try Groq first, faster-whisper second. None if both fail."""
    if not audio_path.exists():
        log.warning("captions: audio file missing: %s", audio_path)
        return None
    out = transcribe_groq(audio_path)
    if out:
        log.info("📝 Captions: %d words via Groq Whisper", len(out))
        return out
    out = transcribe_faster_whisper(audio_path)
    if out:
        log.info("📝 Captions: %d words via faster-whisper", len(out))
        return out
    return None


# ── ASS / SRT writers ─────────────────────────────────────────────
#
# FFmpeg's `subtitles=` filter consumes SRT, but we use ASS because
# Shorts captions need bigger fonts, drop shadows, and per-word
# highlighting — all of which ASS does cleanly. The .ass file is
# fed to FFmpeg via `-vf "ass=captions.ass"`.

def _format_ass_time(seconds: float) -> str:
    """`0:00:01.23` for ASS." A small bias clamps tiny negatives."""
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _escape_ass(text: str) -> str:
    """Curly braces are ASS override markers; escape them."""
    return (text or "").replace("{", "(").replace("}", ")")


def group_words_into_phrases(words: list[Caption],
                              max_words: int = 4,
                              max_gap_s: float = 0.6,
                              max_duration_s: float = 2.5) -> list[Caption]:
    """Group word-level captions into 2-4 word phrases that fit on screen.

    Word-level karaoke-style captions are jittery on a Short. Grouping
    into 2-4 word chunks reads cleanly while preserving timing. We
    break on long pauses (`max_gap_s`) so phrases don't span thoughts.
    """
    if not words:
        return []
    groups: list[Caption] = []
    buf: list[Caption] = []
    for w in words:
        if buf:
            gap = w.start - buf[-1].end
            phrase_dur = w.end - buf[0].start
            if (len(buf) >= max_words
                    or gap > max_gap_s
                    or phrase_dur > max_duration_s):
                groups.append(Caption(
                    word=" ".join(b.word.strip() for b in buf),
                    start=buf[0].start,
                    end=buf[-1].end,
                ))
                buf = []
        buf.append(w)
    if buf:
        groups.append(Caption(
            word=" ".join(b.word.strip() for b in buf),
            start=buf[0].start,
            end=buf[-1].end,
        ))
    return groups


def write_ass(captions: list[Caption], path: Path,
              video_w: int = 1080, video_h: int = 1920,
              font_size: int = 84,
              primary_colour: str = "&H00FFFFFF",
              outline_colour: str = "&H00000000",
              shadow_colour: str = "&H00000000",
              margin_v: int = 220) -> bool:
    """Write a Shorts-tuned ASS subtitle file.

    Default style: bold white, thick black outline, dropped shadow,
    positioned at the lower-third (margin_v from bottom). Tweak via
    args if you want a different look. Returns True on success.
    """
    if not captions:
        return False
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
        f"Style: Shorts,Arial,{font_size},{primary_colour},&H000000FF,"
        f"{outline_colour},{shadow_colour},1,0,0,0,100,100,0,0,1,6,3,2,"
        f"60,60,{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n"
    )
    lines: list[str] = []
    for cap in captions:
        start = _format_ass_time(cap.start)
        end = _format_ass_time(cap.end)
        text = _escape_ass(cap.word.upper())
        lines.append(f"Dialogue: 0,{start},{end},Shorts,,0,0,0,,{text}")
    try:
        path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
        return True
    except Exception as exc:
        log.warning("write_ass failed: %s", exc)
        return False
