"""Subscriber conversion scoring for Wild Brief Shorts.

The growth engine decides whether a Short can earn attention. This module asks
whether that attention can become recurring audience.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from utils.audience_memory import load_audience_memory
from utils.confidence_engine import assess_confidence, combined_confidence

FAN_GROWTH_PATH = Path("_data/fan_growth.json")

ROBOTIC_TITLE_PATTERNS = (
    r"\b\w+\s+uses?\s+(one|a)\s+(tiny\s+)?(trick|body trick)\b",
    r"\b\w+\s+does\s+this\s+for\s+one\s+(reason|hidden reason)\b",
    r"\b\w+\s+has\s+a\s+shortcut\s+most\s+people\s+miss\b",
    r"\bfor one strange reason\b",
    r"\bone visible cue for a reason\b",
)

CATEGORY_CTA = {
    "fungi": "Want more nature that feels like science fiction but is real?",
    "forests": "Want to see how forests quietly run the planet?",
    "ocean": "Want to uncover what is still hidden in the ocean?",
    "oceans": "Want to uncover what is still hidden in the ocean?",
    "volcanoes": "Want more of Earth's forces in action?",
    "weather": "Want to see more extreme weather explained fast?",
    "geology": "Want to understand the planet under your feet?",
    "rivers": "Want to see how moving water reshapes the world?",
    "ecosystems": "Want to understand how nature really works?",
    "conservation": "Want real examples of nature fighting back?",
    "discoveries": "Want fast updates from the edge of science?",
    "rare_phenomena": "Want more natural events that look impossible?",
    "wildlife": "Want more wild behavior explained without the fluff?",
    "birds": "Want one animal signal a day? Follow for the next clue.",
    "farm": "Want one animal signal a day? Follow for tomorrow's farm clue.",
    "cats": "Want one animal signal a day? Follow for the next pet clue.",
    "dogs": "Want one animal signal a day? Follow for the next pet clue.",
    "primates": "Want one animal signal a day? Follow for the next intelligence clue.",
    "insects": "Want more small creatures doing impossible things?",
    "reptiles": "Want more survival tricks from ancient designs?",
}

DEBATE_PROMPTS = {
    "fungi": "Is this closer to a network, a warning system, or something stranger?",
    "forests": "Do forests feel more like places, systems, or living machines?",
    "ocean": "What feels more impossible: the ocean's depth, pressure, or creatures?",
    "oceans": "What feels more impossible: the ocean's depth, pressure, or creatures?",
    "volcanoes": "Is this destruction, construction, or both at once?",
    "weather": "Which is scarier: wind, water, lightning, or heat?",
    "geology": "Does this make Earth feel stable or constantly moving?",
    "rivers": "Are rivers more like roads, tools, or engines?",
    "ecosystems": "Which matters more here: the individual species or the whole system?",
    "conservation": "Is this proof nature recovers, or proof it needs help sooner?",
    "discoveries": "Would you trust this explanation from footage alone?",
    "rare_phenomena": "Which natural phenomenon looks the most fake but is real?",
    "wildlife": "Is this adaptation, instinct, or intelligence?",
    "birds": "Is this adaptation, instinct, or intelligence?",
    "insects": "Is this tiny design more impressive than large-animal survival?",
    "reptiles": "Is this ancient design underrated?",
}

SERIES_BY_CATEGORY = {
    "volcanoes": "Earth Engine",
    "weather": "Earth Engine",
    "geology": "Earth Engine",
    "rivers": "Earth Engine",
    "fungi": "Hidden Network",
    "forests": "Hidden Network",
    "ecosystems": "Hidden Network",
    "rare_phenomena": "Rare Earth",
    "conservation": "Planet Repair",
    "discoveries": "Discovery Brief",
    "birds": "Sky Intelligence",
    "farm": "Farmyard Minds",
    "cats": "Pet Signals",
    "dogs": "Pet Signals",
    "wildlife": "Animal Superpowers",
    "primates": "Animal Intelligence",
    "reptiles": "Survival Tricks",
    "insects": "Small Superpowers",
}


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text or "")


def _category(story: dict) -> str:
    return str(story.get("category") or "").strip().lower()


def contextual_cta(story: dict) -> str:
    category = _category(story)
    return CATEGORY_CTA.get(category, "Follow for one animal signal a day.")


def debate_prompt(story: dict) -> str:
    category = _category(story)
    return DEBATE_PROMPTS.get(category, "What part of this feels most impossible?")


def detect_robotic_title(title: str) -> dict:
    lower = re.sub(r"\s+", " ", str(title or "").lower()).strip()
    hits = [pattern for pattern in ROBOTIC_TITLE_PATTERNS if re.search(pattern, lower)]
    repeated_shape = bool(re.search(r"\b(this|that|one)\b.*\b(this|that|one)\b.*\b(reason|trick|cue)\b", lower))
    risk = min(100, len(hits) * 34 + (22 if repeated_shape else 0))
    return {
        "risk": risk,
        "state": "block" if risk >= 55 else ("revise" if risk >= 25 else "clear"),
        "hits": hits,
    }


def series_identity(story: dict, memory: dict | None = None) -> dict:
    memory = memory or {}
    base = str(story.get("series") or "").strip()
    if not base:
        base = SERIES_BY_CATEGORY.get(_category(story), "Nature Signals")
    counts = memory.get("series_counts") if isinstance(memory.get("series_counts"), dict) else {}
    episode = int(counts.get(base, 0) or 0) + 1
    return {
        "series": base[:60],
        "episode": episode,
        "label": f"{base} #{episode}" if episode > 1 else base,
        "continuity_prompt": f"Next in {base}: compare this with another force of nature.",
    }


def score_subscriber_conversion(story: dict, memory: dict | None = None) -> dict:
    memory = memory or {}
    audience = memory.get("audience_memory") if isinstance(memory.get("audience_memory"), dict) else load_audience_memory()
    title = str(story.get("seo_title") or story.get("title") or "")
    hook = str(story.get("hook") or "")
    cta = str(story.get("cta_prompt") or "")
    pinned = str((story.get("packaging") or {}).get("pinned_comment") or story.get("pinned_comment") or "")
    series = str(story.get("series") or "")
    robotic = detect_robotic_title(title)
    score = 42
    reasons: list[str] = []
    if len(_words(hook)) <= 10 and re.search(r"\b(watch|why|because|before|turns|changes|hidden|real)\b", hook.lower()):
        score += 13
        reasons.append("hook_invites_return")
    cta_lower = cta.lower()
    if cta and (
        ("want" in cta_lower and "more" in cta_lower)
        or "one animal signal" in cta_lower
        or ("follow" in cta_lower and "signal" in cta_lower)
    ):
        score += 14
        reasons.append("identity_cta")
    if pinned and "?" in pinned and not re.search(r"\b(next topic|what should|comment below)\b", pinned.lower()):
        score += 14
        reasons.append("debate_comment")
    if re.search(r"\b(tomorrow|next)\b", pinned.lower()) and "signal" in pinned.lower():
        score += 6
        reasons.append("return_prompt")
    if series:
        score += 10
        reasons.append("series_identity")
    if "#" in series or re.search(r"#\d+", str((story.get("packaging") or {}).get("series_label") or "")):
        score += 7
        reasons.append("episode_continuity")
    score -= robotic["risk"] * 0.35
    category = _category(story)
    fmt = str(story.get("story_format") or "").lower()
    series_base = re.sub(r"\s+#\d+$", "", series).strip()
    weights = audience.get("weights") or {}
    cat_weight = float((memory.get("subscriber_category_weights") or {}).get(category, 1.0))
    cat_weight *= float((weights.get("category_subscribers") or {}).get(category, 1.0))
    if fmt:
        cat_weight *= float((weights.get("format_subscribers") or {}).get(fmt, 1.0))
    if series_base:
        cat_weight *= float((weights.get("series_return") or {}).get(series_base, 1.0))
    score *= max(0.78, min(1.32, cat_weight))
    score = round(max(0, min(100, score)))
    confidence = combined_confidence([
        ((audience.get("category") or {}).get(category) or {}).get("confidence") or {},
        ((audience.get("format") or {}).get(fmt) or {}).get("confidence") or {},
        ((audience.get("series") or {}).get(series_base) or {}).get("confidence") or {},
        assess_confidence("pattern", 1, inferred=1),
    ])
    return {
        "score": score,
        "state": "strong" if score >= 76 else ("usable" if score >= 62 else "weak"),
        "subscriber_probability": min(0.18, round(score / 700, 3)),
        "return_probability": min(0.35, round((score + (8 if series else 0)) / 360, 3)),
        "comment_probability": min(0.28, round((score + (10 if pinned and "?" in pinned else 0)) / 430, 3)),
        "robotic_title": robotic,
        "reasons": tuple(reasons),
        "confidence": confidence,
        "reasoning": confidence.get("reasoning", "Subscriber conversion uses packaging signals while real subscriber history matures."),
    }


def build_fan_growth(markers: list[dict], comments: list[dict] | None = None) -> dict:
    comments = comments or []
    video_rows = []
    category_rates: dict[str, list[float]] = defaultdict(list)
    format_rates: dict[str, list[float]] = defaultdict(list)
    recurring_authors: Counter[str] = Counter()
    coverage = {"with_views": 0, "with_subscribers": 0, "with_comments": 0}
    for raw in comments:
        author = str(raw.get("author") or raw.get("authorDisplayName") or raw.get("author_channel_id") or "").strip()
        if author:
            recurring_authors[author] += 1
    for marker in markers:
        stats = marker.get("analytics") if isinstance(marker.get("analytics"), dict) else {}
        views = float(stats.get("views") or stats.get("viewCount") or marker.get("views") or 0)
        comments_count = float(stats.get("comments") or stats.get("commentCount") or marker.get("comments") or 0)
        subs = float(stats.get("subscribersGained") or marker.get("subscribers_gained") or 0)
        subs_per_1k = round(subs * 1000 / max(views, 1), 3)
        comments_per_1k = round(comments_count * 1000 / max(views, 1), 3)
        if views:
            coverage["with_views"] += 1
        if subs:
            coverage["with_subscribers"] += 1
        if comments_count:
            coverage["with_comments"] += 1
        category = str(marker.get("category") or "").lower()
        fmt = str(marker.get("story_format") or "").lower()
        if category:
            category_rates[category].append(subs_per_1k)
        if fmt:
            format_rates[fmt].append(subs_per_1k)
        video_rows.append({
            "video_id": marker.get("video_id", ""),
            "title": marker.get("title", ""),
            "category": category,
            "story_format": fmt,
            "series": marker.get("series", ""),
            "views": int(views),
            "subscribers_gained": int(subs),
            "subs_per_1k_views": subs_per_1k,
            "comments_per_1k_views": comments_per_1k,
            "subscriber_conversion": marker.get("subscriber_conversion", {}),
        })

    def avg(values: list[float]) -> float:
        return round(sum(values) / len(values), 3) if values else 0.0

    return {
        "coverage": {"total_markers": len(markers), **coverage},
        "videos_ranked_by_subs_per_1k": sorted(video_rows, key=lambda row: row["subs_per_1k_views"], reverse=True)[:20],
        "category_subscriber_rates": {k: avg(v) for k, v in category_rates.items()},
        "format_subscriber_rates": {k: avg(v) for k, v in format_rates.items()},
        "recurring_commenters": [
            {"author": author, "comments": count}
            for author, count in recurring_authors.most_common(20)
            if count >= 2
        ],
        "subscriber_category_weights": {
            k: round(max(0.85, min(1.25, 1 + (avg(v) - 1.5) / 10)), 3)
            for k, v in category_rates.items()
        },
    }


def write_fan_growth(markers: list[dict], comments: list[dict] | None = None,
                     path: Path = FAN_GROWTH_PATH) -> dict:
    payload = build_fan_growth(markers, comments)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload
