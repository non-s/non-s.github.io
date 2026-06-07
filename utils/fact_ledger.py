"""Editorial memory for repeated animal facts and angles."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone


_STOPWORDS = {
    "animal", "animals", "wildlife", "shorts", "facts", "fact", "why", "this",
    "that", "they", "their", "them", "with", "from", "just", "like", "here",
    "real", "reason", "secret", "really", "because", "what", "when", "your",
    "it's", "isnt", "isn't", "dont", "don't", "one", "first", "watch",
    "show", "shows", "reveal", "reveals", "visible", "cue", "clip", "short",
    "movement", "payoff", "viewer", "viewers", "miss", "most", "in", "on",
    "of", "at", "to", "for", "by", "before", "after",
    "cat", "cats", "dog", "dogs", "seal", "seals", "paw", "paws",
    "landing", "ear", "ears", "turn", "nose", "check", "tail", "pause",
    "grooming", "reset", "whisker", "whiskers", "map", "white",
    "camouflage", "body", "freeze",
}


def _tokens(text: str) -> list[str]:
    return [
        token.lower().strip("'")
        for token in re.findall(r"[A-Za-z][A-Za-z']+", text or "")
        if token.lower().strip("'") not in _STOPWORDS
    ]


def angle_key(story: dict) -> str:
    """Return a stable, coarse key for editorial de-duplication."""
    category = str(story.get("category") or "unknown").lower()
    text = " ".join(str(story.get(key) or "") for key in ("seo_title", "title", "hook", "script"))
    tokens = _tokens(text)
    counts = Counter(tokens)
    strongest = [token for token, _ in counts.most_common(4)]
    return f"{category}:" + "-".join(strongest or ["general"])


def build_fact_ledger(stories: list[dict]) -> dict:
    """Summarise repeated facts, titles and angles across the pending queue."""
    groups: dict[str, list[dict]] = defaultdict(list)
    repeated_phrases: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    for story in stories:
        if story.get("consumed"):
            continue
        key = angle_key(story)
        groups[key].append(story)
        category_counts[str(story.get("category") or "unknown").lower()] += 1
        text = f"{story.get('seo_title', '')} {story.get('hook', '')}".lower()
        for phrase in (
            "not just happiness", "not just happy", "not just playing",
            "not just fun", "real reason", "secret", "purr", "knead",
        ):
            if phrase in text:
                repeated_phrases[phrase] += 1
    clusters = []
    for key, sample in sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True):
        if len(sample) < 2:
            continue
        clusters.append({
            "angle_key": key,
            "count": len(sample),
            "category": str(sample[0].get("category") or "unknown"),
            "titles": [
                str(item.get("seo_title") or item.get("title") or "")[:120]
                for item in sample[:8]
            ],
        })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pending_stories": sum(1 for story in stories if not story.get("consumed")),
        "category_counts": dict(category_counts.most_common()),
        "repeated_phrases": dict(repeated_phrases.most_common(12)),
        "duplicate_clusters": clusters[:30],
        "risk_score": min(100, sum(item["count"] - 1 for item in clusters) * 4),
    }


def duplicate_angle_ids(stories: list[dict]) -> set[str]:
    """Return queue ids that belong to non-primary duplicate clusters."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for story in stories:
        if not story.get("consumed"):
            groups[angle_key(story)].append(story)
    ids: set[str] = set()
    for sample in groups.values():
        for story in sample[1:]:
            story_id = str(story.get("id") or "")
            if story_id:
                ids.add(story_id)
    return ids
