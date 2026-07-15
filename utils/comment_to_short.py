"""Promote high-signal viewer comments into queueable Short ideas."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from utils.curiosity_angles import build_curiosity_package
from utils.editorial_guard import editorial_issues
from utils.packaging import extract_action, extract_animal, extract_cue, package_story
from utils.publish_score import score_story
from utils.youtube_brain import creator_premortem

ANIMAL_ALIASES = {
    "ant": "ants",
    "ants": "ants",
    "bear": "bears",
    "bears": "bears",
    "bird": "birds",
    "birds": "birds",
    "cat": "cats",
    "cats": "cats",
    "dog": "dogs",
    "dogs": "dogs",
    "dolphin": "dolphins",
    "dolphins": "dolphins",
    "duck": "ducks",
    "ducks": "ducks",
    "duckling": "ducklings",
    "ducklings": "ducklings",
    "eagle": "eagles",
    "eagles": "eagles",
    "fox": "foxes",
    "foxes": "foxes",
    "frog": "frogs",
    "frogs": "frogs",
    "lion": "lions",
    "lions": "lions",
    "octopus": "octopuses",
    "octopuses": "octopuses",
    "orca": "orcas",
    "orcas": "orcas",
    "owl": "owls",
    "owls": "owls",
    "penguin": "penguins",
    "penguins": "penguins",
    "shark": "sharks",
    "sharks": "sharks",
    "snake": "snakes",
    "snakes": "snakes",
    "tiger": "tigers",
    "tigers": "tigers",
    "turtle": "turtles",
    "turtles": "turtles",
    "whale": "whales",
    "whales": "whales",
    "wolf": "wolves",
    "wolves": "wolves",
}
CATEGORY_BY_ANIMAL = {
    "ants": "insects",
    "bears": "wildlife",
    "birds": "birds",
    "cats": "cats",
    "dogs": "dogs",
    "dolphins": "ocean",
    "ducks": "farm",
    "ducklings": "farm",
    "eagles": "birds",
    "foxes": "wildlife",
    "frogs": "reptiles",
    "lions": "wildlife",
    "octopuses": "ocean",
    "orcas": "ocean",
    "owls": "birds",
    "penguins": "birds",
    "sharks": "ocean",
    "snakes": "reptiles",
    "tigers": "wildlife",
    "turtles": "reptiles",
    "whales": "ocean",
    "wolves": "wildlife",
}
CUE_BY_ANIMAL = {
    "ants": "antenna cue",
    "bears": "tail cue",
    "birds": "wing cue",
    "cats": "tail cue",
    "dogs": "ear cue",
    "dolphins": "call",
    "ducks": "wing cue",
    "ducklings": "group movement",
    "eagles": "eye cue",
    "foxes": "tail cue",
    "frogs": "call",
    "lions": "ear cue",
    "octopuses": "skin change",
    "orcas": "call",
    "owls": "eye cue",
    "penguins": "flipper cue",
    "sharks": "fin cue",
    "snakes": "head cue",
    "tigers": "ear cue",
    "turtles": "head cue",
    "whales": "call",
    "wolves": "tail cue",
}


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text or "")


def _comment_id(comment: dict) -> str:
    raw = "|".join(_text(comment.get(key)) for key in ("comment_id", "id", "video_id", "text", "comment"))
    return "comment-short-" + hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:16]


def _recommendable_title(title: str) -> bool:
    title = _text(title)
    if not title:
        return False
    return not editorial_issues({"title": title, "seo_title": title}, include_script=False)


def _normal_title(story: dict) -> str:
    title = str(story.get("seo_title") or story.get("title") or "")
    title = re.sub(r"[^\w\s'-]", " ", title.lower(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", title).strip()


def _story_angle(story: dict) -> str:
    return "|".join(
        (
            extract_animal(story).lower(),
            extract_action(story).lower(),
            extract_cue(story).lower(),
            str(story.get("category") or "").lower(),
        )
    )


def _packaged_identity(story: dict) -> tuple[str, str]:
    try:
        packaged = package_story(story)
    except Exception:
        packaged = story
    return _normal_title(packaged), _story_angle(packaged)


def score_comment(comment: dict) -> dict:
    text = _text(comment.get("text") or comment.get("comment"))
    words = _words(text)
    lower = text.lower()
    score = 28.0
    reasons: list[str] = []
    
    # VIP Community Order Command
    if lower.startswith("/wildbrief ") or lower.startswith("!wildbrief "):
        score += 900.0  # Instant priority
        reasons.append("vip_community_order")
        
    if "?" in text:
        score += 24
        reasons.append("viewer_question")
    if any(token in lower for token in ("can you", "do ", "what about", "why", "how")):
        score += 14
        reasons.append("request_language")
    animals = _animals_in_text(lower)
    if animals:
        score += min(18, 6 * len(animals))
        reasons.append("animal_named")
    if re.search(r"\b(?:why|how|what|when|best|clutch|hunt|hunting|noise|number|\d+)\b", lower):
        score += 10
        reasons.append("specific_fact_prompt")
    try:
        likes = int(comment.get("likeCount") or comment.get("likes") or 0)
    except Exception:
        likes = 0
    if likes:
        score += min(14, likes * 2)
        reasons.append("liked_by_viewers")
    if len(words) < 4:
        score -= 18
        reasons.append("too_short")
    if len(words) > 45:
        score -= 8
        reasons.append("too_long")
    if any(token in lower for token in ("subscribe", "http", "crypto", "giveaway")):
        score -= 40
        reasons.append("spam_risk")
    author = str(comment.get("author") or "").strip().lower()
    if "wildbrief" in author or "wild-brief" in author:
        score -= 35
        reasons.append("channel_self_prompt")
    return {
        "score": round(max(0.0, min(100.0, score)), 2),
        "reasons": reasons,
        "animals": animals,
        "text": text,
    }


def _animals_in_text(lower: str) -> list[str]:
    animals: set[str] = set()
    if "big cat" in lower or "predator" in lower:
        animals.add("lions")
    for word in re.findall(r"[a-z]+", lower):
        animal = ANIMAL_ALIASES.get(word)
        if animal:
            animals.add(animal)
    if "lions" in animals and ("big cat" in lower or "predator" in lower):
        animals.discard("cats")
    return sorted(animals)


def _category_for(animal: str, comment_text: str) -> str:
    if animal == "lions" and re.search(r"\b(?:big cat|predator|hunt|hunting)\b", comment_text.lower()):
        return "wildlife"
    return CATEGORY_BY_ANIMAL.get(animal, "wildlife")


def _cue_for(animal: str, comment_text: str) -> str:
    lower = comment_text.lower()
    if animal == "ducklings" and re.search(r"\b(?:clutch|number|\d+)\b", lower):
        return "group movement"
    if animal == "lions" and re.search(r"\b(?:hunt|hunting|noise)\b", lower):
        return "silent cue"
    return CUE_BY_ANIMAL.get(animal, "visible cue")


def _title_for(animal: str, cue: str, comment_text: str) -> str:
    subject = animal.title()
    lower = comment_text.lower()
    if animal == "ducklings" and re.search(r"\b(?:clutch|number|\d+)\b", lower):
        return "Ducklings follow the group before they swim"
    if animal == "lions" and re.search(r"\b(?:big cat|predator|hunt|hunting|noise)\b", lower):
        return "Lions keep the hunt quiet for a reason"
    return f"{subject} follow the {cue} for a reason"


def _script_for(title: str, animal: str, cue: str, comment_text: str) -> tuple[str, str]:
    if animal == "ducklings":
        hook = "Ducklings follow the group before they swim."
        script = (
            f"{hook} Watch the group movement first, because the useful clue is not one perfect "
            "number; it is whether the whole clutch stays close enough to follow the mother. "
            "The group shape tells you when the ducklings are ready to move."
        )
        return hook, script
    if animal == "lions":
        hook = "Lions keep the hunt quiet for a reason."
        script = (
            f"{hook} Watch the ears and body first, because sound can warn prey before the chase "
            "even starts. The quiet moment is part of the hunting setup, not an empty pause."
        )
        return hook, script
    subject = animal.title()
    hook = f"{subject} follow the {cue} for a reason."
    script = (
        f"{hook} Watch the {cue} first, because that small signal changes what happens next. "
        "The useful part is timing: the cue shows up early, then the behavior makes sense "
        "when viewers look back at the opening shot."
    )
    return hook, script


def _directly_publishable(candidate: dict) -> bool:
    packaged = package_story({**candidate, "studio_state": "comment_idea"})
    publish = score_story(packaged)
    brain = creator_premortem(packaged)
    packaging = packaged.get("packaging") or {}
    return (
        publish.get("approved") is True
        and publish.get("state") == "publish_ready"
        and not (brain.get("risks") or [])
        and packaging.get("state") != "rewrite_packaging"
        and not (packaging.get("risks") or [])
    )


def build_comment_short_candidate(comment: dict, markers: list[dict] | None = None) -> dict:
    scored = score_comment(comment)
    text = scored["text"]
    animal = (scored["animals"] or ["nature"])[0]
    source_video = _text(comment.get("video_id"))
    candidate_id = _comment_id(comment)
    author = _text(comment.get("authorDisplayName") or comment.get("author") or "A viewer")
    cue = _cue_for(animal, text)
    title = _title_for(animal, cue, text) if animal != "nature" else "Nature reveals one clue viewers asked about"
    hook, script = (
        _script_for(title, animal, cue, text)
        if animal != "nature"
        else (
            "A viewer asked about one nature clue.",
            "A viewer asked about one nature clue. Watch the visible cue first, because the answer is easier to spot when the setup is clear.",
        )
    )
    category = _category_for(animal, text) if animal != "nature" else "wildlife"
    if animal != "nature":
        angle = build_curiosity_package(
            {
                "title": title,
                "seo_title": title,
                "hook": hook,
                "script": script,
                "category": category,
                "source_comment": text,
                "yt_tags": [animal],
            },
            subject=animal,
            context=text,
            force=True,
        )
        if angle:
            title = str(angle["title"])
            hook = str(angle["hook"])
            script = str(angle["script"])
            cue = str(angle["cue"])
            thumbnail_text = str(angle["thumbnail_text"])
            yt_tags = list(angle.get("yt_tags") or [animal, "viewer question", "nature facts"])
        else:
            thumbnail_text = f"{animal.upper()} {cue.upper()}"[:28]
            yt_tags = [animal, "viewer question", "nature facts"]
    else:
        thumbnail_text = "NATURE ANSWER"
        yt_tags = [animal, "viewer question", "nature facts"]
    related = ""
    for marker in markers or []:
        if _text(marker.get("video_id")) == source_video:
            candidate_title = _text(marker.get("title"))
            related = candidate_title if _recommendable_title(candidate_title) else ""
            break
    prompt = text[:180].rstrip(".")
    source_url = f"https://www.youtube.com/shorts/{source_video}?comment={candidate_id[-12:]}" if source_video else ""
    return {
        "id": candidate_id,
        "source": "YouTube comment idea",
        "source_url": source_url,
        "url": source_url,
        "source_license": "Comment-derived editorial prompt; new licensed media required before render",
        "source_video_id": source_video,
        "source_title": related,
        "source_comment": text[:500],
        "title": title,
        "seo_title": title,
        "category": category,
        "description": f"Viewer question seed: {prompt}",
        "hook": hook,
        "script": script,
        "thumbnail_text": thumbnail_text,
        "yt_tags": yt_tags,
        "score": scored["score"],
        "comment_score": scored,
        "vip_author": author if "vip_community_order" in scored["reasons"] else "",
        "comment_context": {
            "video_id": source_video,
            "published_at": comment.get("publishedAt", ""),
            "author": comment.get("author", ""),
            "parent_comment_id": str(comment.get("comment_id") or comment.get("id") or ""),
        },
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def build_candidates(comments_payload: dict, markers: list[dict] | None = None) -> list[dict]:
    raw = (
        comments_payload.get("raw_comments")
        or comments_payload.get("top_comments")
        or comments_payload.get("comments")
        or []
    )
    candidates = [build_comment_short_candidate(item, markers) for item in raw if isinstance(item, dict)]
    return sorted(candidates, key=lambda item: item.get("score", 0), reverse=True)


def merge_into_queue(queue: dict, candidates: list[dict], *, min_score: float = 64.0, max_items: int = 6) -> dict:
    stories = list(queue.get("stories") or [])
    existing_indexes = {
        str(item.get("id")): index for index, item in enumerate(stories) if isinstance(item, dict) and item.get("id")
    }
    seen = set(existing_indexes)
    seen_titles = {_normal_title(item) for item in stories if isinstance(item, dict)}
    seen_angles = {_story_angle(item) for item in stories if isinstance(item, dict)}
    added = 0
    updated = 0
    removed = 0
    remove_ids: set[str] = set()
    for candidate in candidates:
        if added >= max_items:
            break
        candidate_id = str(candidate.get("id") or "")
        if float(candidate.get("score") or 0) < min_score:
            continue
        if not _directly_publishable(candidate):
            if candidate_id in existing_indexes:
                index = existing_indexes[candidate_id]
                existing = stories[index] if isinstance(stories[index], dict) else {}
                if existing.get("studio_state") == "comment_idea":
                    remove_ids.add(candidate_id)
                    removed += 1
            continue
        if candidate_id in existing_indexes:
            index = existing_indexes[candidate_id]
            existing = stories[index] if isinstance(stories[index], dict) else {}
            if existing.get("studio_state") == "comment_idea":
                refreshed = {**existing, **candidate}
                refreshed["studio_state"] = "comment_idea"
                refreshed["comment_to_short"] = {
                    **(existing.get("comment_to_short") or {}),
                    "score": candidate.get("score", 0),
                    "source_video_id": candidate.get("source_video_id", ""),
                    "queued_at": (existing.get("comment_to_short") or {}).get("queued_at")
                    or datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                stories[index] = refreshed
                updated += 1
            continue
        packaged_title, packaged_angle = _packaged_identity(candidate)
        if packaged_title in seen_titles or packaged_angle in seen_angles:
            continue
        item = dict(candidate)
        item["studio_state"] = "comment_idea"
        item["comment_to_short"] = {
            "score": candidate.get("score", 0),
            "source_video_id": candidate.get("source_video_id", ""),
            "queued_at": datetime.now(timezone.utc).isoformat(),
        }
        stories.append(item)
        seen.add(str(item.get("id")))
        existing_indexes[str(item.get("id"))] = len(stories) - 1
        if packaged_title:
            seen_titles.add(packaged_title)
        if packaged_angle:
            seen_angles.add(packaged_angle)
        added += 1
    out = dict(queue)
    if remove_ids:
        stories = [
            story for story in stories if not (isinstance(story, dict) and str(story.get("id") or "") in remove_ids)
        ]
    out["stories"] = stories
    out["comment_to_short_added"] = added
    out["comment_to_short_updated"] = updated
    out["comment_to_short_removed"] = removed
    out["updated_at"] = datetime.now(timezone.utc).isoformat()
    return out
