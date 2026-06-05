"""
utils/channel_memory.py — Recurring callbacks to past coverage.

Why this exists
---------------
A real channel host says things like "last week I told you about X"
or "as I called out three days ago". That continuity is what makes
viewers feel like they're watching a serial commentator, not a wire-
service reader. Without it, every Short reads as an island.

This module:

  1. After every successful Short, `remember()` appends the story's
     core facts (slug, hook, topic, sources, geo) to a JSONL ledger.
  2. Before each new story is enriched, fetch_animals.py calls
     `find_callback_candidates()` to surface 0-2 recent past stories
     that share entities / topics with the new one.
  3. The candidates are injected into the AI prompt so the LLM can
     OPTIONALLY weave a callback line in: "I covered octopus camouflage
     two weeks ago — and here's the detail I missed."

Conservative by design: most stories DON'T get a callback (it'd feel
forced). We only mention past coverage when there's a clear entity
overlap with high-relevance prior coverage, and the prompt lets the
LLM skip the callback if it doesn't fit naturally.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

MEMORY_LOG = Path(os.environ.get("CHANNEL_MEMORY_LOG",
                                   "_data/channel_memory.jsonl"))
# How far back to look for callback candidates.
LOOKBACK_DAYS = int(os.environ.get("CHANNEL_MEMORY_LOOKBACK_DAYS", "30"))
# Max entries we keep on disk. Older ones get pruned.
MAX_ENTRIES = int(os.environ.get("CHANNEL_MEMORY_MAX_ENTRIES", "500"))

_ANGLE_STOPWORDS = {
    "animal", "animals", "brief", "secret", "secrets", "facts", "fact",
    "here", "really", "this", "that", "their", "your", "with", "from",
    "why", "how", "what", "when", "they", "them", "because",
}


def remember(story: dict) -> None:
    """Append a story's core facts to the memory ledger. Best-effort."""
    entry = {
        "ts":          time.time(),
        "iso":         datetime.now(timezone.utc).isoformat(),
        "slug":        story.get("slug") or story.get("id"),
        "title":       (story.get("seo_title") or story.get("title", ""))[:200],
        "hook":        (story.get("hook") or "")[:240],
        "category":    story.get("category", ""),
        "geo":         story.get("geo_hashtag", ""),
        "topic":       story.get("topic_hashtag", ""),
        "subject":     story.get("editorial", {}).get("subject", ""),
        "angle_key":   angle_key(story),
        "series":      story.get("series", ""),
        "source":      story.get("source", ""),
        "language":    story.get("language", "en"),
        # Entities = the AI-picked search tags from yt_tags. The first
        # three are the entity-driven ones per the fetch_animals prompt
        # contract.
        "entities":    [t for t in (story.get("yt_tags") or [])[:3]
                         if isinstance(t, str)],
    }
    if not entry["slug"]:
        return
    try:
        MEMORY_LOG.parent.mkdir(parents=True, exist_ok=True)
        with MEMORY_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        log.debug("channel_memory remember failed: %s", exc)


def _iter_recent(path: Path = MEMORY_LOG, days: int = LOOKBACK_DAYS):
    if not path.exists():
        return
    cutoff = time.time() - days * 86400
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (e.get("ts") or 0) < cutoff:
                continue
            yield e
    except Exception:
        return


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-']{2,}")


def _tokenise(text: str) -> set[str]:
    """Lowercase non-stopword tokens, 3+ chars."""
    return {w.lower() for w in _WORD_RE.findall(text)
             if w.lower() not in {"the", "and", "for", "with", "from",
                                    "that", "this", "are", "was", "were",
                                    "but", "not", "you", "your", "have",
                                    "has", "had", "they", "them", "into"}}


def angle_key(story: dict) -> str:
    """Stable coarse angle key: subject + strongest non-generic terms."""
    title_text = " ".join(str(story.get(k) or "") for k in (
        "seo_title", "title", "hook", "thumbnail_text",
    ))
    tokens = []
    for token in _WORD_RE.findall(title_text):
        token = token.lower()
        if token in _ANGLE_STOPWORDS or len(token) < 4 or token in tokens:
            continue
        tokens.append(token)
    subject = str((story.get("editorial") or {}).get("subject") or story.get("topic_hashtag") or "").lower()
    base = [subject] if subject else []
    for token in tokens:
        if token not in base:
            base.append(token)
        if len(base) >= 4:
            break
    return "-".join(base)


