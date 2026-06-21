"""Automated editor-in-chief for Wild Brief Shorts."""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass

from utils import channel_memory
from utils.humanity_engine import score_story as score_humanity
from utils.script_quality import evaluate as evaluate_script
from utils.script_quality import should_block as script_should_block

MIN_EDITORIAL_SCORE = 62
MIN_HUMANITY_SCORE = int(os.environ.get("WILD_BRIEF_MIN_HUMANITY_SCORE", "58"))
SUBJECT_COOLDOWN_DAYS = 3
ANGLE_COOLDOWN_DAYS = 10

SERIES_BY_CATEGORY = {
    "cats": "Pet Secrets",
    "dogs": "Pet Secrets",
    "ocean": "Ocean Mysteries",
    "wildlife": "Animal Superpowers",
    "birds": "Sky Intelligence",
    "farm": "Farmyard Surprises",
    "reptiles": "Cold-Blooded Secrets",
    "insects": "Tiny Worlds",
    "primates": "Primate Intelligence",
    "nocturnal": "Night Shift Nature",
    "arctic": "Polar Survival",
    "earth_from_space": "Planet Earth",
    "weather": "Earth Engine",
    "volcanoes": "Earth Engine",
    "geology": "Earth Engine",
    "rivers": "Earth Engine",
    "forests": "Hidden Network",
    "fungi": "Hidden Network",
    "tree": "Hidden Network",
    "trees": "Hidden Network",
    "plants": "Biology Brief",
    "ecosystems": "Hidden Network",
    "rare_phenomena": "Rare Earth",
    "conservation": "Planet Repair",
    "discoveries": "Discovery Brief",
}

_ANIMAL_ALIASES = {
    "ant": "ant",
    "ants": "ant",
    "bat": "bat",
    "bats": "bat",
    "bear": "bear",
    "bears": "bear",
    "bee": "bee",
    "bees": "bee",
    "beetle": "beetle",
    "beetles": "beetle",
    "bird": "bird",
    "birds": "bird",
    "butterfly": "butterfly",
    "butterflies": "butterfly",
    "cat": "cat",
    "cats": "cat",
    "kitten": "cat",
    "kittens": "cat",
    "chameleon": "chameleon",
    "chameleons": "chameleon",
    "chicken": "chicken",
    "chickens": "chicken",
    "cow": "cow",
    "cows": "cow",
    "chimpanzee": "chimpanzee",
    "chimpanzees": "chimpanzee",
    "coral": "coral",
    "corals": "coral",
    "crocodile": "crocodile",
    "crocodiles": "crocodile",
    "deer": "deer",
    "dog": "dog",
    "dogs": "dog",
    "golden": "dog",
    "retriever": "dog",
    "retrievers": "dog",
    "puppy": "dog",
    "puppies": "dog",
    "dolphin": "dolphin",
    "dolphins": "dolphin",
    "duck": "duck",
    "ducks": "duck",
    "eagle": "eagle",
    "eagles": "eagle",
    "elephant": "elephant",
    "elephants": "elephant",
    "fish": "fish",
    "flamingo": "flamingo",
    "flamingos": "flamingo",
    "fox": "fox",
    "foxes": "fox",
    "goat": "goat",
    "goats": "goat",
    "gecko": "gecko",
    "geckos": "gecko",
    "gorilla": "gorilla",
    "gorillas": "gorilla",
    "hedgehog": "hedgehog",
    "hedgehogs": "hedgehog",
    "horse": "horse",
    "horses": "horse",
    "jellyfish": "jellyfish",
    "iguana": "iguana",
    "iguanas": "iguana",
    "leopard": "leopard",
    "leopards": "leopard",
    "lion": "lion",
    "lions": "lion",
    "lemur": "lemur",
    "lemurs": "lemur",
    "lizard": "lizard",
    "lizards": "lizard",
    "macaque": "macaque",
    "macaques": "macaque",
    "mantis": "mantis",
    "mantises": "mantis",
    "monkey": "monkey",
    "monkeys": "monkey",
    "octopus": "octopus",
    "octopuses": "octopus",
    "owl": "owl",
    "owls": "owl",
    "orangutan": "orangutan",
    "orangutans": "orangutan",
    "parrot": "parrot",
    "parrots": "parrot",
    "penguin": "penguin",
    "penguins": "penguin",
    "pig": "pig",
    "pigs": "pig",
    "seal": "seal",
    "seals": "seal",
    "shark": "shark",
    "sharks": "shark",
    "sheep": "sheep",
    "tiger": "tiger",
    "tigers": "tiger",
    "snake": "snake",
    "snakes": "snake",
    "turtle": "turtle",
    "turtles": "turtle",
    "walrus": "walrus",
    "walruses": "walrus",
    "whale": "whale",
    "whales": "whale",
    "wolf": "wolf",
    "wolves": "wolf",
}


