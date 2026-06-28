"""Rewrite stories that fail the channel success gate.

The agency gate should be strict, but a strict gate without a recovery path
turns inventory into waste. This module makes conservative, deterministic
repairs: shorten scripts, remove question overload, rotate overused phrases
and add a clearer visible cue to repeated angles.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from utils.agency_gate import evaluate_story

MAX_SUCCESS_WORDS = 105
REPAIRABLE_REASONS = {
    "duplicate_angle_rewrite_required",
    "editorial_generic_retention_scaffold",
    "overused_phrase_pressure",
    "category_recovery_rules_not_met",
    "success_recovery_format_required",
    "success_recovery_hook_required",
    "success_question_overload",
    "success_script_too_long",
}

ANGLE_BANK = {
    "arctic": ["ice footing", "heat saving", "white camouflage", "group timing"],
    "birds": ["feather signal", "head angle", "beak pressure", "eye position", "wing timing"],
    "cats": ["whisker map", "ear flick", "paw landing", "tail pause", "grooming reset"],
    "dogs": ["nose check", "paw pressure", "ear turn", "calming yawn", "body freeze"],
    "farm": ["face memory", "hoof timing", "pupil shape", "herd signal", "feeding cue"],
    "insects": ["wing flash", "antenna check", "foot taste", "motion lock"],
    "nocturnal": ["night vision", "silent step", "ear tracking", "pupil shift"],
    "ocean": ["fin angle", "gill rhythm", "ink cloud", "shell cue", "song pattern"],
    "primates": ["hand signal", "face memory", "tool choice", "group rule"],
    "reptiles": ["tongue flick", "shell shield", "heat map", "stillness trick"],
    "wildlife": ["scent mark", "paw placement", "stripe break", "ear direction", "escape path"],
}

PHRASE_ROTATIONS = {
    "secret": "signal",
    "secrets": "signals",
    "real reason": "visible reason",
    "you won't believe": "watch the clue",
    "nobody knows": "most viewers miss",
}

RECOVERY_BLUEPRINTS = {
    "forests": {
        "subject": "forests",
        "title": "Forests trap cool air below thick leaves",
        "hook": "Forests trap cool air below thick leaves.",
        "thumb": "COOL CANOPY",
        "visible": "shadow line",
        "payoff": "The shaded layer keeps soil moisture from leaving as fast, so air near the ground heats more slowly.",
        "format": "body_superpower",
    },
    "plants": {
        "subject": "plants",
        "title": "Plants turn light into stored sugar",
        "hook": "Plants turn light into stored sugar.",
        "thumb": "LIGHT TO SUGAR",
        "visible": "leaf surface",
        "payoff": "Chlorophyll catches energy so the leaf can build sugar from air and water.",
        "format": "body_superpower",
    },
    "rivers": {
        "subject": "rivers",
        "title": "Rivers drop heavy grains at slow edges",
        "hook": "Rivers drop heavy grains at slow edges.",
        "thumb": "FLOW SORTING",
        "visible": "calm edge",
        "payoff": "Fast water keeps lighter sand moving while slower water drops pieces it cannot carry.",
        "format": "myth_buster",
    },
    "birds": {
        "subject": "birds",
        "title": "Birds use feather position before the move",
        "hook": "Birds signal the next move with feather position.",
        "thumb": "FEATHER CUE",
        "visible": "feather position",
        "payoff": "That body cue shows balance, attention, and timing before the obvious action.",
        "format": "animal_memory",
    },
    "primates": {
        "subject": "primates",
        "title": "Primates read hands before the group reacts",
        "hook": "Primates read hand signals before the group reacts.",
        "thumb": "HAND SIGNAL",
        "visible": "hand movement",
        "payoff": "A small hand cue can carry attention, warning, or social timing.",
        "format": "animal_memory",
    },
}

RECOVERY_VARIANTS = {
    "forests": [
        {
            "title": "Forests trap cool air below thick leaves",
            "hook": "Forests trap cool air below thick leaves.",
            "thumb": "COOL CANOPY",
            "visible": "shadow line",
            "payoff": "The shaded layer keeps soil moisture from leaving as fast, so air near the ground heats more slowly.",
        },
        {
            "title": "Forest shade keeps soil moisture from leaving",
            "hook": "Forest shade keeps soil moisture from leaving.",
            "thumb": "SHADE HOLDS WATER",
            "visible": "leaf shade",
            "payoff": "Leaves block direct sun and slow evaporation, which keeps the lower forest air cooler.",
        },
        {
            "title": "Canopy layers slow heat near the ground",
            "hook": "Canopy layers slow heat near the ground.",
            "thumb": "CANOPY LAYERS",
            "visible": "canopy layers",
            "payoff": "Stacked leaves break up sunlight and wind, making the forest floor warm up more slowly.",
        },
    ],
    "rivers": [
        {
            "title": "Rivers drop heavy grains at slow edges",
            "hook": "Rivers drop heavy grains at slow edges.",
            "thumb": "SLOW EDGE",
            "visible": "calm edge",
            "payoff": "Fast water keeps lighter sand moving while slower water drops pieces it cannot carry.",
        },
        {
            "title": "River bends sort sand from larger stones",
            "hook": "River bends sort sand from larger stones.",
            "thumb": "BEND SORTING",
            "visible": "river bend",
            "payoff": "The outside current carries more force, while quieter inside bends collect smaller grains.",
        },
        {
            "title": "Rivers draw speed maps with sediment",
            "hook": "Rivers draw speed maps with sediment.",
            "thumb": "SEDIMENT MAP",
            "visible": "sediment line",
            "payoff": "Each bar of sand marks where the current slowed enough to let material fall out.",
        },
    ],
}

KNOWN_ANIMALS = {
    "bee",
    "bees",
    "butterfly",
    "butterflies",
    "cat",
    "cats",
    "chicken",
    "chickens",
    "cow",
    "cows",
    "crocodile",
    "crocodiles",
    "deer",
    "dog",
    "dogs",
    "dolphin",
    "dolphins",
    "duck",
    "ducks",
    "duckling",
    "ducklings",
    "elephant",
    "elephants",
    "fox",
    "foxes",
    "goat",
    "goats",
    "hedgehog",
    "hedgehogs",
    "horse",
    "horses",
    "ladybug",
    "ladybugs",
    "lemur",
    "lemurs",
    "leopard",
    "leopards",
    "macaque",
    "macaques",
    "macaw",
    "macaws",
    "mantis",
    "monkey",
    "monkeys",
    "octopus",
    "octopuses",
    "owl",
    "owls",
    "penguin",
    "penguins",
    "seal",
    "seals",
    "shark",
    "sharks",
    "tiger",
    "tigers",
    "turtle",
    "turtles",
    "walrus",
    "walruses",
    "whale",
    "whales",
}


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text or "")


def _word_count(text: str) -> int:
    return len(_words(text))


def _stable_choice(story: dict, values: list[str], salt: str = "") -> str:
    seed = f"{story.get('id') or story.get('title') or 'wildbrief'}:{salt}"
    idx = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(values)
    return values[idx]


def _category_subject(story: dict) -> str:
    category = str(story.get("category") or "animal").lower()
    if category == "dogs":
        return "dog"
    if category == "cats":
        return "cat"
    title = str(story.get("title") or story.get("seo_title") or "")
    for token in re.findall(r"[A-Za-z]+", title):
        low = token.lower()
        if low in KNOWN_ANIMALS:
            return low
    blocked = {
        "a",
        "an",
        "the",
        "why",
        "what",
        "how",
        "this",
        "that",
        "before",
        "after",
        "reveal",
        "reveals",
        "show",
        "shows",
        "most",
        "viewers",
        "miss",
        "nose",
        "ear",
        "ears",
        "paw",
        "paws",
        "body",
        "grooming",
        "tail",
        "white",
        "camouflage",
        "check",
        "turn",
        "pressure",
        "reset",
        category,
        category.rstrip("s"),
    }
    for token in re.findall(r"[A-Za-z]+", title):
        low = token.lower()
        if low not in blocked:
            return low
    if category == "wildlife":
        return "animal"
    return category.rstrip("s") or "animal"


def _display_subject(story: dict) -> str:
    subject = _category_subject(story)
    category = str(story.get("category") or "").lower()
    if category == "dogs" or subject == "dog":
        return "Dogs"
    if category == "cats" or subject == "cat":
        return "Cats"
    if subject in {"seal", "seals"}:
        return "Seals"
    if category == "birds":
        return "Birds"
    if category == "farm":
        return "Farm animals"
    if category == "ocean":
        return "Ocean animals"
    if category == "arctic":
        return "Arctic animals"
    if category == "insects":
        return "Insects"
    if category == "primates":
        return "Primates"
    if category == "reptiles":
        return "Reptiles"
    if category == "nocturnal":
        return "Night animals"
    return subject.capitalize()


def _rotate_phrases(text: str) -> str:
    out = text or ""
    for source, replacement in PHRASE_ROTATIONS.items():
        out = re.sub(rf"\b{re.escape(source)}\b", replacement, out, flags=re.IGNORECASE)
    return out


def _remove_question_overload(text: str, keep_first: bool = False) -> str:
    if not text:
        return ""
    kept = 0
    chars = []
    for ch in text:
        if ch != "?":
            chars.append(ch)
            continue
        kept += 1
        chars.append("?" if keep_first and kept == 1 else ".")
    return re.sub(r"\s+", " ", "".join(chars)).strip()


def _trim_script(text: str, max_words: int = MAX_SUCCESS_WORDS) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if _word_count(text) <= max_words:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out = []
    count = 0
    for sentence in sentences:
        sentence_words = _word_count(sentence)
        if out and count + sentence_words > max_words:
            break
        if sentence_words > max_words:
            break
        out.append(sentence)
        count += sentence_words
    if not out:
        out = [" ".join(_words(text)[:max_words]) + "."]
    trimmed = " ".join(out).strip()
    return trimmed if trimmed.endswith((".", "!", "?")) else trimmed + "."


def _source_detail(story: dict) -> str:
    raw = str(story.get("title") or story.get("description") or story.get("seo_title") or "")
    clean = re.sub(r"[^A-Za-z0-9' ]+", " ", raw)
    tokens = [
        token.lower()
        for token in clean.split()
        if token.lower()
        not in {
            "why",
            "what",
            "how",
            "this",
            "that",
            "with",
            "from",
            "their",
            "before",
            "after",
            "animal",
            "animals",
            "wildlife",
            "shorts",
        }
    ]
    return " ".join(tokens[:7]) or "one visible moment"


def _recovery_blueprint(story: dict) -> dict:
    category = str(story.get("category") or "").lower()
    if category in RECOVERY_VARIANTS:
        base = dict(RECOVERY_BLUEPRINTS.get(category, {}))
        base.update(_stable_choice(story, RECOVERY_VARIANTS[category], "recovery-variant"))
        return base
    if category in RECOVERY_BLUEPRINTS:
        return RECOVERY_BLUEPRINTS[category]
    subject = _display_subject(story)
    lower_subject = subject.lower()
    detail = _source_detail(story)
    cue = _stable_choice(story, ANGLE_BANK.get(category, ANGLE_BANK["wildlife"]), "recovery-cue")
    return {
        "subject": lower_subject,
        "title": f"{subject} make the {cue} matter first",
        "hook": f"{subject} make the {cue} matter first.",
        "thumb": cue.upper()[:32],
        "visible": cue,
        "payoff": f"The visible cue inside {detail} gives the viewer one clear reason to keep watching.",
        "format": "body_superpower",
    }


def _rewrite_success_recovery(story: dict, reasons: list[str]) -> dict:
    out = dict(story)
    blueprint = _recovery_blueprint(story)
    visible = blueprint["visible"]
    subject = blueprint["subject"]
    source_detail = _source_detail(story)
    hook = blueprint["hook"]
    script = (
        f"{hook} Watch the {visible} first, because that detail shows the mechanism in motion. "
        f"The source moment is {source_detail}. {blueprint['payoff']} "
        "By the last line, the opening detail has a job viewers can name."
    )
    script = _trim_script(script, max_words=95)
    experiments = dict(out.get("experiments") or {})
    experiments["hook_style"] = "outcome_first"
    experiments["script_tone"] = "conversational"
    out.update(
        {
            "seo_title": str(blueprint["title"])[:100],
            "title": str(blueprint["title"])[:100],
            "hook": hook,
            "script": script,
            "lead": script[:400],
            "thumbnail_text": str(blueprint["thumb"])[:32],
            "story_format": blueprint["format"],
            "experiments": experiments,
        }
    )
    out["success_recovery"] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "category": str(story.get("category") or ""),
        "subject": subject,
        "visible": visible,
        "format": blueprint["format"],
        "hook_style": "outcome_first",
        "reasons": reasons,
    }
    return out


def _rewrite_duplicate_angle(story: dict) -> dict:
    out = dict(story)
    category = str(story.get("category") or "wildlife").lower()
    cue = _stable_choice(story, ANGLE_BANK.get(category, ANGLE_BANK["wildlife"]), "cue")
    subject = _category_subject(story)
    display = _display_subject(story)
    detail = _source_detail(story)
    title = f"{display} show the {cue} in {detail}"
    hook = f"Watch the {cue} first."
    script = (
        f"{hook} The useful moment is not the whole clip; it is the {detail}. "
        f"That visible cue gives this {subject} Short a different job from the last one. "
        "One animal, one movement, one payoff. Follow the cue and the behavior makes sense."
    )
    experiments = dict(out.get("experiments") or {})
    experiments["hook_style"] = "outcome_first"
    experiments["script_tone"] = "conversational"
    out.update(
        {
            "seo_title": title[:100],
            "hook": hook,
            "script": script,
            "lead": script[:400],
            "thumbnail_text": cue.upper()[:32],
            "experiments": experiments,
        }
    )
    return out


def rewrite_story(story: dict, reasons: list[str] | None = None) -> tuple[dict, bool]:
    reasons = list(reasons or [])
    out = dict(story)
    before = {
        "seo_title": out.get("seo_title") or out.get("title") or "",
        "hook": out.get("hook") or "",
        "script_words": _word_count(str(out.get("script") or "")),
        "reasons": reasons,
    }
    changed = False
    recovery_reason_set = {
        "category_recovery_rules_not_met",
        "editorial_generic_retention_scaffold",
        "success_recovery_format_required",
        "success_recovery_hook_required",
    }
    applied_recovery = bool(recovery_reason_set & set(reasons))
    if applied_recovery:
        recovered = _rewrite_success_recovery(out, reasons)
        changed = changed or recovered != out
        out = recovered
    if "duplicate_angle_rewrite_required" in reasons and not applied_recovery:
        out = _rewrite_duplicate_angle(out)
        changed = True
    if "overused_phrase_pressure" in reasons:
        for key in ("seo_title", "title", "hook", "script", "lead", "thumbnail_text"):
            if key in out:
                rotated = _rotate_phrases(str(out.get(key) or ""))
                changed = changed or rotated != out.get(key)
                out[key] = rotated
    if "success_question_overload" in reasons:
        for key in ("seo_title", "title", "hook", "script", "lead"):
            if key in out:
                cleaned = _remove_question_overload(str(out.get(key) or ""), keep_first=False)
                changed = changed or cleaned != out.get(key)
                out[key] = cleaned
    if "success_script_too_long" in reasons or _word_count(str(out.get("script") or "")) > MAX_SUCCESS_WORDS:
        trimmed = _trim_script(str(out.get("script") or ""))
        changed = changed or trimmed != out.get("script")
        out["script"] = trimmed
        out["lead"] = trimmed[:400]
    if changed:
        out["success_rewrite"] = {
            "at": datetime.now(timezone.utc).isoformat(),
            "before": before,
            "after": {
                "seo_title": out.get("seo_title") or out.get("title") or "",
                "hook": out.get("hook") or "",
                "script_words": _word_count(str(out.get("script") or "")),
            },
            "reasons": reasons,
        }
    return out, changed


def rewrite_queue(
    queue: dict, rewrite_ids: set[str], verdicts: dict[str, list[str]], limit: int = 250
) -> tuple[dict, list[dict]]:
    stories = []
    changed = []
    for story in queue.get("stories") or []:
        story_id = str(story.get("id") or "")
        previous_reasons = (story.get("success_rewrite") or {}).get("reasons") or []
        refresh_previous = "duplicate_angle_rewrite_required" in previous_reasons
        reasons = verdicts.get(story_id, previous_reasons)
        should_repair = bool(set(reasons) & REPAIRABLE_REASONS)
        if (
            story.get("consumed")
            or (story_id not in rewrite_ids and not refresh_previous and not should_repair)
            or len(changed) >= limit
        ):
            stories.append(story)
            continue
        updated, did_change = rewrite_story(story, reasons)
        stories.append(updated)
        if did_change:
            changed.append(
                {
                    "id": story_id,
                    "category": updated.get("category", ""),
                    "title": updated.get("seo_title") or updated.get("title", ""),
                    "reasons": verdicts.get(story_id, []),
                    "script_words": _word_count(str(updated.get("script") or "")),
                }
            )
    out = dict(queue)
    out["stories"] = stories
    out["updated_at"] = datetime.now(timezone.utc).isoformat()
    return out, changed


def evaluate_pending(
    queue: dict, rewrite_ids: set[str], recovery_plans: dict[str, dict], duplicate_ids: set[str], success_plan: dict
) -> dict[str, list[str]]:
    verdicts = {}
    for story in queue.get("stories") or []:
        if story.get("consumed"):
            continue
        verdict = evaluate_story(story, rewrite_ids, recovery_plans, duplicate_ids, success_plan)
        if not verdict.get("approved"):
            story_id = str(story.get("id") or "")
            if story_id:
                verdicts[story_id] = list(verdict.get("reasons") or [])
    return verdicts