def find_callback_candidates(story: dict, max_candidates: int = 2,
                              path: Path | None = None,
                              days: int = LOOKBACK_DAYS) -> list[dict]:
    """Return up to N past stories that share entities/topics with `story`.

    Ranking: shared entities (exact match) are worth 3 points each;
    shared topic_hashtag = 2 points; shared geo = 1 point; token
    overlap in title/hook = 1 point each (capped at 3). Top scorers
    return up to `max_candidates`. Empty list when nothing meaningful
    overlaps — most stories will get an empty list, which is the right
    answer (no forced callbacks).
    """
    if max_candidates <= 0:
        return []
    target_entities = {e.lower() for e in (story.get("yt_tags") or [])[:5]
                        if isinstance(e, str)}
    target_topic = (story.get("topic_hashtag") or "").lower()
    target_geo = (story.get("geo_hashtag") or "").lower()
    title_text = f"{story.get('seo_title','')} {story.get('hook','')}"
    target_tokens = _tokenise(title_text)
    target_slug = story.get("slug") or story.get("id")

    scored: list[tuple[int, dict]] = []
    for past in _iter_recent(path or MEMORY_LOG, days):
        if past.get("slug") == target_slug:
            continue
        score = 0
        # Strongest signal: shared named entities.
        past_entities = {e.lower() for e in (past.get("entities") or [])}
        score += 3 * len(target_entities & past_entities)
        if target_topic and past.get("topic", "").lower() == target_topic:
            score += 2
        if target_geo and past.get("geo", "").lower() == target_geo:
            score += 1
        past_tokens = _tokenise(f"{past.get('title','')} {past.get('hook','')}")
        token_overlap = len(target_tokens & past_tokens)
        score += min(token_overlap, 3)
        # Require at least one ENTITY match or strong token overlap.
        # Without that the callback would feel forced.
        has_entity_match = bool(target_entities & past_entities)
        if score >= 4 and (has_entity_match or token_overlap >= 4):
            scored.append((score, past))

    scored.sort(key=lambda t: (-t[0], -t[1].get("ts", 0)))
    return [s[1] for s in scored[:max_candidates]]


def recent_angle_repeat(story: dict, days: int = 10,
                        path: Path | None = None) -> bool:
    """Return True when the same coarse angle appeared recently."""
    key = angle_key(story)
    if not key:
        return False
    for past in _iter_recent(path or MEMORY_LOG, days=days):
        if past.get("slug") == (story.get("slug") or story.get("id")):
            continue
        if past.get("angle_key") == key:
            return True
    return False


def callback_prompt_block(candidates: list[dict]) -> str:
    """Render the candidates into the AI prompt's instruction block.

    Returns an empty string when there are no candidates — caller
    appends only when non-empty.
    """
    if not candidates:
        return ""
    lines = [
        "RECENT COVERAGE YOU (the host) ALREADY BROADCAST:",
    ]
    for c in candidates[:2]:
        when = (c.get("iso", "")[:10] or "recently")
        lines.append(
            f'- On {when}: "{c.get("hook", "").strip()}"'
        )
    lines.append(
        "If this new story is a clear continuation, you MAY weave in "
        "ONE short callback line ('I called this out last week — here's "
        "how it played out:' or similar) — but ONLY if it fits "
        "naturally. Forced callbacks read as filler. When in doubt, "
        "skip the callback."
    )
    return "\n".join(lines)


def prune_older_than(days: int = 60, path: Path | None = None) -> int:
    """Drop entries older than `days`. Returns kept count."""
    p = path or MEMORY_LOG
    if not p.exists():
        return 0
    cutoff = time.time() - days * 86400
    kept: list[dict] = []
    for e in _iter_recent(p, days=days):
        if (e.get("ts") or 0) >= cutoff:
            kept.append(e)
    # Keep at most MAX_ENTRIES newest.
    kept.sort(key=lambda e: e.get("ts", 0), reverse=True)
    kept = kept[:MAX_ENTRIES]
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for e in kept:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    tmp.replace(p)
    return len(kept)