@dataclass(frozen=True)
class EditorialReview:
    approved: bool
    score: int
    state: str
    series: str
    subject: str
    humanity: dict
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z][a-z0-9'-]{2,}", (text or "").lower()))


def subject_for_story(story: dict) -> str:
    """Prefer the most specific stable subject carried by the queue."""
    tags = [str(t).strip().lower() for t in (story.get("yt_tags") or []) if str(t).strip()]
    narrative = " ".join(
        [
            str(story.get("title") or ""),
            str(story.get("hook") or ""),
            str(story.get("script") or ""),
        ]
    )
    for word in re.findall(r"[a-z]+", narrative.lower()):
        if word in _ANIMAL_ALIASES:
            return _ANIMAL_ALIASES[word]
    for word in re.findall(r"[a-z]+", " ".join(tags).lower()):
        if word in _ANIMAL_ALIASES:
            return _ANIMAL_ALIASES[word]
    evergreen = {"animals", "animal facts", "wildlife", "nature", "funfacts"}
    for tag in tags:
        if tag not in evergreen:
            return tag
    topic = str(story.get("topic_hashtag") or "").strip().lower()
    return topic or str(story.get("category") or "animals").strip().lower()


def series_for_story(story: dict) -> str:
    category = str(story.get("category") or "wildlife").strip().lower()
    return SERIES_BY_CATEGORY.get(category, "Nature Signals")


def _recent_subject_repeat(subject: str, story: dict, days: int) -> bool:
    if not subject:
        return False
    target = _tokens(subject)
    if not target:
        return False
    for past in channel_memory._iter_recent(days=days):
        past_subject = str(past.get("subject") or "").lower()
        past_entities = " ".join(str(e) for e in (past.get("entities") or []))
        if target & _tokens(f"{past_subject} {past_entities}"):
            return True
    return False


def review(story: dict) -> EditorialReview:
    """Approve only Shorts that look deliberate, specific and non-repetitive."""
    reasons: list[str] = []
    grade, script_issues = evaluate_script(story)
    humanity = score_humanity(story)
    score = grade * 6
    score += min(20, max(0, int(story.get("score", 0) or 0) * 2))
    score += round((humanity.score - 50) * 0.3)

    thumb_words = re.findall(r"[A-Za-z0-9]+", str(story.get("thumbnail_text") or ""))
    if 2 <= len(thumb_words) <= 4:
        score += 8
    else:
        reasons.append("thumbnail copy must contain 2-4 readable words")

    subject = subject_for_story(story)
    if subject and subject not in {"animals", "wildlife", "nature"}:
        score += 6
    else:
        reasons.append("animal subject is too generic")

    if story.get("pexels_download_url") or story.get("source_url"):
        score += 6
    else:
        reasons.append("no source clip is attached")

    repeat = _recent_subject_repeat(subject, story, SUBJECT_COOLDOWN_DAYS)
    if repeat:
        score -= 35
        reasons.append(f"subject repeated inside {SUBJECT_COOLDOWN_DAYS}-day cooldown")
    try:
        angle_repeat = channel_memory.recent_angle_repeat(story, days=ANGLE_COOLDOWN_DAYS)
    except Exception:
        angle_repeat = False
    if angle_repeat:
        score -= 25
        reasons.append(f"story angle repeated inside {ANGLE_COOLDOWN_DAYS}-day cooldown")

    score = max(0, min(100, score))
    if script_should_block(script_issues):
        reasons.append("script quality gate blocked the narration")
    if humanity.score < MIN_HUMANITY_SCORE:
        reasons.append("humanity score is too low")
    if score < MIN_EDITORIAL_SCORE:
        reasons.append(f"editorial score {score} is below {MIN_EDITORIAL_SCORE}")

    approved = not reasons or (
        score >= MIN_EDITORIAL_SCORE
        and humanity.score >= MIN_HUMANITY_SCORE
        and not repeat
        and not angle_repeat
        and not script_should_block(script_issues)
        and 2 <= len(thumb_words) <= 4
    )
    if approved and (story.get("studio_polish") or {}).get("applied"):
        state = "polished"
    elif approved:
        state = "publish_now"
    elif repeat or angle_repeat:
        state = "cooldown_subject"
    elif score < 45 or humanity.score < 35 or "animal subject is too generic" in reasons:
        state = "discard"
    else:
        state = "needs_ai_rewrite"
    return EditorialReview(
        approved=approved,
        score=score,
        state=state,
        series=series_for_story(story),
        subject=subject,
        humanity=humanity.to_dict(),
        reasons=tuple(reasons),
    )


def rank_candidates(candidates: list[dict]) -> list[dict]:
    """Attach editorial metadata and sort strongest publishable stories first."""
    ranked: list[dict] = []
    for story in candidates:
        item = dict(story)
        editorial = review(item)
        item["editorial"] = editorial.to_dict()
        item["studio_state"] = editorial.state
        item["series"] = editorial.series
        ranked.append(item)
    return sorted(
        ranked,
        key=lambda item: (
            bool((item.get("editorial") or {}).get("approved")),
            int(((item.get("editorial") or {}).get("humanity") or {}).get("score", 0)),
            int((item.get("editorial") or {}).get("score", 0)),
            int(item.get("score", 0) or 0),
        ),
        reverse=True,
    )
