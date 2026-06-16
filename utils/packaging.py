"""Magnetic Shorts packaging: title, thumbnail, comment and topic hook."""

from __future__ import annotations

import re

from utils.curiosity_angles import CURIOUS_CUE_WORDS, build_curiosity_package, is_generic_movement_copy
from utils.curiosity_gap import CuriosityGapEngine
from utils.editorial_guard import editorial_issues
from utils.editorial_rules import evaluate_story_package
from utils.growth_engine import (
    analyze_retention,
    experiment_plan,
    load_format_memory,
    select_best_packaging,
)
from utils.loop_engine import LoopGenerator
from utils.story_intelligence import audit_title, classify_format
from utils.subscriber_conversion import (
    contextual_cta,
    debate_prompt,
    score_subscriber_conversion,
    series_identity,
)
from utils.swipe_risk import SwipeRiskScore

SUBJECT_TERMS = {
    "atmosphere",
    "cow",
    "cows",
    "duck",
    "ducks",
    "duckling",
    "ducklings",
    "chicken",
    "chickens",
    "deer",
    "horse",
    "horses",
    "tiger",
    "tigers",
    "penguin",
    "penguins",
    "goat",
    "goats",
    "wolf",
    "wolves",
    "bear",
    "bears",
    "bird",
    "birds",
    "owl",
    "owls",
    "cat",
    "cats",
    "dog",
    "dogs",
    "lion",
    "lions",
    "elephant",
    "elephants",
    "dolphin",
    "dolphins",
    "whale",
    "whales",
    "parrot",
    "parrots",
    "macaw",
    "macaws",
    "donkey",
    "donkeys",
    "sheep",
    "shark",
    "sharks",
    "bee",
    "bees",
    "butterfly",
    "butterflies",
    "ant",
    "ants",
    "beetle",
    "beetles",
    "mantis",
    "mantises",
    "dragonfly",
    "dragonflies",
    "octopus",
    "octopuses",
    "seal",
    "seals",
    "fox",
    "foxes",
    "snake",
    "snakes",
    "chameleon",
    "chameleons",
    "turtle",
    "turtles",
    "orangutan",
    "orangutans",
    "monkey",
    "monkeys",
    "fungi",
    "mushroom",
    "mushrooms",
    "forest",
    "forests",
    "ocean",
    "volcano",
    "volcanoes",
    "lava",
    "storm",
    "weather",
    "geology",
    "river",
    "rivers",
    "glacier",
    "ecosystem",
    "ecosystems",
    "earth",
    "fossil",
    "plant",
    "plants",
    "tree",
    "trees",
    "coral",
    "reef",
    "lightning",
    "mountain",
    "mountains",
    "mineral",
    "minerals",
    "rock",
    "rocks",
}
ACTION_VERBS = (
    "fake",
    "protect",
    "escape",
    "remember",
    "recognize",
    "call",
    "hear",
    "hide",
    "slide",
    "hunt",
    "plan",
    "trick",
    "warn",
    "aim",
    "carry",
    "carries",
    "cover",
    "covered",
    "choose",
    "save",
    "signal",
    "follow",
    "rely",
    "digest",
    "groom",
    "roll",
    "bray",
    "erupt",
    "glow",
    "flow",
    "form",
    "grow",
    "melt",
    "freeze",
    "recover",
    "connect",
    "communicate",
    "build",
    "built",
    "collapse",
    "coordinate",
    "count",
    "dance",
    "explode",
    "fly",
    "judge",
    "leave",
    "leaves",
    "lay",
    "lays",
    "make",
    "record",
    "reveal",
    "wear",
    "cool",
    "compare",
    "carve",
    "detect",
    "feel",
    "imprint",
    "lock",
    "measure",
    "send",
    "sample",
    "sense",
    "smell",
    "stabilize",
    "store",
    "steer",
    "taste",
    "track",
    "trap",
    "wash",
)
CUE_WORDS = (
    *CURIOUS_CUE_WORDS,
    "ear position",
    "ear movement",
    "head movement",
    "hand movement",
    "tail position",
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
    "eyes",
    "ears",
    "ear",
    "tail",
    "beak",
    "wing",
    "wings",
    "feet",
    "paw",
    "paws",
    "horn",
    "horns",
    "sound",
    "call",
    "stripe",
    "feathers",
    "movement",
    "cue",
    "body",
    "nose",
    "face",
    "head",
    "pupil",
    "pupils",
    "hoof",
    "hooves",
    "fin",
    "fins",
    "gill",
    "gills",
    "antenna",
    "antennae",
    "hand",
    "hands",
    "arm",
    "arms",
    "leg",
    "legs",
    "flipper",
    "flippers",
    "whisker",
    "whiskers",
    "lava",
    "ash",
    "cloud",
    "clouds",
    "canopy shift",
    "canopy",
    "underground threads",
    "thread",
    "threads",
    "root network",
    "roots",
    "mycelium",
    "cap",
    "caps",
    "spore",
    "spores",
    "leaf",
    "leaf movement",
    "leaves",
    "mushroom",
    "object",
    "objects",
    "group",
    "groups",
    "reef",
    "coral",
    "wave",
    "waves",
    "current",
    "glacier",
    "rock",
    "rocks",
    "crater",
    "ice",
)
GENERIC_PHRASES = (
    "hiding in plain sight",
    "another secret",
    "another signal",
    "amazing fact",
    "incredible animal",
    "you won't believe",
    "one visible cue for a reason",
    "secret hiding in plain sight",
    "signal cue",
    "turn the detail into the clue",
    "reveal the next move through movement",
    "rely on body posture",
    "recognize faces through body posture",
    "signal the next move with body posture",
    "through body cue",
    "signal the next move with detail",
    "watch the detail when",
    "the detail that explains",
    "recognize faces through tail",
    "signal the next move with movement",
    "rely on movement to signal",
    "recognize faces through ear",
    "recognize faces through hand",
    "recognize faces through flipper",
    "recognize faces through beak",
    "recognize faces through wing",
    "recognize signals through body cue",
    "recognize signals through body posture",
    "recognize signals through ear position",
    "recognize signals through head movement",
    "recognize signals through fin movement",
    "recognize signals through hand movement",
    "recognize signals through tail position",
    "recognize signals through wing movement",
    "recognize signals through wing position",
    "recognize signals through beak movement",
    "recognize signals through flipper movement",
    "recognize signals through first movement",
    "rely on ear position to signal",
    "rely on head movement to signal",
    "rely on fin movement to signal",
    "rely on hand movement to signal",
    "rely on tail position to signal",
    "rely on wing movement to signal",
    "rely on wing position to signal",
    "rely on beak movement to signal",
    "rely on flipper movement to signal",
    "rely on first movement to signal",
    "signal the next move with ear position",
    "signal the next move with head movement",
    "signal the next move with fin movement",
    "signal the next move with hand movement",
    "signal the next move with tail position",
    "signal the next move with wing movement",
    "signal the next move with wing position",
    "signal the next move with beak movement",
    "signal the next move with flipper movement",
    "signal the next move with first movement",
    "this movement changes what",
    "this first movement changes what",
    "this first move changes what",
    "rely on the first movement for a reason",
    "rely on first movement for a reason",
    "when the ear movement changes",
    "this ear position changes what",
    "watch this clue",
    "tiny clue",
    "nature trick",
    "look closer",
    "wait for it",
    "the real reason",
    "read the moment",
    "one visible signal",
    "before the payoff",
    "hidden cue",
    "final move",
    "payoff appears",
)
BODY_SIGNAL_TEMPLATE = re.compile(
    r"(?:(?:recognize signals through|signal the next move with) "
    r"(?:body cue|body posture|ear position|eye contact|face shape|feeding cue|"
    r"fin movement|first movement|flipper movement|hand movement|head movement|"
    r"tail position|wing movement|wing position|beak movement|ear|ears|eye|eyes|"
    r"face|faces|feet|fin|fins|flipper|flippers|hand|hands|head|hoof|hooves|"
    r"leg|legs|nose|paw|paws|tail|wing|wings)\b|rely on(?: the)? "
    r"(?:body cue|body posture|ear position|eye contact|face shape|feeding cue|"
    r"fin movement|first movement|flipper movement|hand movement|head movement|"
    r"tail position|wing movement|wing position|beak movement|ear|ears|eye|eyes|"
    r"face|faces|feet|fin|fins|flipper|flippers|hand|hands|head|hoof|hooves|"
    r"leg|legs|nose|paw|paws|tail|wing|wings) to signal)\b",
    re.I,
)
GENERIC_MOVEMENT_TITLE = re.compile(
    r"\bthis (?:(?:first )?movement|first move) changes what [a-z]+s? do next\b|"
    r"\brely on (?:the )?first movement for a reason\b|"
    r"\b(?:read the moment from one first move|react differently when the first move appears|"
    r"rely on (?:the )?first movement to [a-z]+)\b",
    re.I,
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
NATURE_SIGNAL_CATEGORIES = {
    "earth_from_space",
    "ecosystems",
    "forests",
    "fungi",
    "geology",
    "ocean",
    "oceans",
    "plants",
    "rare_phenomena",
    "rivers",
    "tree",
    "trees",
    "volcanoes",
    "weather",
}
NATURE_SIGNAL_SUBJECTS = {
    "atmosphere",
    "biodiversity",
    "coral",
    "earth",
    "earth systems",
    "ecosystem",
    "ecosystems",
    "forest",
    "forests",
    "fungi",
    "geology",
    "glacier",
    "lava",
    "mushroom",
    "mushrooms",
    "mycelium",
    "ocean",
    "plant",
    "plants",
    "reef",
    "river",
    "rivers",
    "rock",
    "rocks",
    "storm",
    "storms",
    "tree",
    "trees",
    "volcano",
    "volcanoes",
    "weather",
}
NATURE_CATEGORY_SIGNALS = (
    ("earth_from_space", ("earth systems", "earth_from_space", "atmosphere", "aerial view", "cloud pattern", "clouds")),
    ("forests", ("forest", "forests", "canopy", "rainforest")),
    ("trees", ("tree", "trees", "root network", "roots")),
    ("fungi", ("fungi", "fungal", "mushroom", "mushrooms", "mycelium")),
    ("geology", ("geology", "rock layers", "rocks", "minerals")),
    ("weather", ("weather", "storm", "lightning", "tornado")),
)


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]+", text or "")


