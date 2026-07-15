"""Shared pytest setup.

The src/ package's __init__.py eagerly imports every submodule (voice
generation, subtitles, music mixing, video editing), which pulls in heavy
optional dependencies (moviepy, openai-whisper, edge-tts, ...) that the
Quality workflow intentionally does not install just to run these unit
tests. To avoid that, we import the modules under test the same way
main.py already does: by inserting src/ directly onto sys.path and
importing them as top-level modules, bypassing src/__init__.py entirely.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

for path in (str(ROOT_DIR), str(SRC_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)
