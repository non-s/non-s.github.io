"""Turn remake backlog items into queue-ready story drafts."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone


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


def _category(title: str) -> str:
    lower = title.lower()
    for category, aliases in CATEGORY_HINTS.items():
        if any(re.search(rf"\b{re.escape(alias)}s?\b", lower) for alias in aliases):
            return category
    return "wildlife"


def _title(animal: str, source_title: str) -> str:
    source = _clean(source_title)
    if "remember" in source.lower():
        return f"{animal.capitalize()} remember more than you think"
    if "math" in source.lower():
        return f"{animal.capitalize()} use numbers before you notice"
    if "bottle" in source.lower() or "feeding" in source.lower():
        return f"{animal.capitalize()} do not just want milk"
    if "bury" in source.lower():
        return f"{animal.capitalize()} hide their heads for a reason"
    return f"{animal.capitalize()} have one hidden trick viewers missed"


def build_remake_story(remake: dict, *, generated_at: str | None = None) -> dict:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    source_title = str(remake.get("source_title") or remake.get("title") or "")
    animal = _animal(source_title)
    category = str(remake.get("category") or _category(source_title))
    seo_title = _title(animal, source_title)
    suggested = str((remake.get("retention_surgery") or {}).get("suggested_hook") or "")
    hook = suggested if re.search(rf"\b{re.escape(animal)}s?\b", suggested.lower()) else ""
    hook = hook or f"{animal.capitalize()} do this for one hidden reason."
    hook = _clean(hook).rstrip(".") + "."
    source_signal = _clean(source_title)[:90] or seo_title
    script = (
        f"{hook} Watch the first movement, because the detail is easy to miss. "
        f"The original topic pulled attention with this angle: {source_signal}. This remake cuts straight "
        f"to the animal's visible payoff. One body cue, one reason, one surprise: "
        f"that is the version viewers can understand before they swipe."
    )
    source_id = str(remake.get("source_video_id") or source_title)
    digest = hashlib.sha256(f"remake:{source_id}:{seo_title}".encode("utf-8")).hexdigest()[:16]
    return {
        "id": f"remake-{digest}",
        "fetched_at": generated_at,
        "published_at": generated_at,
        "consumed": False,
        "consumed_at": None,
        "title": source_title,
        "url": f"https://www.youtube.com/shorts/{source_id}" if source_id else "",
        "source": "Remake Factory",
        "category": category,
        "description": f"Remake draft from proven Wild Brief topic: {source_title}",
        "image_url": "",
        "breaking": False,
        "relevance": 9.5,
        "score": 9,
        "safety_penalty": 0,
        "native_lang": "en",
        "seo_title": seo_title,
        "yt_tags": [animal, category, "animal facts", "wildlife", "shorts"],
        "geo_hashtag": "Global",
        "topic_hashtag": category.title(),
        "yt_description": f"{seo_title}. A sharper remake of a proven Wild Brief topic.",
        "thumbnail_text": _clean(seo_title).upper()[:32],
        "hook": hook,
        "script": script,
        "lead": script[:400],
        "sentiment": "curious",
        "discovery_hashtags": [category.replace("_", ""), "animals", "animalfacts", "wildlife", "funfacts"],
        "remake_of": {
            "video_id": remake.get("source_video_id", ""),
            "title": source_title,
            "views": remake.get("views", 0),
            "retention": remake.get("retention", 0),
            "growth_score": remake.get("growth_score", 0),
            "action": remake.get("action", ""),
        },
        "experiments": {
            "hook_style": "outcome_first",
            "script_tone": "conversational",
            "thumbnail_style": "dynamic_text",
        },
        "production_mode": "remake_factory",
    }


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
        stories[idx] = rebuilt
    existing_ids = {str(item.get("id") or "") for item in stories}
    existing_sources = {
        str((item.get("remake_of") or {}).get("video_id") or "")
        for item in stories
    }
    created = []
    for remake in remakes:
        if len(created) >= limit:
            break
        source_id = str(remake.get("source_video_id") or "")
        if source_id and source_id in existing_sources:
            continue
        story = build_remake_story(remake)
        if story["id"] in existing_ids:
            continue
        stories.append(story)
        created.append(story)
        existing_ids.add(story["id"])
        if source_id:
            existing_sources.add(source_id)
    out = dict(queue)
    out["stories"] = stories
    return out, created
