"""Prevent platform-specific legacy code from returning."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}
BLOCKED = (
    "tik" + "tok",
    "f" + "yp",
    "for" + "you",
    "cat" + "tok",
    "dog" + "tok",
    "bird" + "tok",
    "farm" + "tok",
    "@wildbrief" + "_x",
)


def test_repository_is_focused_on_youtube():
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in {".py", ".md", ".html", ".yml", ".yaml", ".json", ".jsonl", ".example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for term in BLOCKED:
            if term in text:
                hits.append(f"{path.relative_to(ROOT)}: {term}")
    assert hits == [], "legacy platform references found:\n" + "\n".join(hits)
