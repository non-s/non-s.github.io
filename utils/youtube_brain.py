"""Senior YouTube operator heuristics for every Short.

This is not artificial consciousness. It is a deterministic executive
producer layer: every video must have a viewer promise, a retention path,
a replay reason, and a post-publish learning plan before it ships.
"""
from __future__ import annotations

import re
from collections import Counter

from utils.story_intelligence import audit_hook, audit_title, classify_format

ACTION_WORDS = {
    "fake", "protect", "escape", "remember", "recognize", "call", "hear",
    "hide", "slide", "hunt", "plan", "trick", "use", "warn", "follow",
    "choose", "save", "signal", "learn", "change", "disappear", "blend",
    "erupt", "glow", "flow", "form", "grow", "freeze", "melt", "restore",
    "recover", "connect", "communicate", "build", "collapse",
}
WEAK_WORDS = {"secret", "another", "amazing", "incredible", "interesting", "thing"}
VISIBLE_CUE_WORDS = {
    "eyes", "ears", "tail", "beak", "wing", "wings", "feet", "paw", "paws", "horn", "horns",
    "sound", "call", "stripe", "feathers", "movement", "cue", "body",
    "skin", "texture", "colour", "color", "nose", "face", "head",
    "hoof", "hooves", "fin", "fins", "gill", "gills", "antenna",
    "antennae", "pupil", "pupils",
    "leaf", "leaves", "roots", "bark", "canopy", "mushroom", "mycelium",
    "lava", "crater", "ash", "cloud", "lightning", "wave", "current",
    "glacier", "rock", "rings", "reef", "coral", "sky", "ice",
}


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]+", text or "")


def _contains_any(text: str, words: set[str]) -> bool:
    lower = (text or "").lower()
    return any(re.search(r"\b" + re.escape(word) + r"\b", lower) for word in words)


def _first_sentence(text: str) -> str:
    return re.split(r"[.!?]\s+", str(text or "").strip(), maxsplit=1)[0]


def _subject_from_text(text: str, category: str = "") -> str:
    subjects = (
        "cow", "cows", "duck", "ducks", "chicken", "chickens", "deer",
        "horse", "horses", "tiger", "tigers", "penguin", "penguins",
        "goat", "goats", "wolf", "wolves", "bear", "bears", "bird",
        "birds", "owl", "owls", "cat", "cats", "dog", "dogs", "lion",
        "lions", "elephant", "elephants", "dolphin", "dolphins", "whale",
        "whales", "parrot", "parrots", "macaw", "macaws", "octopus", "octopuses",
        "donkey", "donkeys", "sheep", "shark", "sharks", "bee", "bees",
        "butterfly", "butterflies", "ant", "ants", "beetle", "beetles",
        "mantis", "mantises", "dragonfly", "dragonflies", "chameleon",
        "chameleons", "orangutan", "orangutans", "monkey", "monkeys",
        "plant", "plants", "tree", "trees", "forest", "forests",
        "fungi", "mushroom", "mushrooms", "mycelium", "ocean", "coral",
        "reef", "river", "rivers", "mountain", "mountains", "glacier",
        "volcano", "volcanoes", "lava", "storm", "storms", "lightning",
        "aurora", "eclipse", "rock", "rocks", "mineral", "minerals",
        "ecosystem", "ecosystems", "earth", "atmosphere", "conservation",
        "biodiversity", "fossil",
    )
    for token in _words(text.lower()):
        if token in subjects:
            return token
    return category or "nature"


