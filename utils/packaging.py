"""Magnetic Shorts packaging: title, thumbnail, comment and topic hook."""
from __future__ import annotations

import re

from utils.curiosity_gap import CuriosityGapEngine
from utils.editorial_rules import evaluate_story_package
from utils.growth_engine import (
    analyze_retention,
    experiment_plan,
    load_format_memory,
    select_best_packaging,
)
from utils.loop_engine import LoopGenerator
from utils.swipe_risk import SwipeRiskScore
from utils.story_intelligence import audit_title, classify_format
from utils.subscriber_conversion import (
    contextual_cta,
    debate_prompt,
    score_subscriber_conversion,
    series_identity,
)

SUBJECT_TERMS = {
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
_PACKAGING_CACHE: dict[tuple[str, str], dict] = {}


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]+", text or "")


def _title_case_subject(value: str) -> str:
    return value[:1].upper() + value[1:] if value else "Nature"


def extract_subject(story: dict) -> str:
    text = " ".join(str(story.get(k) or "") for k in ("seo_title", "title", "hook", "script", "category", "topic_hashtag"))
    for token in _words(text.lower()):
        clean = token.replace("'s", "")
        if clean in SUBJECT_TERMS:
            return clean
    return str(story.get("category") or "nature").replace("_", " ").lower()


def extract_animal(story: dict) -> str:
    """Backward-compatible alias; returns the generic subject/topic."""
    return extract_subject(story)


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
    return [_clean_title(title) for title in _select_packaging(story)["options"]["titles"][:10]]


def thumbnail_options(story: dict) -> list[str]:
    return _select_packaging(story)["options"]["thumbnail_texts"][:10]


def hook_options(story: dict) -> list[str]:
    return _select_packaging(story)["options"]["hooks"][:5]


def _cache_key(story: dict) -> tuple[str, str]:
    identity = str(story.get("id") or story.get("_queue_id") or story.get("source_url") or "")
    if not identity:
        identity = "|".join(str(story.get(k) or "") for k in ("title", "hook", "script", "thumbnail_text", "category"))
    return (
        identity[:240],
        "|".join(str(story.get(k) or "")[:120] for k in ("title", "hook", "thumbnail_text")),
    )


def _select_packaging(story: dict, memory: dict | None = None) -> dict:
    key = _cache_key(story)
    if key not in _PACKAGING_CACHE:
        _PACKAGING_CACHE[key] = select_best_packaging(story, memory=memory or load_format_memory())
    return _PACKAGING_CACHE[key]


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
    has_subject = any(re.search(r"\b" + re.escape(a) + r"\b", text) for a in SUBJECT_TERMS)
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


def _package_preflight(story: dict) -> dict:
    hook = str(story.get("hook") or story.get("title") or "")
    thumb = str(story.get("thumbnail_text") or "")
    script = str(story.get("script") or "")
    curiosity = CuriosityGapEngine()
    best_hook = curiosity.choose_for_story(story, {
        "recent_hooks": [
            str(item)
            for item in ((story.get("context") or {}).get("recent_hooks") or [])
        ],
    })
    hook_specificity = min(1.0, max(0.0, best_hook.score / 100))
    duration_hint = max(12, min(35, round(len(_words(script)) / 2.6))) if script else 18
    first_2s = " ".join(_words(script)[:12])
    package = {
        "first_frame_text": thumb,
        "first_frame_text_words": len(thumb.split()),
        "hook": hook,
        "hook_words": len(_words(hook)),
        "first_2s_narration": first_2s,
        "caption_chars_per_second": round(len(script) / max(duration_hint, 1), 2),
        "visual_motion_score": float(story.get("visual_motion_score") or (0.76 if story.get("pexels_download_url") else 0.48)),
        "contrast_score": float(story.get("contrast_score") or 0.74),
        "hook_specificity": hook_specificity,
        "novelty_score": float(story.get("novelty_score") or 0.58),
        "payoff_time_s": min(18, max(8, duration_hint * 0.55)),
        "cta_count": 1 if story.get("cta_prompt") else 0,
    }
    loop_plan = LoopGenerator().plan({"script": script, "hook": hook}, package)
    package["loop_score"] = loop_plan["loop_score"]
    swipe = SwipeRiskScore().score_opening(package)
    rulebook = evaluate_story_package(story, package, story.get("context") or {})
    return {
        "curiosity_gap": best_hook.to_dict(),
        "swipe_risk": swipe,
        "loop_plan": loop_plan,
        "editorial_rulebook": rulebook,
        "preflight_inputs": package,
    }


