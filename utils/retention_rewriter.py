"""Local rewrite engine for stories held by retention surgery."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from utils.retention_surgeon import diagnose


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text or "")


def _animal_from_story(story: dict) -> str:
    text = f"{story.get('seo_title', '')} {story.get('title', '')}".lower()
    for token in (
        "dog",
        "dogs",
        "cat",
        "cats",
        "iguana",
        "iguanas",
        "gorilla",
        "gorillas",
        "goat",
        "goats",
        "duckling",
        "ducklings",
        "cow",
        "cows",
        "owl",
        "owls",
        "lion",
        "lions",
        "leopard",
        "leopards",
        "shark",
        "sharks",
        "whale",
        "whales",
        "orca",
        "orcas",
        "octopus",
        "octopuses",
        "dolphin",
        "dolphins",
        "chimpanzee",
        "chimpanzees",
        "gorilla",
        "gorillas",
        "orangutan",
        "orangutans",
        "macaque",
        "macaques",
        "monkey",
        "monkeys",
        "snake",
        "snakes",
        "crocodile",
        "crocodiles",
        "lizard",
        "lizards",
        "chameleon",
        "chameleons",
        "bee",
        "bees",
        "butterfly",
        "butterflies",
        "ant",
        "ants",
        "dragonfly",
        "dragonflies",
        "mantis",
        "beetle",
        "beetles",
        "seal",
        "seals",
        "walrus",
        "penguin",
        "penguins",
        "polar bear",
        "polar bears",
        "bear",
        "bears",
        "deer",
        "wolf",
        "wolves",
    ):
        if re.search(rf"\b{re.escape(token)}\b", text):
            return token
    category = str(story.get("category") or "animal").strip().lower()
    return category.rstrip("s") or "animal"


def _better_hook(story: dict, diagnosis: dict) -> str:
    suggested = str(diagnosis.get("suggested_hook") or story.get("hook") or "").strip()
    animal = _animal_from_story(story)
    if suggested and re.search(rf"\b{re.escape(animal.rstrip('s'))}s?\b", suggested.lower()):
        return suggested.rstrip(".!?") + "."
    return f"{animal.capitalize()} reveal the reason in one tiny movement."


def rewrite_story(story: dict) -> tuple[dict, bool]:
    """Return a rewritten copy and whether anything changed."""
    before = diagnose(story)
    current_hook = str(story.get("hook") or "").strip().lower()
    generic_rewrite = bool(story.get("retention_rewrite_applied")) and current_hook.startswith(
        (
            "wildlife ",
            "animal ",
            "farm ",
            "ocean ",
            "reptile ",
            "reptiles ",
            "bird ",
            "birds ",
            "cat ",
            "cats ",
            "dog ",
            "dogs ",
            "insect ",
            "insects ",
            "primate ",
            "primates ",
            "arctic ",
            "nocturnal ",
        )
    )
    if before.get("verdict") != "rewrite" and not generic_rewrite:
        return dict(story), False

    out = dict(story)
    hook = _better_hook(story, before)
    animal = _animal_from_story(story)
    original = str(story.get("script") or "").strip()
    body = original
    if body.lower().startswith(str(story.get("hook") or "").strip().lower()):
        body = body[len(str(story.get("hook") or "")) :].lstrip(" .!?")
    body = body or str(story.get("description") or story.get("seo_title") or "")
    body = re.sub(r"\s+", " ", body).strip()
    body = re.sub(r"\b(wildlife|animal|farm|ocean)'s\b", f"{animal}'s", body, flags=re.IGNORECASE)
    body = re.sub(r"^\s*,\s*", "", body)

    visual_detail = (
        f"Watch the {animal}'s face, tail, posture, or first movement, because "
        "that tiny cue is what makes the fact land before the viewer swipes."
    )
    payoff = (
        "That is why this version keeps one animal, one visible signal, "
        "and one clear payoff instead of stretching the setup."
    )
    script = f"{hook} {body} {visual_detail} {payoff}".strip()
    words = _words(script)
    if len(words) > 118:
        script = " ".join(words[:118]).rstrip(" ,") + "."

    out["hook"] = hook
    out["script"] = script
    out["lead"] = script[:400]
    out["retention_rewrite_applied"] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "before": before,
        "after": diagnose(out),
        "method": "local_retention_rewriter",
    }
    if not out.get("thumbnail_text"):
        out["thumbnail_text"] = f"{animal.upper()} SECRET"[:32]
    return out, True


def rewrite_queue(queue: dict, rewrite_ids: set[str] | None = None, limit: int = 20) -> tuple[dict, list[dict]]:
    rewrite_ids = rewrite_ids or set()
    stories = []
    changed = []
    for story in queue.get("stories") or []:
        can_repair = bool(story.get("retention_rewrite_applied"))
        if story.get("consumed") or (rewrite_ids and str(story.get("id") or "") not in rewrite_ids and not can_repair):
            stories.append(story)
            continue
        if len(changed) >= limit:
            stories.append(story)
            continue
        updated, did_change = rewrite_story(story)
        stories.append(updated)
        if did_change:
            changed.append(
                {
                    "id": updated.get("id", ""),
                    "title": updated.get("seo_title") or updated.get("title", ""),
                    "before": updated["retention_rewrite_applied"]["before"]["score"],
                    "after": updated["retention_rewrite_applied"]["after"]["score"],
                }
            )
    out = dict(queue)
    out["stories"] = stories
    return out, changed
