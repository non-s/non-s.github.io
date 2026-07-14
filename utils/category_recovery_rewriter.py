"""Rewrite paused-category stories into stricter recovery-safe formats."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from utils.retention_surgeon import diagnose
from utils.story_intelligence import classify_format

CAT_RECOVERY_ANGLES = [
    {
        "key": "whiskers",
        "title": "Why cat whiskers change the whole story",
        "hook": "Cats use their whiskers like a measuring tool.",
        "format": "body_superpower",
        "thumb": "WHISKER SIGNAL",
        "visible": "whiskers",
    },
    {
        "key": "tail",
        "title": "What a cat's tail tells you before it moves",
        "hook": "A cat's tail is the first signal to watch.",
        "format": "animal_memory",
        "thumb": "TAIL SIGNAL",
        "visible": "tail",
    },
    {
        "key": "ears",
        "title": "Why cat ears give away the real mood",
        "hook": "Cats give away the answer with their ears first.",
        "format": "animal_memory",
        "thumb": "EAR CLUE",
        "visible": "ears",
    },
    {
        "key": "paws",
        "title": "Why cat paws land almost silently",
        "hook": "Cat paws are built for quiet, exact movement.",
        "format": "body_superpower",
        "thumb": "QUIET PAWS",
        "visible": "paws",
    },
    {
        "key": "sleep",
        "title": "Why cats sleep like they are still on watch",
        "hook": "Cats sleep this way to protect energy and stay ready.",
        "format": "animal_memory",
        "thumb": "SLEEP SIGNAL",
        "visible": "sleep posture",
    },
    {
        "key": "groom",
        "title": "Why cats groom after tense moments",
        "hook": "Cats groom to control scent, stress, and social trust.",
        "format": "animal_memory",
        "thumb": "GROOMING CLUE",
        "visible": "grooming pause",
    },
    {
        "key": "jump",
        "title": "Why cats jump like their legs are springs",
        "hook": "Cats jump well because their back legs load like springs.",
        "format": "body_superpower",
        "thumb": "SPRING LEGS",
        "visible": "back legs",
    },
    {
        "key": "box",
        "title": "Why cats choose boxes before open space",
        "hook": "Cats choose boxes because tight walls feel safer.",
        "format": "animal_memory",
        "thumb": "BOX LOGIC",
        "visible": "body position",
    },
]

DOG_RECOVERY_ANGLES = [
    {
        "key": "nose",
        "title": "Why a dog's nose changes the whole story",
        "hook": "Dogs read the world through scent before sight.",
        "format": "body_superpower",
        "thumb": "NOSE CLUE",
        "visible": "nose",
    },
    {
        "key": "tail",
        "title": "What a dog's tail says before the bark",
        "hook": "A dog's tail is a signal, not a simple happiness meter.",
        "format": "animal_memory",
        "thumb": "TAIL SIGNAL",
        "visible": "tail",
    },
    {
        "key": "paws",
        "title": "Why dog paws explain the move",
        "hook": "Dog paws carry more information than most people notice.",
        "format": "body_superpower",
        "thumb": "PAW CLUE",
        "visible": "paws",
    },
    {
        "key": "play",
        "title": "Why dog play is more serious than it looks",
        "hook": "Dogs use play to practice timing, trust, and control.",
        "format": "animal_memory",
        "thumb": "PLAY SIGNAL",
        "visible": "first playful move",
    },
    {
        "key": "memory",
        "title": "Why dogs remember more than the moment",
        "hook": "Dogs connect faces, voices, and routines into memory.",
        "format": "animal_memory",
        "thumb": "DOG MEMORY",
        "visible": "face and posture",
    },
    {
        "key": "cool",
        "title": "How dogs cool down without sweating like us",
        "hook": "Dogs cool themselves through panting, paws, and posture.",
        "format": "body_superpower",
        "thumb": "COOLING TRICK",
        "visible": "mouth and paws",
    },
    {
        "key": "yawn",
        "title": "Why a dog yawn can calm the room",
        "hook": "A dog yawn can be a calming signal, not just tiredness.",
        "format": "animal_memory",
        "thumb": "YAWN SIGNAL",
        "visible": "yawn",
    },
]

RECOVERY_VARIANTS = [
    {
        "title_suffix": "in the first second",
        "body": "The clue is not the cute part; it is the timing of the movement.",
        "payoff": "That makes the Short feel observed, not copied.",
    },
    {
        "title_suffix": "before the obvious moment",
        "body": "The best part is the tiny pause before the action starts.",
        "payoff": "That is the difference between a pet clip and a real animal read.",
    },
    {
        "title_suffix": "when the body freezes",
        "body": "Freeze the frame there and the behavior suddenly makes sense.",
        "payoff": "One visible cue is stronger than three loose facts.",
    },
    {
        "title_suffix": "that most people miss",
        "body": "Most viewers watch the face, but the useful signal is smaller.",
        "payoff": "That small detail gives the video a reason to exist.",
    },
    {
        "title_suffix": "right before the move",
        "body": "The movement looks random until you notice the setup.",
        "payoff": "This keeps the hook specific and the payoff immediate.",
    },
]


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text or ""))


def _recovery_angle(story: dict, angles: list[dict]) -> dict:
    text = f"{story.get('seo_title', '')} {story.get('title', '')} {story.get('script', '')}".lower()
    for angle in angles:
        if angle["key"] in text:
            return angle
    seed = str(story.get("id") or story.get("title") or "animal")
    idx = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(angles)
    return angles[idx]


def _variant(story: dict) -> dict:
    seed = str(story.get("id") or story.get("title") or "cat")
    idx = int(hashlib.sha256(f"variant:{seed}".encode("utf-8")).hexdigest(), 16) % len(RECOVERY_VARIANTS)
    return RECOVERY_VARIANTS[idx]


def _source_signal(story: dict) -> str:
    original = str(
        story.get("title")
        or ((story.get("category_recovery_rewrite") or {}).get("before") or {}).get("title")
        or story.get("seo_title")
        or ""
    )
    clean = re.sub(r"[^A-Za-z0-9' ]+", " ", original)
    words = [
        word.lower()
        for word in clean.split()
        if word.lower() not in {"why", "cats", "cat", "the", "this", "their", "really", "just"}
    ]
    return " ".join(words[:4]) or "small movement"


def recover_story(story: dict, plan: dict | None = None) -> tuple[dict, bool]:
    """Return a recovery-safe story copy for paused categories."""
    plan = plan or {}
    category = str(story.get("category") or "").lower()
    if category not in {"cats", "dogs"}:
        return dict(story), False
    out = dict(story)
    angles = CAT_RECOVERY_ANGLES if category == "cats" else DOG_RECOVERY_ANGLES
    subject = "cat" if category == "cats" else "dog"
    angle = _recovery_angle(story, angles)
    variant = _variant(story)
    source_signal = _source_signal(story)
    title = f"{angle['title']} {variant['title_suffix']}"
    hook = angle["hook"]
    script = (
        f"{hook} Watch the first second: the body pauses, then the {angle['visible']} gives the clue. "
        f"In this clip, the recovery angle is {source_signal}. {variant['body']} "
        f"That visible cue is the whole story, so the Short opens on the {subject} "
        f"instead of stretching the setup. {variant['payoff']}"
    )
    if _word_count(script) > 95:
        words = re.findall(r"[A-Za-z0-9']+", script)[:95]
        script = " ".join(words).rstrip(" ,") + "."
    experiments = dict(out.get("experiments") or {})
    experiments["hook_style"] = "outcome_first"
    out.update(
        {
            "seo_title": title,
            "hook": hook,
            "script": script,
            "lead": script[:400],
            "thumbnail_text": angle["thumb"][:32],
            "story_format": angle["format"],
            "experiments": experiments,
            "category_recovery_rewrite": {
                "at": datetime.now(timezone.utc).isoformat(),
                "category": category,
                "angle": angle["key"],
                "variant": variant["title_suffix"],
                "source_signal": source_signal,
                "before": {
                    "title": story.get("seo_title") or story.get("title") or "",
                    "format": story.get("story_format")
                    or classify_format(f"{story.get('title', '')} {story.get('hook', '')} {story.get('script', '')}"),
                    "retention": diagnose(story),
                },
                "after": {
                    "format": angle["format"],
                    "retention": diagnose({**out, "script": script, "hook": hook}),
                },
                "rules": plan.get("rules") or [],
            },
        }
    )
    return out, True


def recover_queue(
    queue: dict, held_ids: set[str], recovery_plans: dict[str, dict] | None = None, limit: int = 50
) -> tuple[dict, list[dict]]:
    recovery_plans = recovery_plans or {}
    stories = []
    changed = []
    for story in queue.get("stories") or []:
        story_id = str(story.get("id") or "")
        needs_refresh = bool(story.get("category_recovery_rewrite"))
        if story.get("consumed") or (story_id not in held_ids and not needs_refresh) or len(changed) >= limit:
            stories.append(story)
            continue
        updated, did_change = recover_story(story, recovery_plans.get(str(story.get("category") or "").lower()))
        stories.append(updated)
        if did_change:
            changed.append(
                {
                    "id": story_id,
                    "category": updated.get("category", ""),
                    "title": updated.get("seo_title") or updated.get("title", ""),
                    "format": updated.get("story_format", ""),
                    "angle": (updated.get("category_recovery_rewrite") or {}).get("angle", ""),
                }
            )
    out = dict(queue)
    out["stories"] = stories
    out["updated_at"] = datetime.now(timezone.utc).isoformat()
    return out, changed
