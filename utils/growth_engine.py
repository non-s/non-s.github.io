"""Autonomous growth scoring for Wild Brief.

Everything here is deterministic, local and free. It turns a candidate story
into three decisions:

* is the topic worth producing?
* is the script likely to retain/replay?
* which title, thumbnail text and hook package should ship?
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from utils.nature_strategy import NATURE_TOPICS

MEMORY_PATH = Path("_data/format_memory.json")

PRIORITY_CATEGORIES = {
    "fungi", "forests", "ocean", "volcanoes", "weather", "geology",
    "ecosystems", "rare_phenomena", "conservation", "discoveries",
    "wildlife", "reptiles", "insects", "birds",
}

VISUAL_TERMS = {
    "lava", "glow", "storm", "lightning", "tornado", "aurora", "waves",
    "reef", "coral", "mushroom", "roots", "canopy", "ice", "crystal",
    "cave", "river", "waterfall", "volcano", "cloud", "ash", "glacier",
    "eyes", "tail", "wings", "paws", "camouflage", "color", "colour",
    "wing", "feet", "beak", "fin", "fins", "pupil", "pupils", "movement",
    "mushrooms", "thread", "threads", "cap", "caps", "nest", "soil",
    "predator", "predators", "gesture", "gestures",
}

EMOTIONAL_TERMS = {
    "rare", "tiny", "giant", "ancient", "hidden", "deadly", "strange",
    "weird", "survive", "rescue", "protect", "vanish", "explode",
}

COMMENT_TERMS = {
    "why", "how", "which", "what", "next", "guess", "spot", "notice",
    "comment", "ever", "would",
}

ACTION_TERMS = {
    "erupt", "glow", "move", "grow", "talk", "signal", "escape",
    "survive", "hide", "protect", "build", "form", "freeze", "melt",
    "remember", "hunt", "change", "vanish", "recover", "pull", "pulls",
    "follow", "follows",
}

PAYOFF_TERMS = {
    "because", "that is why", "that's why", "explains why", "payoff",
    "trick", "reason", "watch again", "look again",
}

WEAK_PHRASES = {
    "did you know", "in this video", "today we", "nature is amazing",
    "you won't believe", "hidden secret", "animal kingdom",
}


@dataclass(frozen=True)
class ScoreBreakdown:
    score: int
    signals: dict[str, int]
    verdict: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text or "")


def _text(story: dict) -> str:
    return " ".join(str(story.get(k) or "") for k in (
        "category", "topic_hashtag", "title", "seo_title", "hook",
        "script", "thumbnail_text", "description",
    )).lower()


def _contains(text: str, terms: set[str]) -> int:
    return sum(1 for term in terms if re.search(r"\b" + re.escape(term) + r"\b", text))


def load_format_memory(path: Path = MEMORY_PATH) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def build_format_memory(markers: list[dict]) -> dict:
    category_scores: dict[str, list[float]] = defaultdict(list)
    format_scores: dict[str, list[float]] = defaultdict(list)
    title_patterns: Counter[str] = Counter()
    thumbnail_patterns: Counter[str] = Counter()
    hook_patterns: Counter[str] = Counter()

    for marker in markers:
        category = str(marker.get("category") or "").lower()
        fmt = str(marker.get("story_format") or "").lower()
        stats = marker.get("analytics") if isinstance(marker.get("analytics"), dict) else {}
        views = float(stats.get("views") or marker.get("views") or 0)
        avg_view = float(stats.get("averageViewPercentage") or stats.get("avg_view_pct") or marker.get("avg_view_pct") or 0)
        likes = float(stats.get("likes") or marker.get("likes") or 0)
        comments = float(stats.get("comments") or marker.get("comments") or 0)
        subs = float(stats.get("subscribersGained") or marker.get("subscribers_gained") or 0)
        quality = avg_view + min(20, math.log10(max(views, 1)) * 5) + comments * 1.5 + likes * 0.2 + subs * 4
        if category:
            category_scores[category].append(quality)
        if fmt:
            format_scores[fmt].append(quality)
        title = str(marker.get("title") or "")
        thumb = str(marker.get("thumbnail_text") or "")
        hook = str(marker.get("hook") or "")
        if title:
            title_patterns[_pattern(title)] += max(1, int(quality // 20))
        if thumb:
            thumbnail_patterns[_pattern(thumb)] += max(1, int(quality // 20))
        if hook:
            hook_patterns[_pattern(hook)] += max(1, int(quality // 20))

    def _avg_map(values: dict[str, list[float]]) -> dict[str, float]:
        return {k: round(sum(v) / len(v), 2) for k, v in values.items() if v}

    return {
        "category_scores": _avg_map(category_scores),
        "format_scores": _avg_map(format_scores),
        "winning_title_patterns": dict(title_patterns.most_common(12)),
        "winning_thumbnail_patterns": dict(thumbnail_patterns.most_common(12)),
        "winning_hook_patterns": dict(hook_patterns.most_common(12)),
    }


def _pattern(text: str) -> str:
    words = _words(text.lower())
    out = []
    for word in words[:8]:
        if word in VISUAL_TERMS:
            out.append("{visual}")
        elif word in ACTION_TERMS:
            out.append("{action}")
        elif word in EMOTIONAL_TERMS:
            out.append("{emotion}")
        elif len(word) > 3:
            out.append("{subject}")
        else:
            out.append(word)
    return " ".join(out)


def score_topic(story: dict, memory: dict | None = None) -> dict:
    memory = memory or {}
    text = _text(story)
    category = str(story.get("category") or "").lower()
    tags = " ".join(str(t) for t in (story.get("yt_tags") or []))
    base = {
        "viral_potential": 40 + _contains(text, EMOTIONAL_TERMS) * 8 + _contains(text, ACTION_TERMS) * 5,
        "visual_potential": 45 + _contains(text, VISUAL_TERMS) * 10,
        "replay_potential": 42 + _contains(text, {"watch", "spot", "notice", "again", "cue", "before"}) * 10,
        "comment_potential": 30 + _contains(text, COMMENT_TERMS) * 8,
        "educational_potential": 45 + _contains(text, {"because", "why", "science", "research", "forms", "helps"}) * 7,
        "emotional_potential": 35 + _contains(text, EMOTIONAL_TERMS) * 9,
        "novelty": 45 + _contains(text + " " + tags.lower(), {"rare", "strange", "new", "unknown", "first", "weird"}) * 10,
    }
    if category in PRIORITY_CATEGORIES:
        for key in ("viral_potential", "visual_potential", "novelty"):
            base[key] += 14
        base["educational_potential"] += 8
    if category in NATURE_TOPICS:
        base["educational_potential"] += 6
    hist = (memory.get("category_scores") or {}).get(category)
    if hist:
        adj = max(-8, min(10, (float(hist) - 65) / 3))
        for key in base:
            base[key] += int(adj)
    signals = {k: max(0, min(100, int(v))) for k, v in base.items()}
    if signals["visual_potential"] >= 55 and signals["educational_potential"] >= 55:
        signals["viral_potential"] = min(100, signals["viral_potential"] + 8)
        signals["replay_potential"] = min(100, signals["replay_potential"] + 8)
    if _contains(text, ACTION_TERMS) and any(term in text for term in PAYOFF_TERMS):
        signals["replay_potential"] = min(100, signals["replay_potential"] + 12)
        signals["comment_potential"] = min(100, signals["comment_potential"] + 8)
        signals["educational_potential"] = min(100, signals["educational_potential"] + 6)
    score = round(
        signals["viral_potential"] * 0.18
        + signals["visual_potential"] * 0.20
        + signals["replay_potential"] * 0.16
        + signals["comment_potential"] * 0.12
        + signals["educational_potential"] * 0.14
        + signals["emotional_potential"] * 0.10
        + signals["novelty"] * 0.10
    )
    reasons = []
    if signals["visual_potential"] < 55:
        reasons.append("weak_visual_surface")
    if signals["replay_potential"] < 50:
        reasons.append("weak_replay_reason")
    if score < 58:
        reasons.append("low_opportunity_score")
    verdict = "scale" if score >= 78 else ("produce" if score >= 64 else ("rewrite" if score >= 58 else "discard"))
    return ScoreBreakdown(score=score, signals=signals, verdict=verdict, reasons=tuple(reasons)).to_dict()


def analyze_retention(story: dict) -> dict:
    title = str(story.get("seo_title") or story.get("title") or "")
    hook = str(story.get("hook") or "")
    script = str(story.get("script") or "")
    text = _text(story)
    words = _words(script)
    hook_words = _words(hook)
    lower_hook = hook.lower()
    weak_hits = [p for p in WEAK_PHRASES if p in text]

    hook_score = 82
    if not hook:
        hook_score = 20
    if len(hook_words) > 10:
        hook_score -= 18
    if any(lower_hook.startswith(p) for p in WEAK_PHRASES):
        hook_score -= 24
    if not _contains(lower_hook, ACTION_TERMS | VISUAL_TERMS):
        hook_score -= 12

    curiosity_score = 55 + _contains(text, {"why", "because", "but", "watch", "before", "reason"}) * 8
    visual_score = 50 + _contains(text, VISUAL_TERMS) * 8
    replay_score = 52 + _contains(text, {"watch", "spot", "again", "before", "cue", "notice", "replay"}) * 10

    completion = 76
    if len(words) < 36:
        completion -= 4
    elif len(words) > 62:
        completion -= min(22, (len(words) - 62) // 3 * 2)
    if any(term in text for term in PAYOFF_TERMS):
        completion += 8
    if weak_hits:
        completion -= 10 + len(weak_hits) * 3
    if title and hook and len(set(_words(title.lower())[:5]) & set(_words(hook.lower())[:5])) >= 4:
        completion -= 7

    signals = {
        "hook_score": max(0, min(100, int(hook_score))),
        "curiosity_score": max(0, min(100, int(curiosity_score))),
        "visual_score": max(0, min(100, int(visual_score))),
        "replay_score": max(0, min(100, int(replay_score))),
        "completion_prediction": max(0, min(100, int(completion))),
    }
    score = round(
        signals["hook_score"] * 0.25
        + signals["curiosity_score"] * 0.18
        + signals["visual_score"] * 0.17
        + signals["replay_score"] * 0.18
        + signals["completion_prediction"] * 0.22
    )
    reasons = []
    if signals["hook_score"] < 70:
        reasons.append("hook_below_threshold")
    if signals["completion_prediction"] < 70:
        reasons.append("completion_risk")
    if signals["replay_score"] < 62:
        reasons.append("weak_replay_loop")
    verdict = "ready" if score >= 78 else ("rewrite" if score >= 62 else "discard")
    return ScoreBreakdown(score=score, signals=signals, verdict=verdict, reasons=tuple(reasons)).to_dict()


def _subject(story: dict) -> str:
    for source in (story.get("yt_tags") or []):
        text = str(source).strip()
        if text and len(text.split()) <= 3:
            return text.title()
    category = str(story.get("category") or "Nature").replace("_", " ")
    return category.title()


def _action(story: dict) -> str:
    text = _text(story)
    for term in ACTION_TERMS:
        if re.search(r"\b" + re.escape(term) + r"\b", text):
            return term
    return "changes"


def _cue(story: dict) -> str:
    text = _text(story)
    cue_priority = [
        "eyes", "wing", "wings", "tail", "paws", "feet", "beak", "lava",
        "mushroom", "mushrooms", "threads", "roots", "reef", "coral",
        "storm", "lightning", "glacier", "rock", "crater", "movement",
    ]
    for term in cue_priority:
        if re.search(r"\b" + re.escape(term) + r"\b", text):
            return term
    return "detail"


def generate_packaging_options(story: dict) -> dict:
    subject = _subject(story)
    action = _action(story)
    cue = _cue(story)
    current_title = str(story.get("seo_title") or story.get("title") or f"{subject} {action}").strip()
    titles = [
        current_title,
        f"{subject} {action} for one strange reason",
        f"Watch the {cue} when {subject.lower()} {action}",
        f"{subject} is not doing this by accident",
        f"The {cue} that explains {subject.lower()}",
        f"{subject} hides a tiny nature trick",
        f"{subject} does this before the reveal",
        f"Why {subject.lower()} {action} is not random",
        f"{subject}: watch this {cue}",
        f"This {cue} changes the whole story",
    ]
    thumbs = [
        str(story.get("thumbnail_text") or "").upper(),
        f"WATCH THE {cue}".upper(),
        f"{subject} {action}".upper(),
        f"{cue} EXPLAINS IT".upper(),
        "NOT RANDOM",
        "TINY CLUE",
        "NATURE TRICK",
        "LOOK CLOSER",
        "WAIT FOR IT",
        "THE REAL REASON",
    ]
    hooks = [
        str(story.get("hook") or "").strip(),
        f"{subject} {action} because of one tiny {cue}.",
        f"Watch the {cue}; it gives away the whole trick.",
        f"This {cue} is not random.",
        f"{subject} has a shortcut most people miss.",
    ]

    def _dedupe(items: list[str], limit: int) -> list[str]:
        out, seen = [], set()
        for item in items:
            cleaned = re.sub(r"\s+", " ", item).strip(" .,:;-")
            key = cleaned.lower()
            if cleaned and key not in seen:
                out.append(cleaned[:90])
                seen.add(key)
            if len(out) >= limit:
                break
        return out

    return {
        "titles": _dedupe(titles, 10),
        "thumbnail_texts": _dedupe([" ".join(t.split()[:4]) for t in thumbs], 10),
        "hooks": _dedupe(hooks, 5),
    }


def score_package_variant(story: dict, title: str, thumbnail_text: str, hook: str,
                          memory: dict | None = None) -> int:
    candidate = {**story, "title": title, "seo_title": title, "thumbnail_text": thumbnail_text, "hook": hook}
    retention = analyze_retention(candidate)["score"]
    topic = score_topic(candidate, memory=memory)["score"]
    thumb_words = len(_words(thumbnail_text))
    thumb_score = 85 if 2 <= thumb_words <= 4 else 55
    pattern_bonus = 0
    memory = memory or {}
    patterns = memory.get("winning_title_patterns") or {}
    if _pattern(title) in patterns:
        pattern_bonus += min(8, int(patterns[_pattern(title)]))
    score = int(topic * 0.25 + retention * 0.45 + thumb_score * 0.20 + pattern_bonus)
    return max(0, min(100, score))


def select_best_packaging(story: dict, memory: dict | None = None) -> dict:
    options = generate_packaging_options(story)
    best = None
    scored = []
    for title in options["titles"]:
        for thumb in options["thumbnail_texts"]:
            for hook in options["hooks"]:
                score = score_package_variant(story, title, thumb, hook, memory=memory)
                row = {"score": score, "title": title, "thumbnail_text": thumb, "hook": hook}
                scored.append(row)
                if best is None or score > best["score"]:
                    best = row
    scored.sort(key=lambda row: row["score"], reverse=True)
    return {
        "best": best or {"score": 0, "title": story.get("title", ""), "thumbnail_text": story.get("thumbnail_text", ""), "hook": story.get("hook", "")},
        "top_variants": scored[:10],
        "options": options,
    }
