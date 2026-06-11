"""Optional local TTS fallback hooks.

Edge TTS remains the production path. These helpers only activate when an
operator has installed and configured a local Coqui-compatible command.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable


def synthesize_with_coqui(text: str, output_path: Path, locale: str = "en") -> Path | None:
    """Try a local Coqui CLI command. Return None when unavailable."""
    command = os.environ.get("COQUI_TTS_COMMAND") or shutil.which("tts")
    if not command:
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model = os.environ.get("COQUI_TTS_MODEL", "")
    cmd = [command, "--text", text, "--out_path", str(output_path)]
    if model:
        cmd += ["--model_name", model]
    if locale and os.environ.get("COQUI_TTS_LOCALE_ARG", "0") == "1":
        cmd += ["--language_idx", locale]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except Exception:
        return None
    if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1024:
        return output_path
    return None


def synthesize_with_existing_or_fallback(
    primary: Callable[[str, Path], Path | None],
    text: str,
    output_path: Path,
    locale: str = "en",
) -> Path:
    """Run the existing TTS callable first, then optional Coqui fallback."""
    try:
        result = primary(text, output_path)
        if result and Path(result).exists():
            return Path(result)
    except Exception:
        pass
    fallback = synthesize_with_coqui(text, output_path, locale)
    if fallback:
        return fallback
    raise RuntimeError("TTS primary path failed and optional Coqui fallback is unavailable")
