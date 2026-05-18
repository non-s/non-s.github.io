"""
utils/panic.py — One-line kill switch for every generator + uploader.

If the channel gets flagged, the AI pipeline misbehaves, or you just
want to pause publishing for any reason, set the repo secret
`PANIC_HALT=1` (or commit a file `_data/PANIC_HALT` with any content).

Both checks fire before any expensive work — fetch loop, AI calls,
b-roll downloads, FFmpeg renders, uploads. The check is intentionally
free of dependencies so it always works, even if the rest of the
pipeline is broken.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

PANIC_FLAG_FILE = Path("_data/PANIC_HALT")


def is_halted() -> tuple[bool, str]:
    """Return (halted, reason)."""
    env_val = os.environ.get("PANIC_HALT", "").strip().lower()
    if env_val and env_val not in ("0", "false", "no", ""):
        return True, f"env PANIC_HALT={env_val!r}"
    if PANIC_FLAG_FILE.exists():
        try:
            reason = PANIC_FLAG_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            reason = ""
        return True, f"file {PANIC_FLAG_FILE} present" + (f": {reason}" if reason else "")
    return False, ""


def abort_if_halted(component: str = "pipeline") -> None:
    """Exit non-zero with a clear message when the kill switch is engaged.

    Call this at the very top of any script's main(). Cheap enough to
    run unconditionally — single file stat + env lookup.
    """
    halted, reason = is_halted()
    if not halted:
        return
    log.error("🛑 PANIC HALT engaged for %s — %s", component, reason)
    log.error("   To resume: unset PANIC_HALT env var AND/OR delete %s",
               PANIC_FLAG_FILE)
    sys.exit(75)  # 75 = "temporary failure, try again" in /usr/include/sysexits.h