def _title_case_subject(value: str) -> str:
    return value[:1].upper() + value[1:] if value else "Nature"


def extract_subject(story: dict) -> str:
    text = " ".join(
        str(story.get(k) or "") for k in ("seo_title", "title", "hook", "script", "category", "topic_hashtag")
    )
    for token in _words(text.lower()):
        clean = token.replace("'s", "")
        if clean in SUBJECT_TERMS:
            return clean
    return str(story.get("category") or "nature").replace("_", " ").lower()


def extract_animal(story: dict) -> str:
    """Backward-compatible alias; returns the generic subject/topic."""
    return extract_subject(story)


def _normalized_category(story: dict) -> str:
    current = str(story.get("category") or "").strip().lower()
    text = " ".join(
        str(value or "")
        for value in (
            story.get("seo_title"),
            story.get("title"),
            story.get("hook"),
            story.get("topic_hashtag"),
            " ".join(str(tag or "") for tag in (story.get("yt_tags") or [])),
        )
    ).lower()
    for category, signals in NATURE_CATEGORY_SIGNALS:
        if any(re.search(r"\b" + re.escape(signal) + r"\b", text) for signal in signals):
            return category
    return current


def _uses_nature_signal(story: dict) -> bool:
    category = str(story.get("category") or "").strip().lower()
    subject = extract_subject(story).strip().lower()
    category_text = category.replace("_", " ")
    category_forms = {category, category_text, category_text.rstrip("s"), category.rstrip("s"), "nature"}
    return subject in NATURE_SIGNAL_SUBJECTS or (category in NATURE_SIGNAL_CATEGORIES and subject in category_forms)


