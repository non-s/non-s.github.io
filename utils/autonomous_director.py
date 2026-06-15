"""Autonomous channel decision engine.

This module does not pretend to be magic. It turns the channel's own
analytics, queue health and API coverage into explicit operating decisions.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from utils.editorial_guard import editorial_issues


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _slug(text: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return clean[:60] or "wildbrief"


ANIMAL_ALIASES = {
    "ducklings": "ducklings",
    "duckling": "ducklings",
    "ducks": "ducks",
    "duck": "ducks",
    "cows": "cows",
    "cow": "cows",
    "goats": "goats",
    "goat": "goats",
    "chickens": "chickens",
    "chicken": "chickens",
    "deer": "deer",
    "bears": "bears",
    "bear": "bears",
    "elephants": "elephants",
    "elephant": "elephants",
    "cats": "cats",
    "cat": "cats",
    "dogs": "dogs",
    "dog": "dogs",
    "birds": "birds",
    "bird": "birds",
    "whales": "whales",
    "whale": "whales",
    "dolphins": "dolphins",
    "dolphin": "dolphins",
    "tigers": "tigers",
    "tiger": "tigers",
    "lions": "lions",
    "lion": "lions",
    "snakes": "snakes",
    "snake": "snakes",
    "reptiles": "reptiles",
    "reptile": "reptiles",
}

CUE_ALIASES = {
    "face": "face cue",
    "faces": "face cue",
    "math": "number sense",
    "numbers": "number sense",
    "injury": "injury display",
    "injuries": "injury display",
    "tail": "tail signal",
    "wing": "wing signal",
    "wings": "wing signal",
    "feet": "footwork",
    "hooves": "hoof movement",
    "eyes": "eye contact",
    "ears": "ear position",
    "roar": "silent hunting",
    "signal": "alarm call",
    "signals": "alarm call",
}


def _animal_from_title(title: str, category: str) -> str:
    words = re.findall(r"[a-z]+", str(title or "").lower())
    for word in words:
        if word in ANIMAL_ALIASES:
            return ANIMAL_ALIASES[word]
    fallback = str(category or "animals").lower()
    if fallback in {"farm", "wildlife"}:
        return "animals"
    return fallback


def _cue_from_title(title: str) -> str:
    words = re.findall(r"[a-z]+", str(title or "").lower())
    for word in words:
        if word in CUE_ALIASES:
            return CUE_ALIASES[word]
    return "first movement"


def _sequel_brief(title: str) -> str:
    animal = _animal_from_title(title, "wildlife")
    cue = _cue_from_title(title)
    subject = animal.capitalize()
    return f"Create a fresh follow-up with {subject}, a new {cue} detail, and a different fact."


def _recommendable_title(title: str) -> bool:
    title = str(title or "").strip()
    if not title:
        return False
    return not editorial_issues({"title": title, "seo_title": title}, include_script=False)


def subscriber_conversion(latest: dict) -> dict:
    views = int(latest.get("total_views", 0) or 0)
    subs = int(latest.get("subscribers_gained", 0) or 0)
    return {
        "views": views,
        "subscribers_gained": subs,
        "subs_per_1000_views": round(subs * 1000 / views, 3) if views else 0.0,
        "state": "strong" if views and subs * 1000 / views >= 1.0 else "needs_focus",
    }


def _rank_map(mapping: dict, limit: int = 5) -> list[dict]:
    rows = []
    for key, value in (mapping or {}).items():
        try:
            score = float(value or 0)
        except Exception:
            score = 0.0
        rows.append({"value": key, "score": round(score, 3)})
    rows.sort(key=lambda item: item["score"], reverse=True)
    return rows[:limit]


def traffic_source_insight(youtube_intelligence: dict) -> dict:
    reports = {item.get("id"): item for item in youtube_intelligence.get("analytics_reports") or []}
    report = reports.get("traffic_source") or {}
    sample = report.get("sample") or []
    if report.get("status") != "ok" or not sample:
        return {
            "state": "unavailable",
            "reason": report.get("error") or "traffic_source_report_not_ready",
            "dominant_source": "",
        }
    ranked = sorted(sample, key=lambda row: float(row.get("views", 0) or 0), reverse=True)
    return {
        "state": "ready",
        "dominant_source": str(ranked[0].get("insightTrafficSourceType") or ""),
        "top_sources": ranked[:5],
    }


def quota_budget(youtube_intelligence: dict) -> dict:
    issues = youtube_intelligence.get("issues") or []
    reports = youtube_intelligence.get("analytics_reports") or []
    unavailable = [item for item in reports if item.get("status") not in {"ok", "not_run"}]
    risk = 0
    risk += 35 if any("token" in str(issue) for issue in issues) else 0
    risk += min(45, len(unavailable) * 7)
    risk += 10 if (youtube_intelligence.get("coverage_score", 0) or 0) < 50 else 0
    return {
        "risk_score": min(100, risk),
        "state": "watch" if risk >= 35 else "normal",
        "issues": issues[:8],
        "unavailable_reports": [item.get("id", "") for item in unavailable[:8]],
        "policy": "Use read-only reports daily; reserve write quota for scheduled publishing only.",
    }


def sequel_candidates(latest: dict, limit: int = 8) -> list[dict]:
    out = []
    for item in latest.get("top_performers") or []:
        title = str(item.get("title") or "")
        if not _recommendable_title(title):
            continue
        views = int(item.get("views", 0) or 0)
        growth = float(item.get("growth_score", 0) or 0)
        if views < 100 or growth < 120:
            continue
        category = str(item.get("category") or "wildlife")
        story_format = str(item.get("story_format") or "single_fact")
        seed = f"{item.get('video_id')}:{title}:sequel"
        out.append(
            {
                "source_video_id": item.get("video_id", ""),
                "source_title": title,
                "category": category,
                "story_format": story_format,
                "growth_score": round(growth, 3),
                "views": views,
                "sequel_brief": _sequel_brief(title),
                "sequel_id": "sequel-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16],
            }
        )
        if len(out) >= limit:
            break
    return out


def build_sequel_story(candidate: dict, generated_at: str | None = None) -> dict:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    category = str(candidate.get("category") or "wildlife")
    source_title = str(candidate.get("source_title") or "Animal behavior")
    animal = _animal_from_title(source_title, category)
    cue = _cue_from_title(source_title)
    visible_signal = f"the {cue}"
    if str(candidate.get("story_format")) == "animal_memory":
        title = f"{animal.capitalize()} remember the {cue} for a reason"
        hook = f"{animal.capitalize()} remember the {cue} fast."
    else:
        title = f"{animal.capitalize()} rely on the {cue} for a reason"
        hook = f"{animal.capitalize()} rely on the {cue} for survival."
    script = (
        f"{hook} Watch {visible_signal} first, because {animal} change the next decision "
        "around that clue. The setup is visible early, then the behavior makes sense when "
        "viewers look back at the opening shot."
    )
    return {
        "id": str(candidate.get("sequel_id") or "sequel-" + _slug(source_title)),
        "fetched_at": generated_at,
        "published_at": generated_at,
        "consumed": False,
        "consumed_at": None,
        "title": title,
        "seo_title": title[:100],
        "url": f"https://www.youtube.com/shorts/{candidate.get('source_video_id', '')}",
        "source_url": f"https://www.youtube.com/shorts/{candidate.get('source_video_id', '')}",
        "source": "YouTube Analytics sequel",
        "source_license": "Derived analytics brief; new media required before render",
        "category": category,
        "description": f"Fresh follow-up brief from a proven {cue} winner; use new footage and a new fact.",
        "breaking": False,
        "relevance": 9.5,
        "score": 9,
        "safety_penalty": 0,
        "native_lang": "en",
        "yt_tags": [category, "animal facts", "wildlife", "shorts", "sequel"],
        "geo_hashtag": "Global",
        "topic_hashtag": category.title(),
        "thumbnail_text": f"{animal.upper()} {cue.upper()}"[:32],
        "hook": hook,
        "script": script,
        "lead": script[:400],
        "story_format": candidate.get("story_format") or "single_fact",
        "experiments": {
            "hook_style": "outcome_first",
            "script_tone": "conversational",
            "thumbnail_style": "frame_first_side_caption",
            "cta_style": "viewer_request",
        },
        "sequel_of": {
            "video_id": candidate.get("source_video_id", ""),
            "title": source_title,
            "growth_score": candidate.get("growth_score", 0),
            "views": candidate.get("views", 0),
        },
    }


def append_sequels(queue: dict, candidates: list[dict], limit: int = 5) -> tuple[dict, list[dict]]:
    stories = list(queue.get("stories") or [])
    existing_by_source = {
        str((story.get("sequel_of") or {}).get("video_id") or ""): idx
        for idx, story in enumerate(stories)
        if (story.get("sequel_of") or {}).get("video_id")
    }
    existing_source_ids = set(existing_by_source)
    existing_angles: set[tuple[str, str]] = set()
    for story in stories:
        for related_key in ("sequel_of", "remake_of"):
            related = story.get(related_key) or {}
            if isinstance(related, dict) and related.get("video_id"):
                existing_source_ids.add(str(related.get("video_id")))
        for url_key in ("source_url", "url"):
            url = str(story.get(url_key) or "")
            if "/shorts/" in url:
                existing_source_ids.add(url.rsplit("/shorts/", 1)[-1].split("?", 1)[0])
        title = " ".join(str(story.get(key) or "") for key in ("seo_title", "title", "hook"))
        subject = _animal_from_title(title, str(story.get("category") or "wildlife"))
        cue = _cue_from_title(title)
        existing_angles.add((subject, cue))
    existing_ids = {str(story.get("id") or "") for story in stories}
    created = []
    for candidate in candidates:
        source_id = str(candidate.get("source_video_id") or "")
        if not source_id:
            continue
        if source_id in existing_source_ids:
            continue
        candidate_angle = (
            _animal_from_title(str(candidate.get("source_title") or ""), str(candidate.get("category") or "wildlife")),
            _cue_from_title(str(candidate.get("source_title") or "")),
        )
        if candidate_angle in existing_angles:
            continue
        story = build_sequel_story(candidate)
        if source_id in existing_by_source:
            idx = existing_by_source[source_id]
            stories[idx].update(story)
            continue
        if len(created) >= limit:
            continue
        if story["id"] in existing_ids:
            continue
        stories.append(story)
        created.append(story)
        existing_by_source[source_id] = len(stories) - 1
        existing_source_ids.add(source_id)
        existing_angles.add(candidate_angle)
        existing_ids.add(story["id"])
    out = dict(queue)
    out["stories"] = stories
    out["updated_at"] = datetime.now(timezone.utc).isoformat()
    return out, created


def build_director(latest: dict, youtube_intelligence: dict, health: dict, ops: dict, fact_ledger: dict) -> dict:
    category_growth = _rank_map(latest.get("category_avg_growth_score") or {})
    format_growth = _rank_map(latest.get("format_avg_growth_score") or {})
    conversion = subscriber_conversion(latest)
    traffic = traffic_source_insight(youtube_intelligence)
    quota = quota_budget(youtube_intelligence)
    sequels = sequel_candidates(latest)
    paused = [str(item.get("category") or "") for item in ops.get("paused_topics") or []]
    duplicate_risk = int(fact_ledger.get("risk_score", 0) or 0)
    health_score = int(health.get("score", 0) or 0)
    autonomy_score = health_score
    autonomy_score -= 15 if quota["state"] == "watch" else 0
    autonomy_score -= 10 if duplicate_risk >= 60 else 0
    autonomy_score -= 10 if conversion["state"] == "needs_focus" else 0
    autonomy_score = max(0, min(100, autonomy_score))
    decisions = []
    if category_growth:
        decisions.append(f"Double down on {category_growth[0]['value']} until another category beats its growth score.")
    if format_growth:
        decisions.append(f"Favor {format_growth[0]['value']} as the next story format.")
    if conversion["state"] == "needs_focus":
        decisions.append("Add a soft subscriber conversion CTA to strong candidates only.")
    if paused:
        decisions.append("Keep paused categories in recovery mode: " + ", ".join(paused[:4]) + ".")
    if sequels:
        decisions.append("Generate sequels from the top winners before searching unrelated subjects.")
    if traffic["state"] == "ready":
        decisions.append(f"Optimize next scripts for dominant traffic source: {traffic['dominant_source']}.")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "autonomy_score": autonomy_score,
        "state": "autonomous_ready" if autonomy_score >= 80 else "needs_operator_attention",
        "publish_mix": {
            "winner_sequels": 40 if sequels else 20,
            "proven_categories": 35,
            "fresh_experiments": 15,
            "recovery_categories": 10 if paused else 0,
        },
        "subscriber_conversion": conversion,
        "traffic_source": traffic,
        "quota_budget": quota,
        "category_priorities": category_growth,
        "format_priorities": format_growth,
        "sequel_candidates": sequels,
        "duplicate_risk": duplicate_risk,
        "decisions": decisions,
    }
