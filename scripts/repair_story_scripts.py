"""Repair templated queue scripts with fact-specific deterministic copy."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.editorial_guard import editorial_issues  # noqa: E402
from utils.local_rewriter import rescue_story  # noqa: E402
from utils.packaging import package_story  # noqa: E402
from utils.publish_score import score_story  # noqa: E402
from utils.script_quality import check_templated_narration  # noqa: E402
from utils.youtube_brain import creator_premortem  # noqa: E402


QUEUE = Path("_data/stories_queue.json")
REPAIRABLE_EDITORIAL_ISSUES = {
    "awkward_before_they_remember",
    "awkward_plural_one_cue",
    "awkward_uncountable_one_cue",
    "bad_domain_plural",
    "bad_plural_verb",
    "bad_singular_subject_verb",
    "generic_clickbait_language",
    "generic_first_move_title",
    "generic_hiding_plain_sight",
    "generic_movement_template",
    "generic_next_move_cue",
    "generic_payoff_filler",
    "generic_signal_cue",
}


def _load(path: Path) -> dict:
    if not path.exists():
        return {"stories": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _needs_repair(story: dict) -> bool:
    if (story.get("local_rewrite") or {}).get("method") == "deterministic_rescue":
        return True
    if check_templated_narration(str(story.get("script") or "")):
        return True
    if len(str(story.get("script") or "").split()) < 42:
        return True
    return bool(set(editorial_issues(story)) & REPAIRABLE_EDITORIAL_ISSUES)


def _packaging_lab(story: dict) -> dict:
    packaging = story.get("packaging") or {}
    titles = [str(item).strip() for item in packaging.get("title_options") or [] if str(item).strip()]
    thumbs = [str(item).strip() for item in packaging.get("thumbnail_options") or [] if str(item).strip()]
    hook = str(story.get("hook") or "").strip()
    title = str(story.get("seo_title") or story.get("title") or "").strip()
    hook_variants = [hook, title, str(packaging.get("pinned_comment") or "").split("?")[0].strip()]
    clean_hooks: list[str] = []
    seen: set[str] = set()
    for item in hook_variants:
        clean = " ".join(item.split())[:110]
        key = clean.lower()
        if clean and key not in seen:
            clean_hooks.append(clean)
            seen.add(key)
    return {
        "title_variants": titles[:3] or ([title] if title else []),
        "thumbnail_variants": thumbs[:3],
        "hook_variants": clean_hooks[:3],
        "pinned_comment": packaging.get("pinned_comment", ""),
        "test_rule": "Try the first variant now; keep the other two as measured rewrite options if 24h retention misses target.",
    }


def _refresh_story_state(story: dict) -> dict:
    packaged = package_story(story)
    publish = score_story(packaged)
    brain = creator_premortem(packaged)
    packaged["publish_score"] = publish
    packaged["youtube_brain"] = brain
    autonomy = dict(packaged.get("autonomy") or {})
    autonomy["publish_score"] = publish.get("score", autonomy.get("publish_score", 0))
    autonomy["state"] = publish.get("state", autonomy.get("state", "rewrite"))
    autonomy["packaging_lab"] = _packaging_lab(packaged)
    autonomy["updated_at"] = datetime.now(timezone.utc).isoformat()
    packaged["autonomy"] = autonomy
    return packaged


def repair_queue(path: Path = QUEUE, *, include_consumed: bool = False) -> dict:
    queue = _load(path)
    changed = 0
    held = 0
    repaired_ids: list[str] = []
    held_ids: list[str] = []
    used_scripts = {
        str(story.get("script") or "")
        for story in queue.get("stories") or []
        if isinstance(story, dict)
        and story.get("script")
        and not (story.get("consumed") and not include_consumed)
        and not _needs_repair(story)
    }
    for index, story in enumerate(queue.get("stories") or []):
        if not isinstance(story, dict):
            continue
        if story.get("consumed") and not include_consumed:
            continue
        if not _needs_repair(story):
            continue
        reasons = list((story.get("local_rewrite") or {}).get("reasons") or [])
        reasons.extend(editorial_issues(story))
        reasons.append("templated_narration")
        repaired: dict = {}
        applied = False
        for attempt in range(12):
            candidate = dict(story)
            if attempt:
                candidate["_fact_rescue_salt"] = str(attempt)
            repaired, applied = rescue_story(candidate, list(dict.fromkeys(reasons)))
            if applied and str(repaired.get("script") or "") not in used_scripts:
                repaired.pop("_fact_rescue_salt", None)
                break
            applied = False
        if applied:
            repaired = _refresh_story_state(repaired)
            repaired.setdefault("queue_repair", {})
            repaired["queue_repair"] = {
                **dict(repaired.get("queue_repair") or {}),
                "script_repaired_at": datetime.now(timezone.utc).isoformat(),
                "method": "fact_script_rescue",
            }
            queue["stories"][index] = repaired
            used_scripts.add(str(repaired.get("script") or ""))
            changed += 1
            repaired_ids.append(str(repaired.get("id") or ""))
        else:
            held += 1
            held_ids.append(str(story.get("id") or ""))
    if changed:
        queue["updated_at"] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "path": str(path),
        "changed": changed,
        "held": held,
        "repaired_ids": repaired_ids,
        "held_ids": held_ids,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default=str(QUEUE))
    parser.add_argument("--include-consumed", action="store_true")
    args = parser.parse_args(argv)
    result = repair_queue(Path(args.queue), include_consumed=args.include_consumed)
    print(json.dumps(result, indent=2))
    return 0 if result["held"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
