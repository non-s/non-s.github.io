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
import hashlib
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from utils.nature_strategy import NATURE_TOPICS
from utils.audience_memory import load_audience_memory
from utils.confidence_engine import assess_confidence
from utils.editorial_guard import editorial_issues

MEMORY_PATH = Path("_data/format_memory.json")
WINNER_PATTERNS_PATH = Path("_data/winner_patterns.json")

PRIORITY_CATEGORIES = {
    "fungi",
    "forests",
    "ocean",
    "volcanoes",
    "weather",
    "geology",
    "ecosystems",
    "rare_phenomena",
    "conservation",
    "discoveries",
    "wildlife",
    "reptiles",
    "insects",
    "birds",
}

CATEGORY_FALLBACK_CUES = {
    "fungi": "underground threads",
    "plants": "leaf movement",
    "forests": "canopy shift",
    "geology": "rock layers",
    "earth_from_space": "cloud pattern",
    "ocean": "water movement",
}

SUBJECT_CUE_TERMS_BY_CATEGORY = {
    "fungi": {"fungi", "fungus", "mushroom", "mushrooms"},
    "plants": {"plant", "plants"},
    "forests": {"forest", "forests", "tree", "trees"},
    "geology": {"geology", "geologies"},
    "earth_from_space": {"earth", "system", "systems"},
    "ocean": {"ocean", "sea", "water"},
}

VISUAL_TERMS = {
    "lava",
    "glow",
    "storm",
    "lightning",
    "tornado",
    "aurora",
    "waves",
    "reef",
    "coral",
    "mushroom",
    "roots",
    "canopy",
    "ice",
    "crystal",
    "cave",
    "river",
    "waterfall",
    "volcano",
    "cloud",
    "clouds",
    "ash",
    "glacier",
    "eyes",
    "tail",
    "wings",
    "paws",
    "camouflage",
    "color",
    "colour",
    "wing",
    "feet",
    "beak",
    "fin",
    "fins",
    "pupil",
    "pupils",
    "movement",
    "ear",
    "ears",
    "head",
    "hand",
    "hands",
    "flipper",
    "flippers",
    "hoof",
    "hooves",
    "mouth",
    "feeding",
    "bottle",
    "rock",
    "rocks",
    "mushrooms",
    "mycelium",
    "underground",
    "thread",
    "threads",
    "cap",
    "caps",
    "gill",
    "gills",
    "spore",
    "spores",
    "object",
    "objects",
    "group",
    "groups",
    "line",
    "lines",
    "thread",
    "threads",
    "cap",
    "caps",
    "nest",
    "soil",
    "predator",
    "predators",
    "gesture",
    "gestures",
}

EMOTIONAL_TERMS = {
    "rare",
    "tiny",
    "giant",
    "ancient",
    "hidden",
    "deadly",
    "strange",
    "weird",
    "survive",
    "rescue",
    "protect",
    "vanish",
    "explode",
}

COMMENT_TERMS = {
    "why",
    "how",
    "which",
    "what",
    "next",
    "guess",
    "spot",
    "notice",
    "comment",
    "ever",
    "would",
}

ACTION_TERMS = {
    "erupt",
    "glow",
    "move",
    "grow",
    "talk",
    "signal",
    "signals",
    "connect",
    "connects",
    "communicate",
    "communicates",
    "escape",
    "survive",
    "hide",
    "protect",
    "build",
    "form",
    "freeze",
    "melt",
    "remember",
    "hunt",
    "change",
    "changes",
    "vanish",
    "recover",
    "pull",
    "pulls",
    "follow",
    "follows",
    "lock",
    "locks",
    "choose",
    "chooses",
    "fake",
    "fakes",
    "trick",
    "tricks",
    "aim",
    "breathe",
    "carry",
    "chew",
    "cling",
    "cool",
    "dance",
    "feel",
    "graze",
    "groom",
    "map",
    "pant",
    "point",
    "pollinate",
    "read",
    "reuse",
    "rotate",
    "sample",
    "see",
    "sense",
    "smell",
    "stay",
    "step",
    "track",
    "trade",
    "turn",
    "walk",
}
ACTION_PRIORITY = (
    "fake",
    "fakes",
    "protect",
    "escape",
    "remember",
    "recognize",
    "signal",
    "signals",
    "communicate",
    "communicates",
    "connect",
    "connects",
    "follow",
    "follows",
    "lock",
    "locks",
    "rely",
    "survive",
    "hide",
    "hunt",
    "choose",
    "chooses",
    "trick",
    "tricks",
    "pull",
    "pulls",
    "aim",
    "breathe",
    "carry",
    "chew",
    "cling",
    "cool",
    "dance",
    "feel",
    "graze",
    "groom",
    "map",
    "pant",
    "point",
    "pollinate",
    "read",
    "reuse",
    "rotate",
    "sample",
    "see",
    "sense",
    "smell",
    "stay",
    "step",
    "track",
    "trade",
    "turn",
    "walk",
    "build",
    "form",
    "grow",
    "move",
    "talk",
    "glow",
    "erupt",
    "recover",
    "freeze",
    "melt",
    "vanish",
    "change",
    "changes",
)

PAYOFF_TERMS = {
    "because",
    "that is why",
    "that's why",
    "explains why",
    "payoff",
    "trick",
    "reason",
    "watch again",
    "look again",
}

