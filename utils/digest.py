"""Shared helpers for the editorial digest scripts.

`create_daily_briefing.py`, `create_weekly_wrapup.py` and
`create_monthly_roundup.py` all need to:

  - walk `_posts/` within a date window,
  - skip auto-generated posts (briefing/digest/milestone/etc),
  - rank surviving posts by signal strength, and
  - build a permalink from `path.stem + frontmatter`.

Three copies of that logic drifted over time. This module centralises
them so the editorial scripts only own the prompt + output shape.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from utils.frontmatter import parse, get_list, get_str

# Auto-generated post categories — exclude from "real news" digests so a
# digest doesn't cite another digest.
AUTO_POST_SLUG_MARKERS: frozenset[str] = frozenset({
    "briefing",
    "roundup",
    "digest",
    "milestone",
    "stats",
    "wrapup",
    "best-of",
})


def build_post_url(path: Path, fm: dict) -> str:
    """Reconstruct a post's site permalink from its filename + categories.

    Returns an empty string when the filename doesn't follow the
    `YYYY-MM-DD-slug.md` convention.
    """
    parts = path.stem.split("-", 3)
    if len(parts) < 4:
        return ""
    y, m, d, slug = parts
    cats = get_list(fm, "categories")
    cat = (cats[0] if cats else "news").strip()
    return f"/{cat}/{y}/{m}/{d}/{slug}/"


def parse_post_date(path: Path) -> date | None:
    """Parse the YYYY-MM-DD prefix from a post filename, or None."""
    try:
        y, m, d = path.stem.split("-")[:3]
        return date(int(y), int(m), int(d))
    except (ValueError, IndexError):
        return None


def base_score(fm: dict) -> int:
    """Signal-only score: breaking + fact-checked + has TL;DR + has image."""
    score = 0
    if str(get_str(fm, "breaking", "")).lower() == "true":
        score += 50
    if str(get_str(fm, "featured", "")).lower() == "true":
        score += 30
    if get_str(fm, "fact_check") == "verified":
        score += 10
    if get_str(fm, "tl_dr"):
        score += 5
    if len(get_str(fm, "description") or "") > 80:
        score += 5
    if get_str(fm, "image"):
        score += 3
    return score


def load_posts_in_window(
    posts_dir: Path,
    start: date,
    end: date,
    skip: frozenset[str] = AUTO_POST_SLUG_MARKERS,
) -> list[tuple[Path, dict, date]]:
    """Walk `posts_dir/*.md`, return (path, frontmatter, date) for posts
    whose filename date falls inside `[start, end]` and that don't match
    any of the auto-generated slug markers in `skip`.

    Posts whose frontmatter fails to parse or whose filename doesn't carry
    a valid date prefix are skipped silently.
    """
    out: list[tuple[Path, dict, date]] = []
    for path in posts_dir.glob("*.md"):
        if any(marker in path.stem for marker in skip):
            continue
        dt = parse_post_date(path)
        if dt is None or not (start <= dt <= end):
            continue
        try:
            fm = parse(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        # Belt-and-braces: also filter via `categories:` frontmatter, in
        # case the slug doesn't contain the marker word.
        cats = {c.lower() for c in get_list(fm, "categories")}
        if cats & set(skip):
            continue
        out.append((path, fm, dt))
    return out


def cited_posts_yaml(items: list[tuple[Path, dict]]) -> str:
    """Render a `cited_posts:` block for the post frontmatter."""
    urls = [u for u in (build_post_url(p, fm) for p, fm in items) if u]
    if not urls:
        return ""
    return "cited_posts:\n" + "".join(f'  - "{u}"\n' for u in urls)


def first_image(items) -> str:
    """Return the first non-empty `image:` from a list of (path, fm[, …])
    tuples — useful for picking a hero image for the digest."""
    for entry in items:
        fm = entry[1]
        img = get_str(fm, "image")
        if img:
            return img
    return ""