def creator_premortem(story: dict) -> dict:
    title = str(story.get("seo_title") or story.get("title") or "")
    hook = str(story.get("hook") or "")
    script = str(story.get("script") or "")
    thumb = str(story.get("thumbnail_text") or "")
    category = str(story.get("category") or "")
    text = f"{title} {hook} {script} {thumb}"
    subject = _subject_from_text(text, category)
    story_format = str(story.get("story_format") or classify_format(text))
    hook_audit = audit_hook(hook)
    title_audit = audit_title(title)

    score = 44
    strengths: list[str] = []
    risks: list[str] = []
    commands: list[str] = []

    first = _first_sentence(script or hook)
    if subject and subject in first.lower():
        score += 8
        strengths.append("subject_visible_in_first_sentence")
    else:
        score -= 8
        risks.append("subject_not_immediately_clear")
        commands.append("Open with the visible subject before the behavior.")

    if _contains_any(text, ACTION_WORDS):
        score += 10
        strengths.append("action_driven_promise")
    else:
        score -= 10
        risks.append("no_action_promise")
        commands.append("Add a visible action verb: fake, protect, escape, remember, call, or use.")

    if _contains_any(text, VISIBLE_CUE_WORDS):
        score += 8
        strengths.append("visible_cue_for_viewer")
    else:
        score -= 6
        risks.append("missing_visual_cue")
        commands.append("Name the visual cue the viewer should watch in the first second.")

    if "because" in script.lower() or "that's why" in script.lower() or "that is why" in script.lower():
        score += 9
        strengths.append("clear_payoff")
    else:
        score -= 9
        risks.append("payoff_not_explicit")
        commands.append("Give the viewer a because/that-is-why payoff.")

    script_words = len(script.split())
    if 42 <= script_words <= 95:
        score += 8
        strengths.append("shorts_length_fit")
    else:
        score -= 8
        risks.append("script_length_risk")

    if 2 <= len(_words(thumb)) <= 5:
        score += 5
        strengths.append("thumbnail_text_scannable")
    else:
        score -= 5
        risks.append("thumbnail_text_not_scannable")

    if hook_audit.score >= 74:
        score += 6
    else:
        score -= 6
        risks.append("hook_shape_weak")
    if title_audit.score >= 74:
        score += 5
    else:
        score -= 5
        risks.append("title_shape_weak")

    weak_hits = [word for word in WEAK_WORDS if re.search(r"\b" + re.escape(word) + r"\b", text.lower())]
    if weak_hits:
        score -= min(10, len(weak_hits) * 3)
        risks.append("generic_creator_language")
        commands.append("Replace generic curiosity words with a specific behavior or body cue.")

    replay_reason = "watch_the_cue_again" if _contains_any(text, VISIBLE_CUE_WORDS) else "weak"
    viewer_promise = f"See why {subject} {story_format.replace('_', ' ')} matters."
    satisfaction_bet = "The viewer gets one visible behavior and one reason, fast."
    score = max(0, min(100, score))
    state = "publish_minded" if score >= 78 else ("rewrite_before_publish" if score >= 60 else "do_not_publish")
    return {
        "score": score,
        "state": state,
        "animal": subject,
        "subject": subject,
        "story_format": story_format,
        "viewer_promise": viewer_promise,
        "satisfaction_bet": satisfaction_bet,
        "replay_reason": replay_reason,
        "retention_path": [
            "0-1s: visible subject and outcome",
            "1-4s: visible cue",
            "4-18s: mechanism",
            "last 2s: payoff and follow signal",
        ],
        "risks": list(dict.fromkeys(risks)),
        "strengths": list(dict.fromkeys(strengths)),
        "commands": list(dict.fromkeys(commands)),
    }


def publish_brain(meta: dict) -> dict:
    brain = creator_premortem(meta)
    score = brain["score"]
    if meta.get("has_captions"):
        score += 5
    else:
        brain["risks"].append("silent_viewer_loss")
    if meta.get("has_broll"):
        score += 5
    else:
        brain["risks"].append("motion_signal_missing")
    visual = meta.get("visual_qa") or {}
    if visual.get("checked") and not visual.get("approved"):
        score -= 25
        brain["risks"].append("first_frame_not_competitive")
    publish_score = meta.get("publish_score") or {}
    if float(publish_score.get("score", 0) or 0) >= 80:
        score += 6
    score = max(0, min(100, round(score, 1)))
    hard_fail = (
        visual.get("checked") and not visual.get("approved")
        or (not meta.get("has_captions") and not meta.get("has_broll"))
    )
    state = "ship" if score >= 78 and brain["state"] != "do_not_publish" else (
        "hold" if hard_fail and score < 62 else "rewrite"
    )
    return {
        **brain,
        "score": score,
        "state": state,
        "post_publish_plan": {
            "1h": "Check views per hour and early swipe/retention proxy.",
            "6h": "If views move but retention lags, generate hook rewrite.",
            "24h": "Classify as scale, rewrite_hook, pause_topic, or watch.",
        },
    }


def channel_brain_summary(items: list[dict]) -> dict:
    states = Counter(str((item.get("youtube_brain") or {}).get("state") or "unknown") for item in items)
    risks = Counter(
        risk
        for item in items
        for risk in ((item.get("youtube_brain") or {}).get("risks") or [])
    )
    avg = 0.0
    scores = [float((item.get("youtube_brain") or {}).get("score", 0) or 0) for item in items]
    if scores:
        avg = round(sum(scores) / len(scores), 2)
    return {
        "average_score": avg,
        "states": dict(states),
        "top_risks": dict(risks.most_common(8)),
    }
