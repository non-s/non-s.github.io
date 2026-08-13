"""Project data paths for Liquid Wire."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_DATA_ROOT = ROOT / "_data"


def data_dir() -> Path:
    """Return the project data directory."""
    return _DATA_ROOT


def ensure_data_dir() -> Path:
    """Create and return the project data directory."""
    _DATA_ROOT.mkdir(parents=True, exist_ok=True)
    return _DATA_ROOT
