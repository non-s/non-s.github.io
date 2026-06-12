"""
utils/intro_outro.py — Pre-render and cache the host's intro/outro lines.

Why this exists
---------------
A recognizable channel opens and closes EVERY video the same way.
"Welcome back" — instant recognition. The first 2 seconds of audio
should be the SAME 2 seconds the viewer heard yesterday, with the
SAME voice and intonation.

We pre-render the persona's `intro_line` + `outro_line` once per
voice and cache them under `_data/intro_outro_cache/`. The Shorts
pipeline then concatenates `intro + body + outro` for every Short,
re-using the cached audio.

If the cache is missing, we render fresh. If TTS fails, we return
the body unmodified — intro/outro is enhancement, not a hard requirement.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

INTRO_OUTRO_CACHE = Path(os.environ.get("INTRO_OUTRO_CACHE_DIR", "_data/intro_outro_cache"))
ENABLED = os.environ.get("INTRO_OUTRO_ENABLED", "1") not in ("0", "false", "False")


def _cache_key(line: str, voice: str) -> str:
    return hashlib.sha256(f"{line}|{voice}".encode("utf-8")).hexdigest()[:16]


async def _render_line(line: str, voice: str, output_path: Path, text_to_speech_fn=None) -> bool:
    """Render `line` to `output_path` via edge-tts. Returns True on success."""
    if not line.strip():
        return False
    INTRO_OUTRO_CACHE.mkdir(parents=True, exist_ok=True)
    try:
        if text_to_speech_fn is None:
            # Lazy-import so this module doesn't pull generate_shorts
            # into the test-import graph.
            from generate_shorts import text_to_speech as text_to_speech_fn
        # `rate_override` keeps the intro at a calm baseline regardless
        # of the voice's default rate — recognizable, deliberate.
        await text_to_speech_fn(line, output_path, voice=voice, rate_override="+0%")
        return output_path.exists() and output_path.stat().st_size > 1024
    except Exception as exc:
        log.warning("intro_outro render %r failed: %s", line[:40], exc)
        return False


def get_or_render(line: str, voice: str, text_to_speech_fn=None) -> Path | None:
    """Return the cached MP3 path for (line, voice), rendering if absent."""
    if not ENABLED or not line.strip():
        return None
    key = _cache_key(line, voice)
    path = INTRO_OUTRO_CACHE / f"{key}.mp3"
    if path.exists() and path.stat().st_size > 1024:
        return path
    try:
        success = asyncio.run(_render_line(line, voice, path, text_to_speech_fn))
    except RuntimeError:
        # asyncio.run can't be called from inside another event loop.
        # The caller is on the sync path so this branch shouldn't
        # normally fire; we fail-safe by returning None.
        return None
    if not success:
        return None
    return path


def concat_audio(intro: Path | None, body: Path, outro: Path | None, output_path: Path) -> bool:
    """FFmpeg-concat intro + body + outro into `output_path`.

    Any of `intro` / `outro` can be None (skipped). If both are None,
    we just copy `body` so the call is idempotent. Returns True on success.
    """
    inputs = [p for p in (intro, body, outro) if p is not None and p.exists()]
    if not inputs:
        return False
    if len(inputs) == 1:
        # Just copy the body if there's no intro/outro available.
        try:
            output_path.write_bytes(inputs[0].read_bytes())
            return True
        except Exception:
            return False
    # Build the concat-demuxer list file.
    list_file = output_path.with_suffix(".concat.txt")
    try:
        list_file.write_text(
            "\n".join(f"file '{p.resolve()}'" for p in inputs) + "\n",
            encoding="utf-8",
        )
        # Re-encode (not stream-copy) so bitrate / sample-rate mismatches
        # between cached intro and freshly-rendered body don't break the
        # concat. The audio's tiny so re-encode cost is negligible.
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c:a",
            "libmp3lame",
            "-b:a",
            "192k",
            str(output_path),
        ]
        r = subprocess.run(cmd, capture_output=True, timeout=90)
        return r.returncode == 0 and output_path.exists()
    except Exception as exc:
        log.warning("intro_outro concat failed: %s", exc)
        return False
    finally:
        try:
            list_file.unlink(missing_ok=True)
        except Exception:
            pass


def wrap_with_intro_outro(
    body_audio: Path, voice: str, tmp_dir: Path, text_to_speech_fn=None, outro_line: str | None = None
) -> Path:
    """Convenience: render intro + outro for `voice`, concat into a new MP3.

    Returns the wrapped audio path on success, or `body_audio` unchanged
    on any failure. Caller can treat the return value as the canonical
    "narration with brand" audio.
    """
    if not ENABLED:
        return body_audio
    from utils.host_persona import load as load_persona

    persona = load_persona()
    intro = get_or_render(persona.intro_line, voice, text_to_speech_fn)
    outro = get_or_render((outro_line or persona.outro_line), voice, text_to_speech_fn)
    if intro is None and outro is None:
        return body_audio
    wrapped = tmp_dir / "narration_with_brand.mp3"
    if concat_audio(intro, body_audio, outro, wrapped):
        log.info(
            "  🎬 Wrapped with intro/outro (intro=%s, outro=%s)", "yes" if intro else "no", "yes" if outro else "no"
        )
        return wrapped
    return body_audio