def pinned_comment(story: dict) -> str:
    subject = extract_subject(story)
    cue = extract_cue(story)
    prompt = debate_prompt(story)
    if cue != "cue":
        return f"Watch the {cue} again. {prompt}"[:280]
    return f"{_title_case_subject(subject)} is the example. {prompt}"[:280]


def community_prompt(story: dict) -> str:
    subject = extract_subject(story)
    return f"Which nature topic should Wild Brief explain next after {subject}?"


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


def series_package(story: dict, memory: dict | None = None) -> dict:
    base = dict(story)
    if not base.get("series"):
        base["series"] = series_name(base)
    return series_identity(base, memory=memory)


def cta_prompt(story: dict) -> str:
    return contextual_cta(story)[:140]


def replay_prompt(story: dict) -> str:
    cue = extract_cue(story)
    subject = extract_subject(story)
    if cue != "cue":
        return f"End by pointing back to the {cue}, so viewers rewatch the {subject} clip."
    return f"End with the first visual moment again, so viewers rewatch the {subject} clip."


def package_story(story: dict) -> dict:
    out = dict(story)
    memory = load_format_memory()
    selected = _select_packaging(out, memory=memory)
    best_variant = selected["best"]
    if best_variant:
        out["seo_title"] = best_variant["title"]
        out["title"] = best_variant["title"]
        out["thumbnail_text"] = best_variant["thumbnail_text"]
        out["hook"] = best_variant["hook"]
    titles = [_clean_title(title) for title in selected["options"]["titles"][:10]]
    thumbs = selected["options"]["thumbnail_texts"][:10]
    hooks = selected["options"]["hooks"][:5]
    series_info = series_package(out, memory=memory)
    out["series"] = series_info["label"]
    out["cta_prompt"] = cta_prompt(out)
    out["replay_prompt"] = replay_prompt(out)
    out["pinned_comment"] = pinned_comment(out)
    out["community_prompt"] = community_prompt(out)
    packaged_score = score_packaging(out)
    preflight = _package_preflight(out)
    if preflight["swipe_risk"]["band"] == "high":
        packaged_score["score"] = max(0, int(packaged_score["score"]) - 8)
        packaged_score["risks"] = list(dict.fromkeys(packaged_score["risks"] + ["high_swipe_risk"]))
    if not preflight["editorial_rulebook"].get("approved"):
        packaged_score["risks"] = list(dict.fromkeys(
            packaged_score["risks"] + list(preflight["editorial_rulebook"].get("violations") or [])
        ))
        if int(packaged_score["score"]) < 74:
            packaged_score["state"] = "rewrite_packaging"
    subscriber_score = score_subscriber_conversion({
        **out,
        "packaging": {
            "pinned_comment": out["pinned_comment"],
            "series_label": series_info["label"],
        },
    }, memory=memory)
    out["packaging"] = {
        **packaged_score,
        "title_options": titles,
        "thumbnail_options": thumbs,
        "hook_options": hooks,
        "selected_variant": best_variant,
        "top_variants": selected["top_variants"],
        "retention": analyze_retention(out),
        "experiment": experiment_plan(out, memory=memory),
        "series_identity": series_info,
        "pinned_comment": out["pinned_comment"],
        "community_prompt": out["community_prompt"],
        "series": out["series"],
        "cta_prompt": out["cta_prompt"],
        "replay_prompt": out["replay_prompt"],
        "subscriber_conversion": subscriber_score,
        "curiosity_gap": preflight["curiosity_gap"],
        "swipe_risk": preflight["swipe_risk"],
        "loop_plan": preflight["loop_plan"],
        "loop_score": preflight["loop_plan"]["loop_score"],
        "editorial_rulebook": preflight["editorial_rulebook"],
        "preflight_inputs": preflight["preflight_inputs"],
        "principle": "Stop the swipe with a visible cue, then pay it off fast.",
    }
    out["subscriber_conversion"] = out["packaging"]["subscriber_conversion"]
    return out
