"""Turn remake backlog items into queue-ready story drafts."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from utils.curiosity_angles import build_curiosity_package
from utils.editorial_guard import editorial_issues
from utils.packaging import extract_action, extract_animal, extract_cue

CATEGORY_HINTS = {
    "farm": ("duck", "duckling", "cow", "goat", "chicken", "horse", "pig", "sheep"),
    "cats": ("cat", "kitten", "feline"),
    "dogs": ("dog", "puppy", "canine", "husky"),
    "birds": ("bird", "owl", "eagle", "parrot", "hummingbird"),
    "ocean": ("whale", "shark", "octopus", "dolphin", "orca", "turtle", "seal"),
    "wildlife": ("bear", "lion", "tiger", "deer", "wolf", "elephant", "leopard"),
    "primates": ("monkey", "macaque", "chimpanzee", "gorilla", "orangutan"),
    "reptiles": ("snake", "lizard", "crocodile", "chameleon", "gecko"),
    "insects": ("bee", "butterfly", "ant", "dragonfly", "beetle"),
    "arctic": ("penguin", "walrus", "polar bear", "seal"),
    "nocturnal": ("bat", "owl", "fox", "hedgehog"),
}


def _clean(text: str) -> str:
    text = re.sub(r"[^\w\s'-]", "", text or "", flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _animal(title: str) -> str:
    lower = title.lower()
    for aliases in CATEGORY_HINTS.values():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}s?\b", lower):
                return alias
    stop = {"baby", "why", "this", "that", "the", "a", "an"}
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]+", title) if w.lower() not in stop]
    return words[0].lower() if words else "animal"


def _subject(animal: str) -> str:
    lower = (animal or "animal").lower()
    irregular = {
        "deer": "Deer",
        "sheep": "Sheep",
        "fish": "Fish",
        "duckling": "Ducklings",
        "baby goat": "Baby goats",
    }
    if lower in irregular:
        return irregular[lower]
    if lower.endswith("s"):
        return lower.capitalize()
    if lower.endswith("y"):
        return f"{lower[:-1].capitalize()}ies"
    if lower.endswith(("ch", "sh", "x")):
        return f"{lower.capitalize()}es"
    return f"{lower.capitalize()}s"


def _category(title: str) -> str:
    lower = title.lower()
    for category, aliases in CATEGORY_HINTS.items():
        if any(re.search(rf"\b{re.escape(alias)}s?\b", lower) for alias in aliases):
            return category
    return "wildlife"


def _shorts_url(video_id: str) -> str:
    return f"https://www.youtube.com/shorts/{video_id}" if video_id else ""


def _source_keys(story: dict) -> set[str]:
    keys: set[str] = set()
    for key in ("source_url", "url", "source_clip_id", "pexels_video_id"):
        value = str(story.get(key) or "").strip().lower()
        if value:
            keys.add(value)
    for parent_key in ("remake_of", "sequel_of"):
        parent = story.get(parent_key) if isinstance(story.get(parent_key), dict) else {}
        video_id = str(parent.get("video_id") or "").strip()
        if video_id:
            keys.add(video_id.lower())
            keys.add(_shorts_url(video_id).lower())
    return keys


def _angle_key(story: dict) -> str:
    return "|".join(
        (
            extract_animal(story).lower(),
            extract_action(story).lower(),
            extract_cue(story).lower(),
            str(story.get("category") or "").lower(),
        )
    )


def _title_key(story: dict) -> str:
    title = str(story.get("seo_title") or story.get("title") or "")
    return re.sub(r"\s+", " ", _clean(title).lower())


def _recommendable_title(title: str) -> bool:
    title = _clean(title)
    if not title:
        return False
    return not editorial_issues({"title": title, "seo_title": title}, include_script=False)


def _clean_source_reference(raw_title: str, replacement: str) -> str:
    raw_title = _clean(raw_title)
    replacement = _clean(replacement)
    return raw_title if _recommendable_title(raw_title) else replacement


def _clean_action_reference(action: str, raw_title: str, replacement: str) -> str:
    action = str(action or "")
    raw_title = _clean(raw_title)
    replacement = _clean(replacement)
    if raw_title and replacement and raw_title.lower() != replacement.lower():
        action = action.replace(raw_title, replacement)
    return _clean(action)


def _title(animal: str, source_title: str) -> str:
    source = _clean(source_title)
    subject = _subject(animal)
    if "remember" in source.lower():
        return f"{subject} remember the face cue"
    if "math" in source.lower():
        return f"{subject} choose the bigger group before they swim"
    if "bottle" in source.lower() or "feeding" in source.lower():
        return f"{subject} follow the feeding cue for a reason"
    if "bury" in source.lower():
        return f"{subject} hide their heads for a reason"
    return f"{subject} reveal one body clue"


def _suggested_hook(suggested: str, animal: str) -> str:
    if not re.search(rf"\b{re.escape(animal)}s?\b", suggested.lower()):
        return ""
    if editorial_issues({"title": suggested, "hook": suggested, "script": suggested}):
        return ""
    return suggested


def _requires_different_animal(remake: dict) -> bool:
    text = " ".join(
        [str(remake.get("action") or "")] + [str(item) for item in (remake.get("instructions") or [])]
    ).lower()
    return "new animal" in text or "different animal" in text


def build_remake_story(remake: dict, *, generated_at: str | None = None) -> dict:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    source_title = str(remake.get("source_title") or remake.get("title") or "")
    animal = _animal(source_title)
    subject = _subject(animal)
    category = str(remake.get("category") or _category(source_title))
    seo_title = _title(animal, source_title)
    suggested = str((remake.get("retention_surgery") or {}).get("suggested_hook") or "")
    hook = _suggested_hook(suggested, animal)
    hook = hook or f"{subject} show why the useful cue matters."
    hook = _clean(hook).rstrip(".") + "."
    source_lower = source_title.lower()
    is_feeding = "feeding" in source_lower or "bottle" in source_lower
    is_math = "math" in source_lower or "number" in source_lower
    if is_math:
        cue = "object group"
        opening_detail = "object group and first choice"
    elif is_feeding:
        cue = "feeding cue"
        opening_detail = "feeding cue and head movement"
    else:
        cue = "visible cue"
        opening_detail = cue
    thumbnail = f"{subject.upper()} {cue.upper()}"
    if is_math:
        script = (
            f"{hook} Watch the {opening_detail} first, because ducklings can follow a small number pattern "
            "before they ever swim. The clue is the group they move toward, then the number fact makes sense "
            "when viewers look back. That gives the Short one clear setup, one visible action, and one reason "
            "to watch the opening again."
        )
    else:
        script = (
            f"{hook} Watch the {opening_detail} first, because that small detail changes how the animal moves "
            "after the setup. The clue appears early, then the behavior makes sense on replay. That gives "
            "viewers one clear setup, one visible action, and one reason to watch the opening again."
        )
    yt_tags = [animal, category, "animal facts", "wildlife", "shorts"]
    angle = build_curiosity_package(
        {
            "title": seo_title,
            "seo_title": seo_title,
            "source_title": source_title,
            "hook": hook,
            "script": script,
            "category": category,
            "yt_tags": yt_tags,
        },
        subject=animal,
        context=source_title,
        force=True,
    )
    if angle:
        seo_title = str(angle["title"])
        hook = str(angle["hook"])
        script = str(angle["script"])
        cue = str(angle["cue"])
        thumbnail = str(angle["thumbnail_text"])
        yt_tags = list(angle.get("yt_tags") or yt_tags)
    clean_source_title = _clean_source_reference(source_title, seo_title)
    clean_action = _clean_action_reference(str(remake.get("action") or ""), source_title, clean_source_title)
    source_id = str(remake.get("source_video_id") or source_title)
    digest = hashlib.sha256(f"remake:{source_id}:{seo_title}".encode("utf-8")).hexdigest()[:16]
    return {
        "id": f"remake-{digest}",
        "fetched_at": generated_at,
        "published_at": generated_at,
        "consumed": False,
        "consumed_at": None,
        "title": seo_title,
        "url": _shorts_url(source_id),
        "source_url": _shorts_url(source_id),
        "source": "Remake Factory",
        "source_license": "Derived analytics brief; new media required before render",
        "category": category,
        "description": f"Watch the {cue} behind this animal behavior: {clean_source_title}",
        "image_url": "",
        "breaking": False,
        "relevance": 9.5,
        "score": 9,
        "safety_penalty": 0,
        "native_lang": "en",
        "seo_title": seo_title,
        "yt_tags": yt_tags,
        "geo_hashtag": "Global",
        "topic_hashtag": category.title(),
        "yt_description": f"{seo_title}. Watch the {cue} first, then replay the opening clue.",
        "thumbnail_text": thumbnail[:32],
        "hook": hook,
        "script": script,
        "lead": script[:400],
        "sentiment": "curious",
        "discovery_hashtags": [category.replace("_", ""), "animals", "animalfacts", "wildlife", "funfacts"],
        "remake_of": {
            "video_id": remake.get("source_video_id", ""),
            "title": clean_source_title,
            "views": remake.get("views", 0),
            "retention": remake.get("retention", 0),
            "growth_score": remake.get("growth_score", 0),
            "action": clean_action,
        },
        "experiments": {
            "hook_style": "outcome_first",
            "script_tone": "conversational",
            "thumbnail_style": "frame_first_side_caption",
        },
        "production_mode": "remake_factory",
    }


def _preserve_operational_fields(rebuilt: dict, existing: dict) -> dict:
    out = dict(rebuilt)
    for key in (
        "autonomy",
        "queue_prune",
        "publish_score",
        "rights_audit",
        "packaging",
        "youtube_brain",
        "agency_gate",
    ):
        if existing.get(key):
            out[key] = existing[key]
    return out


def append_remakes_to_queue(queue: dict, remakes: list[dict], limit: int = 5) -> tuple[dict, list[dict]]:
    stories = list(queue.get("stories") or [])
    remakes_by_source = {
        str(remake.get("source_video_id") or ""): remake
        for remake in remakes
        if str(remake.get("source_video_id") or "")
    }
    for idx, story in enumerate(stories):
        source_id = str((story.get("remake_of") or {}).get("video_id") or "")
        if story.get("consumed") or not (source_id or story.get("production_mode") == "remake_factory"):
            continue
        remake_source = remakes_by_source.get(source_id) or {
            "source_video_id": source_id,
            "source_title": (story.get("remake_of") or {}).get("title") or story.get("title", ""),
            "views": (story.get("remake_of") or {}).get("views", 0),
            "retention": (story.get("remake_of") or {}).get("retention", 0),
            "growth_score": (story.get("remake_of") or {}).get("growth_score", 0),
            "action": (story.get("remake_of") or {}).get("action", ""),
        }
        rebuilt = build_remake_story(remake_source)
        rebuilt["id"] = story.get("id", rebuilt["id"])
        rebuilt["fetched_at"] = story.get("fetched_at", rebuilt["fetched_at"])
        rebuilt["published_at"] = story.get("published_at", rebuilt["published_at"])
        rebuilt = _preserve_operational_fields(rebuilt, story)
        stories[idx] = rebuilt
    existing_ids = {str(item.get("id") or "") for item in stories}
    existing_sources: set[str] = set()
    existing_angles: set[str] = set()
    existing_titles: set[str] = set()
    for item in stories:
        if item.get("consumed"):
            continue
        existing_sources.update(_source_keys(item))
        angle = _angle_key(item)
        if angle:
            existing_angles.add(angle)
        title_key = _title_key(item)
        if title_key:
            existing_titles.add(title_key)
    created = []
    for remake in remakes:
        if len(created) >= limit:
            break
        if _requires_different_animal(remake):
            continue
        source_id = str(remake.get("source_video_id") or "")
        source_candidates = {source_id.lower(), _shorts_url(source_id).lower()} if source_id else set()
        if source_candidates and existing_sources.intersection(source_candidates):
            continue
        story = build_remake_story(remake)
        if story["id"] in existing_ids:
            continue
        story_sources = _source_keys(story)
        if story_sources and existing_sources.intersection(story_sources):
            continue
        story_title = _title_key(story)
        if story_title and story_title in existing_titles:
            continue
        story_angle = _angle_key(story)
        if story_angle and story_angle in existing_angles:
            continue
        stories.append(story)
        created.append(story)
        existing_ids.add(story["id"])
        existing_sources.update(story_sources)
        if story_title:
            existing_titles.add(story_title)
        if story_angle:
            existing_angles.add(story_angle)
    out = dict(queue)
    out["stories"] = stories
    return out, created
