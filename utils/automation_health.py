"""Local automation health audit for Wild Brief."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from utils.content_agency import agency_snapshot
from utils.editorial import rank_candidates
from utils.growth_strategy import load_strategy, ops_guardian_enforced, paused_categories
from utils.humanity_engine import polish_story
from utils.seo_optimizer import _ANIMAL_WORDS, optimise_title, seo_score

_NATURE_SUBJECT_WORDS = {
    "cacti",
    "cactus",
    "cloud",
    "clouds",
    "coral",
    "earth",
    "ecosystem",
    "ecosystems",
    "field",
    "fields",
    "forest",
    "forests",
    "force",
    "forces",
    "fossil",
    "fossils",
    "fungi",
    "fungus",
    "geology",
    "glacier",
    "glaciers",
    "lava",
    "lightning",
    "magnet",
    "magnets",
    "mushroom",
    "mushrooms",
    "ocean",
    "oceans",
    "plant",
    "plants",
    "reef",
    "reefs",
    "river",
    "rivers",
    "rock",
    "rocks",
    "storm",
    "storms",
    "thunder",
    "tree",
    "trees",
    "volcano",
    "volcanoes",
    "weather",
}
_SUBJECT_FRONTLOAD_WORDS = _ANIMAL_WORDS | _NATURE_SUBJECT_WORDS
_SUBJECT_DESCRIPTOR_WORDS = {
    "baby",
    "carnivorous",
    "giant",
    "gray",
    "great",
    "little",
    "mallard",
    "nocturnal",
    "tiny",
    "wild",
    "young",
}


def _safe_json(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _script_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _story_id(story: dict) -> str:
    return str(story.get("id") or story.get("slug") or story.get("source_clip_id") or story.get("title") or "")


def _frontloaded(title: str) -> bool:
    words = re.findall(r"[a-z]+", (title or "").lower())
    if not words:
        return False
    if words[0] in _SUBJECT_FRONTLOAD_WORDS:
        return True
    return len(words) > 1 and words[0] in _SUBJECT_DESCRIPTOR_WORDS and words[1] in _SUBJECT_FRONTLOAD_WORDS


def _health_seo_score(title: str) -> dict:
    scorecard = seo_score(title)
    score = int(scorecard.get("score", 0) or 0)
    issues = [str(issue) for issue in (scorecard.get("issues") or [])]
    if _frontloaded(title) and "animal_not_front_loaded" in issues:
        score += 28
        issues = [issue for issue in issues if issue != "animal_not_front_loaded"]
    return {"score": max(0, min(100, score)), "issues": issues}


def build_health(root: Path | str = ".") -> dict:
    root = Path(root)
    queue = _safe_json(root / "_data" / "stories_queue.json")
    agency_gate = _safe_json(root / "_data" / "agency_gate.json")
    latest = _safe_json(root / "_data" / "analytics" / "latest.json")
    comments = _safe_json(root / "_data" / "analytics" / "comments.json")
    stories = [item for item in (queue.get("stories") or []) if isinstance(item, dict) and not item.get("consumed")]
    categories = Counter(str(item.get("category") or "unknown") for item in stories)
    scripts = [_script_key(str(item.get("script") or "")) for item in stories if item.get("script")]
    duplicate_scripts = len(scripts) - len(set(scripts))

    seo_scores: list[int] = []
    frontloaded = 0
    for item in stories:
        title = str(item.get("seo_title") or item.get("title") or "")
        optimised = optimise_title(
            title,
            hook=str(item.get("hook") or ""),
            script=str(item.get("script") or ""),
            tags=[str(t) for t in (item.get("yt_tags") or [])],
            category=str(item.get("category") or ""),
        )
        seo_scores.append(int(_health_seo_score(optimised)["score"]))
        if _frontloaded(optimised):
            frontloaded += 1

    pending = len(stories)
    held_ids = {str(item.get("id") or "") for item in (agency_gate.get("held_items") or []) if isinstance(item, dict)}
    paused = set(paused_categories(root / "_data" / "ops_guardian.json").keys()) if ops_guardian_enforced() else set()
    publish_ready = sum(
        1
        for item in stories
        if _story_id(item) not in held_ids
        and str(item.get("category") or "").strip().lower() not in paused
        and (item.get("queue_prune") or {}).get("state") == "publish_ready"
        and (item.get("publish_score") or {}).get("approved") is True
        and (item.get("publish_score") or {}).get("state") == "publish_ready"
        and (item.get("editorial") or {}).get("approved") is True
    )
    avg_seo = round(sum(seo_scores) / len(seo_scores), 2) if seo_scores else 0.0
    frontloaded_pct = round(frontloaded * 100 / pending, 2) if pending else 0.0
    polished = [polish_story(item) for item in stories]
    agency = agency_snapshot(rank_candidates(polished), load_strategy(root / "_data" / "analytics" / "latest.json"))
    agency_ready = int((agency.get("decisions") or {}).get("publish_now", 0) or 0)
    issues: list[str] = []
    if pending < 20:
        issues.append("queue_inventory_low")
    if pending and agency_ready == 0 and publish_ready == 0:
        issues.append("no_agency_publish_now_candidate")
    if duplicate_scripts:
        issues.append("duplicate_scripts_in_queue")
    if avg_seo < 90:
        issues.append("seo_average_below_target")
    if frontloaded_pct < 95:
        issues.append("subject_frontload_below_target")
    if latest and latest.get("metric_scope") != "youtube_analytics_and_public_statistics":
        issues.append("youtube_analytics_scope_incomplete")
    if latest and float(latest.get("avg_view_pct", 0) or 0) < 55:
        issues.append("average_retention_needs_attention")

    score = 100
    score -= min(20, duplicate_scripts * 4)
    score -= 15 if pending < 20 else 0
    score -= 12 if "no_agency_publish_now_candidate" in issues else 0
    score -= max(0, int(90 - avg_seo))
    score -= max(0, int(95 - frontloaded_pct))
    score -= 10 if "youtube_analytics_scope_incomplete" in issues else 0
    score -= 8 if "average_retention_needs_attention" in issues else 0
    score = max(0, min(100, score))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "score": score,
        "state": "excellent" if score >= 90 else ("watch" if score >= 75 else "needs_work"),
        "issues": issues,
        "queue": {
            "pending": pending,
            "publish_ready": publish_ready,
            "categories": dict(sorted(categories.items())),
            "duplicate_scripts": duplicate_scripts,
            "missing_scripts": sum(1 for item in stories if not item.get("script")),
            "missing_source": sum(1 for item in stories if not (item.get("source_url") or item.get("url"))),
        },
        "seo": {
            "average_score": avg_seo,
            "animal_frontloaded_pct": frontloaded_pct,
            "subject_frontloaded_pct": frontloaded_pct,
        },
        "agency": agency,
        "analytics": {
            "pulled_at": latest.get("pulled_at", ""),
            "metric_scope": latest.get("metric_scope", ""),
            "total_views": latest.get("total_views", 0),
            "avg_view_pct": latest.get("avg_view_pct", latest.get("avg_view_percentage", 0)),
            "shorts_tracked": latest.get("shorts_tracked", 0),
        },
        "comments": {
            "comments_sampled": comments.get("comments_sampled", 0),
            "question_count": comments.get("question_count", 0),
        },
    }