def _return_hook(story: dict) -> str:
    return "Tomorrow: another nature signal." if _uses_nature_signal(story) else "Tomorrow: another animal signal."


def _hook_mentions_subject(hook: str, subject: str) -> bool:
    if not subject:
        return True
    return bool(re.search(r"\b" + re.escape(subject.lower()) + r"\b", (hook or "").lower()))


def _plural_like_subject(subject: str) -> bool:
    return subject.endswith("s") or subject in {"fish", "sheep", "deer"}


def _subject_safe_hook(story: dict, hook: str) -> str:
    subject = extract_subject(story).strip().lower()
    if _hook_mentions_subject(hook, subject):
        return hook
    cue = extract_cue({**story, "hook": hook})
    verb = "show" if _plural_like_subject(subject) else "shows"
    subject_label = _title_case_subject(subject)
    if cue != "cue":
        return f"{subject_label} {verb} why the {cue} matters."
    return f"{subject_label} {verb} the first clue in seconds."


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
    for cue in sorted(CUE_WORDS, key=len, reverse=True):
        if re.search(r"\b" + re.escape(cue) + r"\b", text):
            return cue
    return "cue"


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title or "").strip(" -.,")
    return title if len(title) <= 82 else title[:79].rstrip(" -.,") + "..."


def _safe_title_options(story: dict, titles: list[str]) -> list[str]:
    out: list[str] = []
    for title in titles:
        clean = _clean_title(title)
        candidate = {**story, "title": clean, "seo_title": clean}
        if clean and not editorial_issues(candidate, include_script=False):
            out.append(clean)
    return out or [_clean_title(title) for title in titles if _clean_title(title)]


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
    generic_hit = (
        any(phrase in text for phrase in GENERIC_PHRASES)
        or bool(BODY_SIGNAL_TEMPLATE.search(text))
        or bool(GENERIC_MOVEMENT_TITLE.search(text))
        or is_generic_movement_copy(text)
    )
    if generic_hit:
        score -= 28
        risks.append("generic_clickbait_language")
    if "?" in title:
        score += 4
        strengths.append("curiosity_question")
    retention_score = analyze_retention(story)["score"]
    score = round(score * 0.65 + retention_score * 0.35)
    if generic_hit:
        score = min(score, 67)
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
    best_hook = curiosity.choose_for_story(
        story,
        {
            "recent_hooks": [str(item) for item in ((story.get("context") or {}).get("recent_hooks") or [])],
        },
    )
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
        "visual_motion_score": float(
            story.get("visual_motion_score") or (0.76 if story.get("pexels_download_url") else 0.48)
        ),
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
    return_hook = _return_hook(story)
    if cue != "cue":
        return f"Watch the {cue} again. {return_hook} {prompt}"[:280]
    return f"{_title_case_subject(subject)} is the example. {return_hook} {prompt}"[:280]


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
    normalized_category = _normalized_category(out)
    if normalized_category:
        out["category"] = normalized_category
    preserve_source_packaging = (
        str(out.get("studio_state") or "") == "comment_idea"
        or str(out.get("source") or "").strip().lower() == "youtube comment idea"
        or str(out.get("production_mode") or "").strip().lower() == "remake_factory"
        or str(out.get("source") or "").strip().lower() == "remake factory"
        or str((out.get("local_rewrite") or {}).get("method") or "") == "curiosity_angle_rescue"
    )
    angle_package = build_curiosity_package(out, subject=extract_subject(out))
    angle_packaging_applied = False
    if (
        angle_package
        and not preserve_source_packaging
        and is_generic_movement_copy(
            " ".join(str(out.get(key) or "") for key in ("seo_title", "title", "hook", "script", "thumbnail_text"))
        )
    ):
        angle_packaging_applied = True
        out.update(
            {
                "seo_title": angle_package["seo_title"],
                "title": angle_package["title"],
                "hook": angle_package["hook"],
                "script": angle_package["script"],
                "lead": angle_package["lead"],
                "thumbnail_text": angle_package["thumbnail_text"],
                "story_format": angle_package["story_format"],
                "yt_tags": angle_package["yt_tags"],
                "curiosity_angle": {
                    "key": angle_package["angle_key"],
                    "cue": angle_package["cue"],
                    "source": "deterministic_angle_packaging",
                },
            }
        )
    memory = load_format_memory()
    selected = _select_packaging(out, memory=memory)
    best_variant = selected["best"]
    if best_variant and not preserve_source_packaging and not angle_packaging_applied:
        out["seo_title"] = best_variant["title"]
        out["title"] = best_variant["title"]
        out["thumbnail_text"] = best_variant["thumbnail_text"]
        out["hook"] = _subject_safe_hook(out, best_variant["hook"])
    titles = _safe_title_options(out, selected["options"]["titles"][:10])
    thumbs = selected["options"]["thumbnail_texts"][:10]
    hooks = [_subject_safe_hook(out, hook) for hook in selected["options"]["hooks"][:5]]
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
        packaged_score["risks"] = list(
            dict.fromkeys(packaged_score["risks"] + list(preflight["editorial_rulebook"].get("violations") or []))
        )
        if int(packaged_score["score"]) < 74:
            packaged_score["state"] = "rewrite_packaging"
    subscriber_score = score_subscriber_conversion(
        {
            **out,
            "packaging": {
                "pinned_comment": out["pinned_comment"],
                "series_label": series_info["label"],
            },
        },
        memory=memory,
    )
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
