"""Magnetic Shorts packaging: title, thumbnail, comment and community hook."""
from __future__ import annotations

import re

from utils.growth_engine import (
    analyze_retention,
    load_format_memory,
    score_package_variant,
    select_best_packaging,
)
from utils.story_intelligence import audit_title, classify_format

ANIMALS = {
    "cow", "cows", "duck", "ducks", "chicken", "chickens", "deer",
    "horse", "horses", "tiger", "tigers", "penguin", "penguins",
    "goat", "goats", "wolf", "wolves", "bear", "bears", "bird",
    "birds", "owl", "owls", "cat", "cats", "dog", "dogs", "lion",
    "lions", "elephant", "elephants", "dolphin", "dolphins", "whale",
    "whales", "parrot", "parrots", "macaw", "macaws", "donkey",
    "donkeys", "sheep", "shark", "sharks", "bee", "bees",
    "butterfly", "butterflies", "ant", "ants", "beetle", "beetles",
    "mantis", "mantises", "dragonfly", "dragonflies", "octopus",
    "octopuses", "seal", "seals", "fox", "foxes", "snake", "snakes",
    "chameleon", "chameleons", "turtle", "turtles", "orangutan",
    "orangutans", "monkey", "monkeys",
    "fungi", "mushroom", "mushrooms", "forest", "forests", "ocean",
    "volcano", "volcanoes", "lava", "storm", "weather", "geology",
    "river", "rivers", "glacier", "ecosystem", "ecosystems", "earth",
    "plant", "plants", "tree", "trees", "coral", "reef",
}
ACTION_VERBS = (
    "fake", "protect", "escape", "remember", "recognize", "call", "hear",
    "hide", "slide", "hunt", "plan", "trick", "warn", "choose", "save",
    "signal", "follow", "digest", "groom", "roll", "bray",
    "erupt", "glow", "flow", "form", "grow", "melt", "freeze",
    "recover", "connect", "communicate", "build", "collapse",
)
CUE_WORDS = (
    "eyes", "ears", "tail", "beak", "wing", "wings", "feet", "paw", "paws", "horn", "horns",
    "sound", "call", "stripe", "feathers", "movement", "cue", "body",
    "nose", "face", "head", "pupil", "pupils", "hoof", "hooves", "fin", "fins",
    "gill", "gills", "antenna", "antennae",
    "lava", "ash", "cloud", "clouds", "roots", "leaf", "leaves",
    "mushroom", "mycelium", "reef", "coral", "wave", "waves",
    "current", "glacier", "rock", "rocks", "crater", "ice",
)
GENERIC_PHRASES = (
    "hiding in plain sight", "another secret", "another signal",
    "amazing fact", "incredible animal", "you won't believe",
    "one visible cue for a reason", "secret hiding in plain sight",
)
SERIES_CATALOG = {
    "animal_myth": "Animal Myths",
    "animal_memory": "Animal Memory",
    "body_superpower": "Body Clues",
    "survival_trick": "Survival Tricks",
    "visual_cue": "Watch The Cue",
    "earth_engine": "Earth Engine",
    "hidden_network": "Hidden Network",
    "rare_nature": "Rare Earth",
    "conservation_signal": "Planet Repair",
    "default": "Nature Signals",
}


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
    return [_clean_title(title) for title in select_best_packaging(story)["options"]["titles"][:10]]


def thumbnail_options(story: dict) -> list[str]:
    return select_best_packaging(story)["options"]["thumbnail_texts"][:10]


def hook_options(story: dict) -> list[str]:
    return select_best_packaging(story)["options"]["hooks"][:5]


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
    has_subject = any(re.search(r"\b" + re.escape(a) + r"\b", text) for a in ANIMALS)
    if has_subject:
        score += 10
        strengths.append("subject_clear")
    else:
        score -= 10
        risks.append("subject_not_clear")
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
        score -= 28
        risks.append("generic_clickbait_language")
    if "?" in title:
        score += 4
        strengths.append("curiosity_question")
    retention_score = analyze_retention(story)["score"]
    score = round(score * 0.65 + retention_score * 0.35)
    score = max(0, min(100, score))
    return {
        "score": score,
        "state": "magnetic" if score >= 82 else ("usable" if score >= 68 else "rewrite_packaging"),
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


def series_name(story: dict) -> str:
    current = str(story.get("series") or "").strip()
    if current:
        return current[:60]
    text = " ".join(str(story.get(k) or "") for k in ("seo_title", "title", "hook", "script")).lower()
    fmt = classify_format(text)
    if any(word in text for word in ("myth", "really", "not true", "isn't true")):
        return SERIES_CATALOG["animal_myth"]
    if fmt in SERIES_CATALOG:
        return SERIES_CATALOG[fmt]
    if extract_cue(story) != "cue":
        return SERIES_CATALOG["visual_cue"]
    return SERIES_CATALOG["default"]


def cta_prompt(story: dict) -> str:
    subject = extract_animal(story)
    cue = extract_cue(story)
    cta = (
        f"Follow for more wild nature clues. Comment the next subject after {subject}."
        if cue == "cue"
        else f"Follow for more wild nature facts. Did you catch the {cue}?"
    )
    return cta[:140]


def replay_prompt(story: dict) -> str:
    cue = extract_cue(story)
    subject = extract_animal(story)
    if cue != "cue":
        return f"End by pointing back to the {cue}, so viewers rewatch the {subject} clip."
    return f"End with the first visual moment again, so viewers rewatch the {subject} clip."


def package_story(story: dict) -> dict:
    out = dict(story)
    memory = load_format_memory()
    selected = select_best_packaging(out, memory=memory)
    best_variant = selected["best"]
    if best_variant:
        out["seo_title"] = best_variant["title"]
        out["title"] = best_variant["title"]
        out["thumbnail_text"] = best_variant["thumbnail_text"]
        out["hook"] = best_variant["hook"]
    titles = title_options(out)
    thumbs = thumbnail_options(out)
    hooks = hook_options(out)
    out["series"] = series_name(out)
    out["cta_prompt"] = cta_prompt(out)
    out["replay_prompt"] = replay_prompt(out)
    packaged_score = score_packaging(out)
    out["packaging"] = {
        **packaged_score,
        "title_options": titles,
        "thumbnail_options": thumbs,
        "hook_options": hooks,
        "selected_variant": best_variant,
        "top_variants": selected["top_variants"],
        "retention": analyze_retention(out),
        "pinned_comment": pinned_comment(out),
        "community_prompt": community_prompt(out),
        "series": out["series"],
        "cta_prompt": out["cta_prompt"],
        "replay_prompt": out["replay_prompt"],
        "principle": "Stop the swipe with a visible cue, then pay it off fast.",
    }
    return out
