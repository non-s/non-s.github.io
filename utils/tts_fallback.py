"""Optional local TTS fallback hooks.

Edge TTS remains the production path. These helpers only activate when an
operator has installed and configured a local Coqui-compatible command.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone
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
    
    speaker = os.environ.get("COQUI_SPEAKER_WAV")
    if speaker and Path(speaker).exists():
        cmd += ["--speaker_wav", str(speaker)]
        
    if locale and os.environ.get("COQUI_TTS_LOCALE_ARG", "0") == "1":
        cmd += ["--language_idx", locale]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except Exception:
        return None
    if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1024:
        return output_path
    return None


def coqui_healthcheck(
    *,
    synthesize: bool = False,
    output_dir: Path | None = None,
    sample_text: str = "Wild Brief fallback voice check.",
    locale: str = "en",
) -> dict:
    """Return observable state for the optional local Coqui fallback."""
    command = os.environ.get("COQUI_TTS_COMMAND") or shutil.which("tts")
    payload = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "unavailable",
        "command": command or "",
        "model": os.environ.get("COQUI_TTS_MODEL", ""),
        "synthesized": False,
        "reason": "coqui_command_missing",
    }
    if not command:
        return payload
    payload["status"] = "ok"
    payload["reason"] = "command_found"
    if not synthesize:
        return payload
    output_dir = output_dir or Path("_data/tts_health")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "coqui_healthcheck.wav"
    result = synthesize_with_coqui(sample_text, output, locale)
    if result:
        payload.update(
            {
                "synthesized": True,
                "output": str(result),
                "bytes": result.stat().st_size,
                "reason": "synthesis_ok",
            }
        )
        return payload
    payload.update({"status": "failed", "reason": "synthesis_failed"})
    return payload


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
