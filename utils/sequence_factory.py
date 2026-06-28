"""Generate sequel/remake prompts from proven Shorts."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from utils.editorial_guard import editorial_issues
from utils.packaging import extract_action, extract_animal, extract_cue
from utils.remake_factory import build_remake_story

ANALYTICS_FILE = Path("_data/analytics/latest.json")
SEQUENCES_FILE = Path("_data/sequence_plan.json")
SESSION_SEQUELS_FILE = Path("_data/sequel_candidates.json")
FRESH_UPLOAD_ACTIONS_FILE = Path("_data/fresh_upload_actions.json")

FRESH_ACTION_VARIANTS = {
    "package_rescue": "fresh_upload_package_rescue",
    "hook_iteration": "fresh_upload_hook_rescue",
    "opening_iteration": "fresh_upload_opening_rewrite",
    "package_test": "fresh_upload_package_test",
    "amplify": "fresh_upload_momentum_sequel",
}

CATEGORY_SEQUENCE_SEEDS = {
    "arctic": ("Penguins", "reveal", "ice cue", "before the cold move"),
    "birds": ("Owls", "reveal", "wing cue", "after dark"),
    "cats": ("Cats", "reveal", "scent cue", "before they move"),
    "dogs": ("Dogs", "reveal", "nose cue", "before the search"),
    "earth_from_space": ("Storm clouds", "reveal", "shadow cue", "from orbit"),
    "farm": ("Goats", "reveal", "herd cue", "near danger"),
    "forests": ("Forests", "reveal", "cool air cue", "under the canopy"),
    "fungi": ("Mushrooms", "reveal", "hidden gill cue", "under the cap"),
    "geology": ("Rock layers", "reveal", "stripe cue", "inside the cliff"),
    "insects": ("Bees", "reveal", "flight cue", "before takeoff"),
    "ocean": ("Whales", "reveal", "sound cue", "before the dive"),
    "physics": ("Magnets", "reveal", "field cue", "before anything moves"),
    "plants": ("Plants", "reveal", "sunlight cue", "before sugar forms"),
    "primates": ("Monkeys", "reveal", "memory cue", "before the choice"),
    "reptiles": ("Lizards", "reveal", "heat cue", "before they move"),
    "rivers": ("Rivers", "reveal", "sand cue", "along each bank"),
    "space": ("The moon", "reveals", "shadow cue", "before sunrise"),
    "trees": ("Tree rings", "reveal", "weather cue", "inside the trunk"),
    "weather": ("Storm clouds", "reveal", "warning cue", "before the sky changes"),
    "wildlife": ("Foxes", "reveal", "sound cue", "before they turn"),
}

SOURCE_SUBJECT_SIGNALS = (
    ("aurora", "Auroras"),
    ("solar particles", "Auroras"),
    ("the moon", "The moon"),
)

SOURCE_CUE_SIGNALS = (
    ("solar particles", "solar particle cue"),
    ("wing scales", "wing scale cue"),
    ("color scales", "color scale cue"),
    ("ear marks", "ear mark cue"),
    ("signature whistles", "whistle cue"),
    ("shock wave", "shock wave cue"),
    ("scent notes", "scent cue"),
    ("hidden gills", "hidden gill cue"),
    ("cool the air", "cool air cue"),
    ("edge climates", "edge climate cue"),
    ("cool fog", "cool fog cue"),
)


def _safe_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _recommendable_title(title: str) -> bool:
    title = str(title or "").strip()
    if not title:
        return False
    return not editorial_issues({"title": title, "seo_title": title}, include_script=False)


def _num(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_phrase(value: object, fallback: str) -> str:
    text = re.sub(r"[^A-Za-z0-9\s'-]", "", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text or fallback


def _display_subject(value: object, *, category: str = "") -> str:
    raw = _clean_phrase(value, str(category or "nature").replace("_", " "))
    irregular = {
        "aurora": "Auroras",
        "auroras": "Auroras",
        "deer": "Deer",
        "earth": "Earth",
        "fungi": "Fungi",
        "lightning": "Lightning",
        "moon": "The moon",
        "nature": "Nature",
        "physics": "Physics",
        "sheep": "Sheep",
        "space": "Space",
        "weather": "Weather",
    }
    if raw in irregular:
        return irregular[raw]
    if raw.endswith("s"):
        return raw.capitalize()
    if raw.endswith("y"):
        return f"{raw[:-1].capitalize()}ies"
    if raw.endswith(("ch", "sh", "x")):
        return f"{raw.capitalize()}es"
    return f"{raw.capitalize()}s"


def _subject_verb(subject: str) -> str:
    lower = subject.lower()
    if lower.startswith("the ") or lower in {"earth", "lightning", "nature", "physics", "space", "weather"}:
        return "reveals"
    return "reveal" if subject.endswith("s") or subject in {"Deer", "Fungi", "Sheep"} else "reveals"


def _source_subject(source_title: str, category: str) -> str:
    lower = source_title.lower()
    for signal, subject in SOURCE_SUBJECT_SIGNALS:
        if signal in lower:
            return subject
    return _display_subject(
        extract_animal({"title": source_title, "seo_title": source_title, "category": category}),
        category=category,
    )


def _cue_label(raw: object, fallback: str) -> str:
    cue = _clean_phrase(raw, fallback)
    if cue == "cue":
        cue = fallback
    words = cue.split()
    if len(words) > 1 and words[-1].endswith("s"):
        words[-1] = words[-1][:-1]
        cue = " ".join(words)
    if any(token in cue for token in ("cue", "clue", "radar", "flash", "wave")):
        return cue
    return f"{cue} cue"


def _source_cue(source_title: str, story: dict, fallback: str) -> str:
    lower = source_title.lower()
    for signal, cue in SOURCE_CUE_SIGNALS:
        if signal in lower:
            return cue
    cue = extract_cue({"title": source_title, "seo_title": source_title, "script": source_title})
    if cue == "cue":
        cue = extract_cue(story)
    return _cue_label(cue, fallback)


def _possessive_subject(subject: str) -> str:
    lower = subject.lower()
    if lower.startswith("the "):
        return f"{lower}'s"
    if lower.endswith("s") and lower not in {"physics"}:
        return f"{lower}'"
    return f"{lower}'s"


def _safe_variant_title(story: dict, title: str, fallback: str) -> str:
    for candidate in (title, fallback):
        clean = re.sub(r"\s+", " ", candidate or "").strip(" -.,")
        if clean and _recommendable_title(clean):
            return clean[:82]
    return str(story.get("title") or story.get("seo_title") or "Nature reveals one useful clue")[:82]


def _retitle_story_for_variant(story: dict, kind: str, source_title: str) -> dict:
    category = str(story.get("category") or "").strip().lower()
    seed_subject, seed_verb, seed_cue, seed_scene = CATEGORY_SEQUENCE_SEEDS.get(
        category, ("Nature", "reveals", "hidden cue", "in the next scene")
    )
    source_subject = _source_subject(source_title, category)
    cue = _source_cue(source_title, story, seed_cue)
    action = _clean_phrase(extract_action({"title": source_title, "seo_title": source_title}), "show")
    if kind == "same_format_new_animal":
        title = f"{seed_subject} {seed_verb} one {seed_cue} from {_possessive_subject(source_subject)} pattern"
        hook = f"{seed_subject} can make the same format feel new in one visible second."
        thumbnail = f"{seed_subject} {seed_cue}".upper()
        brief = "same proven structure with a fresh subject"
    elif kind == "same_animal_new_behavior":
        verb = _subject_verb(source_subject)
        title = f"{source_subject} {verb} a second {cue} before the payoff"
        hook = f"{source_subject} can carry a second behavior if the first cue is clearer."
        thumbnail = f"SECOND {cue}".upper()
        brief = "same subject with a new behavior"
    else:
        title = f"The first {cue} explains {_possessive_subject(source_subject)} payoff"
        hook = f"Watch the {cue} first, because the payoff only works after that clue."
        thumbnail = f"FIRST {cue}".upper()
        brief = f"stronger opening around the {action} payoff"
    fallback = f"{source_subject} {_subject_verb(source_subject)} one new {cue}"
    title = _safe_variant_title(story, title, fallback)
    hook = re.sub(r"\s+", " ", hook).strip().rstrip(".") + "."
    script = (
        f"{hook} Watch the {cue} in the first second, because this version tests {brief}. "
        "The visual clue arrives before the explanation, then the payoff lands in one clean sentence. "
        "That keeps the sequence close to the proven Short while giving viewers a new reason to replay."
    )
    out = dict(story)
    out["id"] = f"{story.get('id', 'sequence')}-{kind.replace('_', '-')}"
    out["title"] = title
    out["seo_title"] = title
    out["hook"] = hook
    out["script"] = script
    out["lead"] = script[:400]
    out["thumbnail_text"] = thumbnail[:32]
    out["yt_description"] = f"{title}. Watch the {cue} first, then replay the opening clue."
    out["sequence_brief"] = {
        "kind": kind,
        "source_subject": source_subject,
        "cue": cue,
        "test": brief,
        "free_only": True,
    }
    return out


def _fresh_variant_kind(action: dict) -> str:
    lane = str(action.get("lane") or "")
    return FRESH_ACTION_VARIANTS.get(lane, "")


def _fresh_handoff(action: dict) -> dict:
    keys = (
        "id",
        "priority",
        "lane",
        "action_type",
        "video_id",
        "title",
        "category",
        "series",
        "url",
        "state",
        "checkpoint_label",
        "checkpoint_state",
        "age_hours",
        "current_views",
        "target_views",
        "opening_retention_score",
        "recommended_action",
        "why",
        "free_only",
        "manual_approval_required",
    )
    return {key: action.get(key) for key in keys if key in action}


def _fresh_upload_variants(fresh_upload_actions: dict, *, limit: int) -> list[dict]:
    variants = []
    seen_sources: set[str] = set()
    for action in fresh_upload_actions.get("items") or []:
        if len(variants) >= limit:
            break
        if not isinstance(action, dict):
            continue
        kind = _fresh_variant_kind(action)
        if not kind:
            continue
        if not bool(action.get("manual_approval_required")):
            continue
        title = str(action.get("title") or "")
        video_id = str(action.get("video_id") or "")
        if not video_id or video_id in seen_sources or not _recommendable_title(title):
            continue
        story = build_remake_story(
            {
                "source_video_id": video_id,
                "source_title": title,
                "category": action.get("category") or "",
                "views": int(_num(action.get("current_views"))),
                "retention": _num(action.get("opening_retention_score")),
                "growth_score": 0,
                "action": action.get("recommended_action") or action.get("action_type") or kind,
            }
        )
        story = _retitle_story_for_variant(story, kind, title)
        story["sequence_variant"] = kind
        story["sequence_source"] = "fresh_upload_actions"
        story["fresh_upload_handoff"] = _fresh_handoff(action)
        variants.append(story)
        seen_sources.add(video_id)
    return variants


def build_sequence_plan(
    analytics: dict | None = None,
    *,
    limit: int = 5,
    include_session_handoff: bool | None = None,
    fresh_upload_actions: dict | None = None,
    include_fresh_upload_handoff: bool | None = None,
) -> dict:
    load_from_disk = analytics is None
    include_session_handoff = load_from_disk if include_session_handoff is None else include_session_handoff
    include_fresh_upload_handoff = (
        load_from_disk or fresh_upload_actions is not None
        if include_fresh_upload_handoff is None
        else include_fresh_upload_handoff
    )
    analytics = analytics or _safe_json(ANALYTICS_FILE)
    fresh_upload_actions = fresh_upload_actions or (
        _safe_json(FRESH_UPLOAD_ACTIONS_FILE) if include_fresh_upload_handoff else {}
    )
    winners = []
    for item in analytics.get("top_performers") or []:
        if not _recommendable_title(str(item.get("title") or "")):
            continue
        retention = _num(item.get("view_pct") or item.get("average_view_percentage"))
        growth = _num(item.get("growth_score"))
        views = int(_num(item.get("views")))
        if (retention >= 62 and growth >= 180) or views >= 1200:
            winners.append(item)
    variants = []
    for winner in winners[:limit]:
        base = {
            "source_video_id": winner.get("video_id", ""),
            "source_title": winner.get("title", ""),
            "category": winner.get("category", ""),
            "views": winner.get("views", 0),
            "retention": winner.get("view_pct") or winner.get("average_view_percentage") or 0,
            "growth_score": winner.get("growth_score", 0),
        }
        for kind in ("same_format_new_animal", "same_animal_new_behavior", "same_topic_stronger_hook"):
            story = build_remake_story({**base, "action": kind})
            story = _retitle_story_for_variant(story, kind, str(winner.get("title") or ""))
            story["sequence_variant"] = kind
            variants.append(story)
    session_sequels = (_safe_json(SESSION_SEQUELS_FILE).get("items") or []) if include_session_handoff else []
    for item in session_sequels[:limit]:
        if not isinstance(item, dict):
            continue
        story = build_remake_story(
            {
                "source_video_id": item.get("video_id") or item.get("source_video_id", ""),
                "source_title": item.get("title", ""),
                "category": item.get("category", ""),
                "action": item.get("prompt") or "session_graph_sequel",
            }
        )
        story = _retitle_story_for_variant(story, "session_graph_sequel", str(item.get("title") or ""))
        story["sequence_variant"] = "session_graph_sequel"
        handoff = dict(item)
        original_title = str(item.get("title") or "")
        clean_title = str((story.get("remake_of") or {}).get("title") or story.get("title") or "")
        if original_title and clean_title and not _recommendable_title(original_title):
            handoff["title"] = clean_title
            prompt = str(handoff.get("prompt") or "")
            handoff["prompt"] = prompt.replace(original_title, clean_title)
        story["session_handoff"] = handoff
        variants.append(story)
    fresh_variants = _fresh_upload_variants(fresh_upload_actions, limit=limit) if include_fresh_upload_handoff else []
    variants.extend(fresh_variants)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_winners": len(winners),
        "fresh_upload_handoffs": len(fresh_variants),
        "variants": variants,
        "commands": [
            "Use one sequence variant per winner before exploring a cold topic.",
            "Do not publish all variants back-to-back; mix with proven farm/birds inventory.",
            "Use fresh-upload handoffs only as review-ready next drafts, not as automatic reuploads.",
        ],
    }


def write_sequence_plan(path: Path = SEQUENCES_FILE) -> dict:
    plan = build_sequence_plan()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return plan