WEAK_PHRASES = {
    "did you know",
    "in this video",
    "today we",
    "nature is amazing",
    "you won't believe",
    "hidden secret",
    "animal kingdom",
    "amazing fact",
    "incredible",
    "mind blowing",
    "this will shock you",
}

SATURATED_PATTERNS = {
    "another secret",
    "hidden reason",
    "hiding in plain sight",
    "one tiny movement",
    "you won't believe",
    "wait for it",
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


def _copy_is_recommendable(value: str) -> bool:
    value = str(value or "").strip()
    if not value:
        return False
    return not editorial_issues({"title": value, "seo_title": value, "hook": value}, include_script=False)


def _text(story: dict) -> str:
    return " ".join(
        str(story.get(k) or "")
        for k in (
            "category",
            "topic_hashtag",
            "title",
            "seo_title",
            "hook",
            "script",
            "thumbnail_text",
            "description",
        )
    ).lower()


def _contains(text: str, terms: set[str]) -> int:
    return sum(1 for term in terms if re.search(r"\b" + re.escape(term) + r"\b", text))


def load_format_memory(path: Path = MEMORY_PATH) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_winner_patterns(path: Path = WINNER_PATTERNS_PATH) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _audience(memory: dict | None = None) -> dict:
    if memory and isinstance(memory.get("audience_memory"), dict):
        return memory["audience_memory"]
    return load_audience_memory()


def _weight(memory: dict, axis: str, key: str, default: float = 1.0) -> float:
    try:
        return float(((memory.get("weights") or {}).get(axis) or {}).get(key, default))
    except Exception:
        return default


def _metric(marker: dict, stats: dict, *names: str) -> float:
    for name in names:
        if name in stats:
            value = stats.get(name)
        else:
            value = marker.get(name)
        try:
            if value not in (None, ""):
                return float(value)
        except Exception:
            continue
    return 0.0


def _performance_score(marker: dict) -> float:
    stats = marker.get("analytics") if isinstance(marker.get("analytics"), dict) else {}
    views = _metric(marker, stats, "views", "viewCount")
    likes = _metric(marker, stats, "likes", "likeCount")
    comments = _metric(marker, stats, "comments", "commentCount")
    avg_view = _metric(marker, stats, "averageViewPercentage", "avg_view_pct", "avg_view_percentage")
    subs = _metric(marker, stats, "subscribersGained", "subscribers_gained")
    like_rate = likes / max(views, 1)
    comment_rate = comments / max(views, 1)
    sub_rate = subs / max(views, 1)
    retention = avg_view if avg_view else 45
    reach = min(18, math.log10(max(views, 1)) * 4)
    engagement = min(20, like_rate * 550 + comment_rate * 1200 + sub_rate * 2500)
    return round(retention * 0.58 + reach + engagement, 2)


def build_format_memory(markers: list[dict]) -> dict:
    category_scores: dict[str, list[float]] = defaultdict(list)
    format_scores: dict[str, list[float]] = defaultdict(list)
    title_patterns: Counter[str] = Counter()
    thumbnail_patterns: Counter[str] = Counter()
    hook_patterns: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    format_counts: Counter[str] = Counter()
    weak_patterns: Counter[str] = Counter()
    experiment_scores: dict[str, list[float]] = defaultdict(list)
    series_counts: Counter[str] = Counter()
    category_sub_rates: dict[str, list[float]] = defaultdict(list)
    format_sub_rates: dict[str, list[float]] = defaultdict(list)

    for marker in markers:
        category = str(marker.get("category") or "").lower()
        fmt = str(marker.get("story_format") or "").lower()
        stats = marker.get("analytics") if isinstance(marker.get("analytics"), dict) else {}
        views = _metric(marker, stats, "views", "viewCount")
        subs = _metric(marker, stats, "subscribersGained", "subscribers_gained")
        comments = _metric(marker, stats, "comments", "commentCount")
        subs_per_1k = subs * 1000 / max(views, 1)
        comments_per_1k = comments * 1000 / max(views, 1)
        quality = _performance_score(marker)
        has_real_views = views > 0
        if category:
            category_counts[category] += 1
            if has_real_views:
                category_scores[category].append(quality)
                category_sub_rates[category].append(subs_per_1k + comments_per_1k * 0.12)
        if fmt:
            format_counts[fmt] += 1
            if has_real_views:
                format_scores[fmt].append(quality)
                format_sub_rates[fmt].append(subs_per_1k + comments_per_1k * 0.12)
        series = str(marker.get("series") or "").strip()
        if series:
            series_counts[re.sub(r"\s+#\d+$", "", series)] += 1
        title = str(marker.get("title") or "")
        thumb = str(marker.get("thumbnail_text") or "")
        hook = str(marker.get("hook") or "")
        weight = max(1, int(quality // 16)) if has_real_views else 1
        for value, counter in (
            (title, title_patterns),
            (thumb, thumbnail_patterns),
            (hook, hook_patterns),
        ):
            if not value:
                continue
            pattern = _pattern(value)
            if _copy_is_recommendable(value):
                counter[pattern] += weight
            else:
                weak_patterns[pattern] += weight
        if has_real_views and quality < 48:
            for value in (title, thumb, hook):
                if value:
                    weak_patterns[_pattern(value)] += 1
        packaging = marker.get("packaging") if isinstance(marker.get("packaging"), dict) else {}
        experiment = packaging.get("experiment") if isinstance(packaging.get("experiment"), dict) else {}
        assignment = experiment.get("assignment") if isinstance(experiment.get("assignment"), dict) else {}
        for axis, variant in assignment.items():
            if variant and has_real_views:
                experiment_scores[f"{axis}:{variant}"].append(quality)

    def _avg_map(values: dict[str, list[float]]) -> dict[str, float]:
        return {k: round(sum(v) / len(v), 2) for k, v in values.items() if v}

    category_avg = _avg_map(category_scores)
    format_avg = _avg_map(format_scores)
    experiment_avg = _avg_map(experiment_scores)
    category_sub_avg = _avg_map(category_sub_rates)
    format_sub_avg = _avg_map(format_sub_rates)
    category_real_counts = Counter({k: len(v) for k, v in category_scores.items()})
    format_real_counts = Counter({k: len(v) for k, v in format_scores.items()})
    category_sub_counts = Counter({k: len(v) for k, v in category_sub_rates.items()})
    format_sub_counts = Counter({k: len(v) for k, v in format_sub_rates.items()})
    enough_category_data = sum(category_real_counts.values()) >= 8
    enough_format_data = sum(format_real_counts.values()) >= 8

    def _weights(scores: dict[str, float], counts: Counter[str], enough: bool) -> dict[str, float]:
        if not enough:
            return {}
        out = {}
        for key, score in scores.items():
            confidence = min(1.0, counts[key] / 5)
            out[key] = round(1 + ((score - 62) / 100) * confidence, 3)
        return out

    def _subscriber_weights(scores: dict[str, float], counts: Counter[str], enough: bool) -> dict[str, float]:
        if not enough:
            return {}
        out = {}
        for key, score in scores.items():
            confidence = min(1.0, counts[key] / 5)
            out[key] = round(max(0.85, min(1.25, 1 + ((score - 1.5) / 10) * confidence)), 3)
        return out

    return {
        "sample_count": len(markers),
        "category_counts": dict(category_counts),
        "format_counts": dict(format_counts),
        "series_counts": dict(series_counts),
        "category_scores": category_avg,
        "format_scores": format_avg,
        "category_subscriber_rates": category_sub_avg,
        "format_subscriber_rates": format_sub_avg,
        "category_weights": _weights(category_avg, category_real_counts, enough_category_data),
        "format_weights": _weights(format_avg, format_real_counts, enough_format_data),
        "subscriber_category_weights": _subscriber_weights(category_sub_avg, category_sub_counts, enough_category_data),
        "subscriber_format_weights": _subscriber_weights(format_sub_avg, format_sub_counts, enough_format_data),
        "winning_title_patterns": dict(title_patterns.most_common(12)),
        "winning_thumbnail_patterns": dict(thumbnail_patterns.most_common(12)),
        "winning_hook_patterns": dict(hook_patterns.most_common(12)),
        "weak_patterns": dict(weak_patterns.most_common(12)),
        "experiment_scores": experiment_avg,
        "winning_experiments": dict(sorted(experiment_avg.items(), key=lambda item: item[1], reverse=True)[:12]),
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


def _distribution_adjustment(story: dict, patterns: dict | None = None) -> int:
    patterns = patterns or load_winner_patterns()
    if not patterns or int(patterns.get("sample_count") or 0) < 8:
        return 0
    confidence = (
        patterns.get("confidence")
        if isinstance(patterns.get("confidence"), dict)
        else assess_confidence(
            "distribution",
            int(patterns.get("sample_count") or 0),
            observed=int(patterns.get("winner_count") or 0) + int(patterns.get("loser_count") or 0),
            estimated=max(
                0,
                int(patterns.get("sample_count") or 0)
                - int(patterns.get("winner_count") or 0)
                - int(patterns.get("loser_count") or 0),
            ),
        )
    )
    if not confidence.get("can_adjust_strategy"):
        return 0
    category = str(story.get("category") or "").lower()
    fmt = str(story.get("story_format") or "").lower()
    series = re.sub(r"\s+#\d+$", "", str(story.get("series") or ""))
    title_pattern = _pattern(str(story.get("seo_title") or story.get("title") or ""))
    hook_pattern = _pattern(str(story.get("hook") or ""))
    thumb_pattern = _pattern(str(story.get("thumbnail_text") or ""))
    adj = 0
    if category and category in (patterns.get("winning_categories") or {}):
        adj += 5
    if fmt and fmt in (patterns.get("winning_formats") or {}):
        adj += 5
    if series and series in (patterns.get("winning_series") or {}):
        adj += 4
    if hook_pattern and hook_pattern in (patterns.get("winning_hooks") or {}):
        adj += 5
    if thumb_pattern and thumb_pattern in (patterns.get("winning_thumbnails") or {}):
        adj += 3
    if category and category in (patterns.get("losing_categories") or {}):
        adj -= 5
    if fmt and fmt in (patterns.get("losing_formats") or {}):
        adj -= 4
    if series and series in (patterns.get("losing_series") or {}):
        adj -= 4
    if title_pattern and title_pattern in (patterns.get("winning_hooks") or {}):
        adj += 2
    adj = int(round(adj * float(confidence.get("bootstrap_multiplier") or 0)))
    return max(-12, min(18, adj))


def score_topic(story: dict, memory: dict | None = None) -> dict:
    memory = memory or {}
    audience = _audience(memory)
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
        "novelty": 45
        + _contains(text + " " + tags.lower(), {"rare", "strange", "new", "unknown", "first", "weird"}) * 10,
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
    retention_weight = _weight(audience, "category_retention", category)
    subscriber_weight = _weight(audience, "category_subscribers", category)
    comment_weight = _weight(audience, "category_comments", category)
    if audience.get("sample_count", 0) >= 8:
        base["visual_potential"] *= retention_weight
        base["replay_potential"] *= retention_weight
        base["viral_potential"] *= subscriber_weight
        base["comment_potential"] *= comment_weight
    signals = {k: max(0, min(100, int(v))) for k, v in base.items()}
    if signals["visual_potential"] >= 55 and signals["educational_potential"] >= 55:
        signals["viral_potential"] = min(100, signals["viral_potential"] + 8)
        signals["replay_potential"] = min(100, signals["replay_potential"] + 8)
    if _contains(text, ACTION_TERMS) and any(term in text for term in PAYOFF_TERMS):
        signals["replay_potential"] = min(100, signals["replay_potential"] + 12)
        signals["comment_potential"] = min(100, signals["comment_potential"] + 8)
        signals["educational_potential"] = min(100, signals["educational_potential"] + 6)
    distribution_adj = _distribution_adjustment(
        story, memory.get("winner_patterns") if isinstance(memory.get("winner_patterns"), dict) else None
    )
    if distribution_adj:
        signals["viral_potential"] = max(0, min(100, signals["viral_potential"] + distribution_adj))
        signals["replay_potential"] = max(0, min(100, signals["replay_potential"] + int(distribution_adj * 0.5)))
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
    if score < 55:
        reasons.append("low_opportunity_score")
    verdict = "scale" if score >= 78 else ("produce" if score >= 64 else ("rewrite" if score >= 55 else "discard"))
    confidence = ((audience.get("category") or {}).get(category) or {}).get("confidence") or assess_confidence(
        "category",
        0,
        inferred=1,
    )
    out = ScoreBreakdown(score=score, signals=signals, verdict=verdict, reasons=tuple(reasons)).to_dict()
    out["confidence"] = confidence
    out["reasoning"] = confidence.get(
        "reasoning", "Topic score uses current story signals while audience data matures."
    )
    return out


def detect_weak_content(story: dict, memory: dict | None = None) -> dict:
    memory = memory or {}
    text = _text(story)
    title = str(story.get("seo_title") or story.get("title") or "")
    hook = str(story.get("hook") or "")
    thumb = str(story.get("thumbnail_text") or "")
    script_words = _words(str(story.get("script") or "").lower())
    risk = 0
    reasons: list[str] = []
    for phrase in WEAK_PHRASES | SATURATED_PATTERNS:
        if phrase in text:
            risk += 14
            reasons.append("generic_or_saturated_language")
            break
    if len(_words(thumb)) > 4 or any(word in thumb.lower() for word in ("amazing", "secret", "today")):
        risk += 18
        reasons.append("generic_thumbnail")
    if hook and len(set(_words(hook.lower()))) <= 3:
        risk += 18
        reasons.append("generic_hook")
    if script_words:
        common = Counter(script_words).most_common(1)[0]
        if common[1] >= 7 or len(set(script_words)) / max(1, len(script_words)) < 0.48:
            risk += 22
            reasons.append("repetitive_script")
    weak_patterns = memory.get("weak_patterns") or {}
    for value, label in ((title, "weak_title_pattern"), (thumb, "weak_thumbnail_pattern"), (hook, "weak_hook_pattern")):
        pattern = _pattern(value)
        if pattern and weak_patterns.get(pattern, 0) >= 2:
            risk += 14
            reasons.append(label)
    recent = memory.get("recent_topics") or []
    key = re.sub(r"\s+", " ", f"{story.get('category', '')} {title}".lower()).strip()
    if key and key in recent:
        risk += 24
        reasons.append("recently_recycled_topic")
    risk = max(0, min(100, risk))
    return {
        "risk": risk,
        "state": "block" if risk >= 55 else ("watch" if risk >= 30 else "clear"),
        "reasons": tuple(dict.fromkeys(reasons)),
        "confidence": assess_confidence("pattern", len(memory.get("weak_patterns") or {}), inferred=1),
        "reasoning": "Weak-content checks use deterministic pattern risk plus any repeated weak patterns in memory.",
    }


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

    audience = load_audience_memory()
    category = str(story.get("category") or "").lower()
    fmt = str(story.get("story_format") or "").lower()
    if audience.get("sample_count", 0) >= 8:
        completion *= _weight(audience, "category_retention", category)
        if fmt:
            completion *= _weight(audience, "format_retention", fmt)

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
    confidence = ((audience.get("category") or {}).get(category) or {}).get("confidence") or assess_confidence(
        "category",
        0,
        inferred=1,
    )
    out = ScoreBreakdown(score=score, signals=signals, verdict=verdict, reasons=tuple(reasons)).to_dict()
    out["confidence"] = confidence
    out["reasoning"] = confidence.get(
        "reasoning", "Retention score is heuristic until real retention samples are available."
    )
    return out


def _subject(story: dict) -> str:
    for source in story.get("yt_tags") or []:
        text = str(source).strip()
        if text and len(text.split()) <= 3:
            return text.title()
    category = str(story.get("category") or "Nature").replace("_", " ")
    return category.title()


def _display_subject(subject: str) -> str:
    """Return a short plural display subject for grammar-safe packaging."""
    text = re.sub(r"\s+", " ", str(subject or "Nature").strip()).title()
    lower = text.lower()
    irregular = {
        "deer": "Deer",
        "earth": "Earth systems",
        "earth systems": "Earth systems",
        "earth from space": "Earth systems",
        "earth_from_space": "Earth systems",
        "geology": "Geology",
        "geologies": "Geology",
        "weather": "Weather patterns",
        "wildlife": "Wildlife",
        "fish": "Fish",
        "sheep": "Sheep",
        "fungus": "Fungi",
        "fungi": "Fungi",
        "octopus": "Octopuses",
        "cactus": "Cacti",
        "goose": "Geese",
        "mouse": "Mice",
    }
    if lower in irregular:
        return irregular[lower]
    if len(text.split()) > 1:
        return text
    if lower.endswith("s"):
        return text
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
        return text[:-1] + "ies"
    if lower.endswith(("ch", "sh", "x", "z")):
        return text + "es"
    return text + "s"


def _action(story: dict) -> str:
    text = _text(story)
    for term in ACTION_PRIORITY:
        if re.search(r"\b" + re.escape(term) + r"\b", text):
            return term
    return "changes"


def _plural_action(action: str) -> str:
    action = str(action or "change").strip().lower()
    irregular = {
        "changes": "change",
        "signals": "signal",
        "communicates": "communicate",
        "connects": "connect",
        "pulls": "pull",
        "follows": "follow",
        "fakes": "fake",
        "tricks": "trick",
    }
    if action in irregular:
        return irregular[action]
    return action


def _cue_subject_terms(story: dict) -> set[str]:
    category = str(story.get("category") or "").lower()
    terms = set(SUBJECT_CUE_TERMS_BY_CATEGORY.get(category, set()))
    for source in (_subject(story), category):
        for word in _words(str(source).lower()):
            if len(word) <= 2:
                continue
            terms.add(word)
            if word.endswith("ies") and len(word) > 3:
                terms.add(word[:-3] + "y")
            elif word.endswith("s"):
                terms.add(word[:-1])
            else:
                terms.add(f"{word}s")
                if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
                    terms.add(word[:-1] + "ies")
    return terms


def _subject_word_forms(subject: str) -> set[str]:
    forms: set[str] = set()
    for word in _words(str(subject).lower()):
        if len(word) <= 2:
            continue
        forms.add(word)
        if word.endswith("ies") and len(word) > 3:
            forms.add(word[:-3] + "y")
        elif word.endswith("s"):
            forms.add(word[:-1])
        else:
            forms.add(f"{word}s")
            if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
                forms.add(word[:-1] + "ies")
    return forms


def _title_repeats_subject_as_cue(title: str, subject: str) -> bool:
    forms = _subject_word_forms(subject)
    if not forms:
        return False
    words = _words(str(title).lower())
    for idx, word in enumerate(words[:6]):
        if word not in {"use", "uses", "rely", "relies", "read", "reads", "show", "shows"}:
            continue
        before = set(words[max(0, idx - 2) : idx])
        after = set(words[idx + 1 : idx + 4])
        if before & forms and after & forms:
            return True
    return False


def _thumbnail_repeats_subject(thumbnail_text: str, subject: str) -> bool:
    words = set(_words(str(thumbnail_text).lower()))
    forms = _subject_word_forms(subject)
    return bool(words & forms) and len(words) > 1


def _thumbnail_matches_cue(thumbnail_text: str, cue: str) -> bool:
    words = set(_words(str(thumbnail_text).lower()))
    if not words:
        return False
    cue = str(cue or "").strip().lower()
    cue_words = set(_words(cue))
    cue_synonyms = {
        "cloud pattern": {"cloud", "clouds", "pattern", "sky"},
        "rock layers": {"rock", "rocks", "layer", "layers"},
        "leaf movement": {"leaf", "leaves", "move", "movement"},
        "mycelium network": {"mycelium", "fungal", "web", "network", "thread", "threads"},
        "underground threads": {"thread", "threads", "fungal", "web", "network"},
        "root network": {"root", "roots", "network"},
        "wing movement": {"wing", "wings", "flash", "beat", "move", "movement"},
        "wing position": {"wing", "wings", "angle", "position"},
        "fin movement": {"fin", "fins", "shift", "move", "movement"},
        "ear position": {"ear", "ears", "shift", "position"},
        "eye contact": {"eye", "eyes", "contact"},
        "head movement": {"head", "tilt", "move", "movement"},
        "tail position": {"tail", "lift", "position"},
    }
    allowed = cue_words | cue_synonyms.get(cue, set())
    generic = {"watch", "the", "first", "before", "payoff", "reveal", "matters", "move", "cue"}
    if words <= generic:
        return cue in {"first movement", "first move", "movement"}
    return bool(words & allowed)


def _subject_is_plural(subject: str) -> bool:
    lower = str(subject or "").strip().lower()
    if lower in {
        "cacti",
        "deer",
        "fish",
        "fungi",
        "geese",
        "mice",
        "sheep",
        "wildlife",
        "earth systems",
        "weather patterns",
    }:
        return True
    return lower.endswith("s")


def _subject_verb(subject: str, base: str) -> str:
    base = str(base or "").strip().lower()
    if not base or _subject_is_plural(subject):
        return base
    irregular = {"have": "has", "do": "does"}
    if base in irregular:
        return irregular[base]
    if base.endswith("y") and len(base) > 1 and base[-2] not in "aeiou":
        return f"{base[:-1]}ies"
    if base.endswith(("ch", "sh", "x", "z", "s")):
        return f"{base}es"
    return f"{base}s"


def _cue(story: dict) -> str:
    primary_text = " ".join(
        str(story.get(k) or "")
        for k in (
            "category",
            "topic_hashtag",
            "title",
            "seo_title",
            "hook",
            "script",
            "yt_tags",
        )
    ).lower()
    fallback_text = " ".join(str(story.get(k) or "") for k in ("thumbnail_text", "description")).lower()
    cue_priority = [
        "ear position",
        "head movement",
        "hand movement",
        "tail position",
        "eye contact",
        "wing movement",
        "wing position",
        "beak movement",
        "fin movement",
        "flipper movement",
        "first movement",
        "feeding cue",
        "body cue",
        "object group",
        "number cue",
        "alarm call",
        "alarm calls",
        "antennae",
        "antenna",
        "claws",
        "cud",
        "flower",
        "flowers",
        "grooming",
        "pollen",
        "whiskers",
        "whisker",
        "nose",
        "scent",
        "hands",
        "eyes",
        "wing",
        "wings",
        "tail",
        "paws",
        "feet",
        "beak",
        "underground threads",
        "threads",
        "thread",
        "mycelium",
        "cap",
        "caps",
        "gill",
        "gills",
        "spores",
        "canopy shift",
        "canopy",
        "leaf movement",
        "leaves",
        "leaf",
        "root network",
        "clouds",
        "cloud",
        "lava",
        "roots",
        "rocks",
        "mushroom",
        "mushrooms",
        "reef",
        "coral",
        "storm",
        "lightning",
        "glacier",
        "rock",
        "crater",
        "movement",
    ]
    subject_terms = _cue_subject_terms(story)
    for text in (primary_text, fallback_text):
        for term in cue_priority:
            if term in subject_terms:
                continue
            if re.search(r"\b" + re.escape(term) + r"\b", text):
                return term
    category = str(story.get("category") or "").lower()
    return CATEGORY_FALLBACK_CUES.get(category, "first movement")


def _thumb_cue(cue: str) -> str:
    cue = str(cue or "cue").strip().lower()
    return {
        "ear position": "ear shift",
        "ear movement": "ear shift",
        "head movement": "head tilt",
        "hand movement": "hand cue",
        "tail position": "tail lift",
        "eye contact": "eye contact",
        "wing movement": "wing flash",
        "wing position": "wing angle",
        "beak movement": "beak clue",
        "fin movement": "fin shift",
        "flipper movement": "flipper push",
        "first movement": "first move",
        "feeding cue": "feeding cue",
        "object group": "group",
        "number cue": "number trick",
        "body cue": "body move",
        "underground threads": "thread map",
        "threads": "thread map",
        "thread": "thread map",
        "mycelium": "fungal web",
        "roots": "root signal",
        "cap": "cap clue",
        "caps": "cap clue",
        "gill": "gill lines",
        "gills": "gill lines",
        "spores": "spore dust",
        "rock layers": "rock layer",
        "rocks": "rock layer",
        "rock": "rock layer",
        "cloud pattern": "cloud pattern",
        "clouds": "cloud pattern",
        "cloud": "cloud pattern",
        "leaf movement": "leaf move",
        "leaf": "leaf clue",
        "leaves": "leaf move",
        "canopy shift": "canopy shift",
        "water movement": "water shift",
        "alarm call": "alarm call",
        "alarm calls": "alarm call",
        "antennae": "antenna check",
        "antenna": "antenna check",
        "claws": "claw pads",
        "cud": "cud engine",
        "flower": "flower clue",
        "flowers": "flower clue",
        "grooming": "grooming cue",
        "hands": "hand cue",
        "pollen": "pollen move",
        "whiskers": "whisker map",
        "whisker": "whisker map",
        "nose": "scent check",
        "scent": "scent trail",
        "eyes": "face memory",
        "ear": "ear shift",
        "ears": "ear shift",
        "tail": "tail lift",
        "wing": "wing flash",
        "wings": "wing flash",
        "feet": "foot grip",
        "paws": "paw grip",
        "body": "body move",
    }.get(cue, cue)


def _title_cue(cue: str) -> str:
    cue = str(cue or "cue").strip().lower()
    return {
        "ear position": "ear shift",
        "ear movement": "ear shift",
        "wing position": "wing angle",
        "wing movement": "wing flash",
        "tail position": "tail lift",
        "eye contact": "eye contact",
        "flipper movement": "flipper cue",
        "beak movement": "beak cue",
        "fin movement": "fin cue",
        "head movement": "head tilt",
        "hand movement": "hand movement",
        "first movement": "first move",
        "object group": "object group",
        "number cue": "number cue",
        "underground threads": "underground threads",
        "threads": "underground threads",
        "thread": "underground thread",
        "mycelium": "mycelium network",
        "roots": "root network",
        "cap": "cap shape",
        "caps": "cap shapes",
        "gill": "gill lines",
        "gills": "gill lines",
        "spores": "spore dust",
        "rock layers": "rock layers",
        "rocks": "rock layers",
        "rock": "rock layer",
        "cloud pattern": "cloud pattern",
        "clouds": "cloud patterns",
        "cloud": "cloud pattern",
        "leaf movement": "leaf movement",
        "leaf": "leaf movement",
        "leaves": "leaf movement",
        "canopy shift": "canopy shift",
        "water movement": "water shift",
        "alarm call": "alarm call",
        "alarm calls": "alarm call",
        "antennae": "antennae check",
        "antenna": "antenna check",
        "claws": "claw pads",
        "cud": "cud engine",
        "flower": "flower clue",
        "flowers": "flower clue",
        "grooming": "grooming cue",
        "hands": "hand movement",
        "pollen": "pollen transfer",
        "whiskers": "whisker map",
        "whisker": "whisker map",
        "nose": "scent check",
        "scent": "scent trail",
        "eyes": "eye contact",
        "ear": "ear shift",
        "ears": "ear shift",
        "tail": "tail lift",
        "wing": "wing flash",
        "wings": "wing flash",
        "feet": "foot grip",
        "paws": "paw print",
        "flippers": "flipper stroke",
        "fins": "fin shift",
        "hooves": "hoof step",
        "hands": "hand movement",
        "feathers": "feather flash",
        "whiskers": "whisker map",
        "body": "body move",
    }.get(cue, cue)


def _countable_title_cue(cue: str) -> str:
    cue = str(cue or "cue").strip().lower()
    return {
        "underground threads": "thread network",
        "threads": "thread network",
        "thread": "thread line",
        "mycelium": "mycelium network",
        "roots": "root network",
        "spores": "spore cloud",
        "rock layers": "rock layer",
        "rocks": "rock layer",
        "clouds": "cloud pattern",
        "cloud pattern": "cloud pattern",
        "canopy shift": "canopy shift",
        "canopy": "canopy shift",
        "leaf movement": "leaf movement",
        "leaf": "leaf movement",
        "leaves": "leaf movement",
        "root network": "root network",
        "roots": "root network",
        "alarm call": "alarm call",
        "alarm calls": "alarm call",
        "antennae": "antenna check",
        "antenna": "antenna check",
        "claws": "claw pad",
        "cud": "cud cycle",
        "flower": "flower visit",
        "flowers": "flower visit",
        "grooming": "grooming cue",
        "hands": "hand cue",
        "pollen": "pollen grain",
        "whiskers": "whisker touch",
        "whisker": "whisker touch",
        "nose": "scent check",
        "scent": "scent trail",
        "eyes": "eye line",
        "ear": "ear twitch",
        "ears": "ear twitch",
        "tail": "tail lift",
        "wing": "wing flash",
        "wings": "wing flash",
        "feet": "foot grip",
        "paws": "paw print",
        "flippers": "flipper stroke",
        "fins": "fin shift",
        "hooves": "hoof step",
        "hands": "hand move",
        "feathers": "feather flash",
    }.get(cue, _title_cue(cue))


def generate_packaging_options(story: dict) -> dict:
    subject = _display_subject(_subject(story))
    action = _plural_action(_action(story))
    cue = _cue(story)
    thumb_cue = _thumb_cue(cue)
    title_cue = _title_cue(cue)
    countable_cue = _countable_title_cue(cue)
    subject_pronoun = "they" if _subject_is_plural(subject) else "it"
    current_title = str(story.get("seo_title") or story.get("title") or f"{subject} {action}").strip()
    titles = []
    current_title_candidate = {"title": current_title, "seo_title": current_title, "hook": str(story.get("hook") or "")}
    if not _title_repeats_subject_as_cue(current_title, subject) and not editorial_issues(
        current_title_candidate, include_script=False
    ):
        titles.append(current_title)
    if action in {"signal", "connect", "communicate"}:
        titles.append(f"{subject} {_subject_verb(subject, action)} through {title_cue}")
    titles.extend(
        [
            f"{subject} {_subject_verb(subject, 'use')} {title_cue} before {subject_pronoun} {_subject_verb(subject, action)}",
            f"This {countable_cue} gives {subject.lower()} away",
            f"Why {subject.lower()} {_subject_verb(subject, action)} after one {countable_cue}",
            f"{subject} {_subject_verb(subject, 'reveal')} the answer with {title_cue}",
            f"The {countable_cue} that changes the moment",
            f"{subject} {_subject_verb(subject, 'make')} one {countable_cue} matter",
            f"{subject} {_subject_verb(subject, 'show')} the hidden payoff in seconds",
            f"{subject}: watch this {countable_cue}",
            f"Watch {subject.lower()} after the {countable_cue}",
            f"One {countable_cue} changes how {subject.lower()} {_subject_verb(subject, 'react')}",
        ]
    )
    thumbs = []
    current_thumb = str(story.get("thumbnail_text") or "").upper()
    if (
        current_thumb
        and not editorial_issues(
            {"title": subject, "seo_title": subject, "thumbnail_text": current_thumb}, include_script=False
        )
        and not _thumbnail_repeats_subject(current_thumb, subject)
        and _thumbnail_matches_cue(current_thumb, title_cue)
    ):
        thumbs.append(current_thumb)
    thumbs.extend(
        [
            f"{thumb_cue}".upper(),
            f"WATCH {thumb_cue}".upper(),
            f"{subject} {action}".upper(),
            f"{thumb_cue} MATTERS".upper(),
            f"{thumb_cue} PAYOFF".upper(),
            f"{thumb_cue} FIRST".upper(),
            f"{thumb_cue} REVEAL".upper(),
            "WATCH THE MOVE",
            "BEFORE THE PAYOFF",
        ]
    )
    hooks = []
    current_hook = str(story.get("hook") or "").strip()
    if current_hook and not editorial_issues({"title": current_hook, "hook": current_hook}, include_script=False):
        hooks.append(current_hook)
    hooks.extend(
        [
            f"Watch the {title_cue}; the payoff lands seconds later.",
            f"Start with the {countable_cue}; it explains the next move.",
            f"The {countable_cue} is the detail most people miss.",
            f"{subject} {_subject_verb(subject, 'give')} away the answer through {title_cue}.",
        ]
    )

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


def score_package_variant(story: dict, title: str, thumbnail_text: str, hook: str, memory: dict | None = None) -> int:
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
    audience = _audience(memory or {})
    category = str(story.get("category") or "").lower()
    fmt = str(story.get("story_format") or "").lower()
    audience_bonus = 0
    if audience.get("sample_count", 0) >= 8:
        audience_bonus += int((_weight(audience, "category_subscribers", category) - 1) * 18)
        if fmt:
            audience_bonus += int((_weight(audience, "format_subscribers", fmt) - 1) * 16)
    score = int(topic * 0.22 + retention * 0.42 + thumb_score * 0.18 + pattern_bonus + audience_bonus)
    lower_title = str(title or "").lower()
    structural_cues = (
        "underground threads",
        "thread network",
        "mycelium network",
        "root network",
        "rock layers",
        "cloud pattern",
        "cloud patterns",
        "leaf movement",
        "water shift",
    )
    if " through " in lower_title and any(cue in lower_title for cue in structural_cues):
        score += 6
    current_title = str(story.get("seo_title") or story.get("title") or "").strip().lower()
    if current_title and re.sub(r"\W+", " ", lower_title).strip() == re.sub(r"\W+", " ", current_title).strip():
        score += 10
    if re.search(
        r"\bwhy\b.*\bafter one (?:thread network|root network|rock layer|cloud pattern|leaf movement|water shift)\b",
        lower_title,
    ):
        score -= 5
    if re.search(r"\bwhy\b.*\bafter one\b", lower_title):
        score -= 8
    if re.search(r"\bbefore\s+(?:they|it)\s+remember\b", lower_title):
        score -= 18
    score += _distribution_adjustment(
        candidate, memory.get("winner_patterns") if isinstance((memory or {}).get("winner_patterns"), dict) else None
    )
    if editorial_issues(candidate, include_script=False):
        score -= 60
    return max(0, min(100, score))


def select_best_packaging(story: dict, memory: dict | None = None) -> dict:
    options = generate_packaging_options(story)
    best = None
    scored = []
    fallback_scored = []
    for title in options["titles"][:5]:
        for thumb in options["thumbnail_texts"][:5]:
            for hook in options["hooks"][:3]:
                candidate = {**story, "title": title, "seo_title": title, "thumbnail_text": thumb, "hook": hook}
                issues = editorial_issues(candidate, include_script=False)
                score = score_package_variant(story, title, thumb, hook, memory=memory)
                row = {"score": score, "title": title, "thumbnail_text": thumb, "hook": hook}
                fallback_scored.append(row)
                if issues:
                    continue
                scored.append(row)
                if best is None or score > best["score"]:
                    best = row
    if not scored:
        scored = fallback_scored
        if best is None and scored:
            best = max(scored, key=lambda row: row["score"])
    scored.sort(key=lambda row: row["score"], reverse=True)
    return {
        "best": best
        or {
            "score": 0,
            "title": story.get("title", ""),
            "thumbnail_text": story.get("thumbnail_text", ""),
            "hook": story.get("hook", ""),
        },
        "top_variants": scored[:10],
        "options": options,
    }


def experiment_plan(story: dict, memory: dict | None = None) -> dict:
    memory = memory or {}
    winners = {
        "title_pattern": next(iter((memory.get("winning_title_patterns") or {}).keys()), ""),
        "thumbnail_pattern": next(iter((memory.get("winning_thumbnail_patterns") or {}).keys()), ""),
        "hook_pattern": next(iter((memory.get("winning_hook_patterns") or {}).keys()), ""),
    }
    winning_experiments = memory.get("winning_experiments") or {}
    sample_count = int(memory.get("sample_count") or 0)
    explore_rate = 0.35 if sample_count < 12 else 0.18
    if sample_count >= 30:
        explore_rate = 0.10
    category = str(story.get("category") or "nature").lower()
    digest = hashlib.sha256(
        f"{story.get('id') or story.get('title')}-{category}".encode("utf-8", errors="ignore")
    ).hexdigest()
    axis_seed = int(digest[:8], 16) % 100
    mode = "explore" if axis_seed < int(explore_rate * 100) else "exploit"
    return {
        "mode": mode,
        "explore_rate": explore_rate,
        "winners": winners,
        "winning_experiments": dict(list(winning_experiments.items())[:5]),
        "sample_count": sample_count,
        "assignment": {
            "format": "winner_inspired" if mode == "exploit" and winners["hook_pattern"] else "fresh_variant",
            "hook": "pattern_reuse" if mode == "exploit" and winners["hook_pattern"] else "new_hook",
            "thumbnail": "pattern_reuse" if mode == "exploit" and winners["thumbnail_pattern"] else "new_thumbnail",
            "cta": "specific_question" if mode == "explore" else "follow_for_more",
        },
    }
