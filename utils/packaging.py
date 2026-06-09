"""Magnetic Shorts packaging: title, thumbnail, comment and community hook."""
from __future__ import annotations

import re

from utils.story_intelligence import audit_title, classify_format

ANIMALS = {
    "cow", "cows", "duck", "ducks", "chicken", "chickens", "deer",
    "horse", "horses", "tiger", "tigers", "penguin", "penguins",
    "goat", "goats", "wolf", "wolves", "bear", "bears", "bird",
    "birds", "owl", "owls", "cat", "cats", "dog", "dogs", "lion",
    "lions", "elephant", "elephants", "dolphin", "dolphins", "whale",
    "whales", "parrot", "parrots", "macaw", "macaws", "donkey",
    "donkeys", "sheep", "shark", "sharks",
}
ACTION_VERBS = (
    "fake", "protect", "escape", "remember", "recognize", "call", "hear",
    "hide", "slide", "hunt", "plan", "trick", "warn", "choose", "save",
    "signal", "follow", "digest", "groom", "roll", "bray",
)
CUE_WORDS = (
    "eyes", "ears", "tail", "beak", "wing", "wings", "feet", "paw", "paws", "horn", "horns",
    "sound", "call", "stripe", "feathers", "movement", "cue", "body",
    "nose", "face", "head",
)
GENERIC_PHRASES = (
    "hiding in plain sight", "another secret", "another signal",
    "amazing fact", "incredible animal", "you won't believe",
)


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]+", text or "")


def _title_case_animal(value: str) -> str:
    return value[:1].upper() + value[1:] if value else "Animals"


def extract_animal(story: dict) -> str:
    text = " ".join(str(story.get(k) or "") for k in ("seo_title", "title", "hook", "script", "category"))
    for token in _words(text.lower()):
        clean = token.replace("'s", "")
        if clean in ANIMALS:
            return clean
    return str(story.get("category") or "animals").lower()


def extract_action(story: dict) -> str:
    text = " ".join(str(story.get(k) or "") for k in ("seo_title", "title", "hook", "script")).lower()
    for verb in ACTION_VERBS:
        if re.search(r"\b" + re.escape(verb) + r"\b", text):
            return verb
    fmt = classify_format(text)
    if fmt == "animal_memory":
        return "remember"
    if fmt == "body_superpower":
        return "use"
    if fmt == "survival_trick":
        return "survive"
    return "show"


def extract_cue(story: dict) -> str:
    text = " ".join(str(story.get(k) or "") for k in ("seo_title", "title", "hook", "script", "thumbnail_text")).lower()
    for cue in CUE_WORDS:
        if re.search(r"\b" + re.escape(cue) + r"\b", text):
            return cue
    return "cue"


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title or "").strip(" -.,")
    return title if len(title) <= 82 else title[:79].rstrip(" -.,") + "..."


def title_options(story: dict) -> list[str]:
    animal = _title_case_animal(extract_animal(story))
    action = extract_action(story)
    cue = extract_cue(story)
    current = _clean_title(str(story.get("seo_title") or story.get("title") or ""))
    options = [
        current,
        f"{animal} {action} for one reason most people miss",
        f"Why {animal.lower()} {action} is not random",
        f"{animal} {action}: watch the {cue}",
        f"The {cue} that explains why {animal.lower()} {action}",
    ]
    out: list[str] = []
    seen = set()
    for option in options:
        clean = _clean_title(option)
        key = clean.lower()
        if clean and key not in seen:
            out.append(clean)
            seen.add(key)
    return out[:5]


def thumbnail_options(story: dict) -> list[str]:
    animal = extract_animal(story).upper()
    cue = extract_cue(story).upper()
    action = extract_action(story).upper()
    raw = str(story.get("thumbnail_text") or "").upper()
    options = [
        raw,
        f"WATCH THE {cue}",
        f"{animal} {action}",
        "NOT RANDOM",
        "TINY CUE",
    ]
    out: list[str] = []
    seen = set()
    for option in options:
        clean = re.sub(r"[^A-Z0-9 '&-]+", " ", option).strip()
        words = clean.split()
        clean = " ".join(words[:4])
        if clean and clean.lower() not in seen:
            out.append(clean)
            seen.add(clean.lower())
    return out[:5]


def score_packaging(story: dict) -> dict:
    title = str(story.get("seo_title") or story.get("title") or "")
    thumb = str(story.get("thumbnail_text") or "")
    hook = str(story.get("hook") or "")
    text = f"{title} {thumb} {hook}".lower()
    score = 42
    strengths: list[str] = []
    risks: list[str] = []
    if audit_title(title).score >= 74:
        score += 14
        strengths.append("title_shape")
    else:
        risks.append("title_needs_stronger_shape")
    if 2 <= len(thumb.split()) <= 4:
        score += 14
        strengths.append("thumbnail_scannable")
    else:
        risks.append("thumbnail_not_2_4_words")
    if any(re.search(r"\b" + re.escape(v) + r"\b", text) for v in ACTION_VERBS):
        score += 12
        strengths.append("action_word")
    else:
        risks.append("missing_action_word")
    if any(re.search(r"\b" + re.escape(c) + r"\b", text) for c in CUE_WORDS):
        score += 10
        strengths.append("visible_cue")
    else:
        risks.append("missing_visible_cue")
    if any(phrase in text for phrase in GENERIC_PHRASES):
        score -= 18
        risks.append("generic_clickbait_language")
    if "?" in title:
        score += 4
        strengths.append("curiosity_question")
    score = max(0, min(100, score))
    return {
        "score": score,
        "state": "magnetic" if score >= 78 else ("usable" if score >= 62 else "rewrite_packaging"),
        "strengths": strengths,
        "risks": risks,
    }


def pinned_comment(story: dict) -> str:
    animal = extract_animal(story)
    cue = extract_cue(story)
    return (
        f"Did you spot the {cue} before the reveal? "
        f"Comment the next animal you want me to decode after {animal}."
    )[:280]


def community_prompt(story: dict) -> str:
    animal = extract_animal(story)
    return f"Which {animal} behavior should Wild Brief decode next?"


def package_story(story: dict) -> dict:
    out = dict(story)
    titles = title_options(out)
    thumbs = thumbnail_options(out)
    current_score = score_packaging(out)
    best_title = max(titles, key=lambda t: audit_title(t).score) if titles else out.get("title", "")
    if current_score["state"] == "rewrite_packaging" and best_title:
        out["seo_title"] = best_title
        out["title"] = best_title
    if thumbs and ("thumbnail_not_2_4_words" in current_score["risks"] or not out.get("thumbnail_text")):
        out["thumbnail_text"] = thumbs[0] if 2 <= len(thumbs[0].split()) <= 4 else thumbs[1]
    packaged_score = score_packaging(out)
    out["packaging"] = {
        **packaged_score,
        "title_options": titles,
        "thumbnail_options": thumbs,
        "pinned_comment": pinned_comment(out),
        "community_prompt": community_prompt(out),
        "principle": "Stop the swipe with a visible cue, then pay it off fast.",
    }
    return out
