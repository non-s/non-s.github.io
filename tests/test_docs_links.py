import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_docs_relative_links_exist():
    for path in [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]:
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            if target.startswith(("http://", "https://", "#")):
                continue
            rel = target.split("#", 1)[0]
            if rel:
                assert (path.parent / rel).exists(), f"{path}: missing link {target}"
