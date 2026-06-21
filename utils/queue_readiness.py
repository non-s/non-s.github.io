"""Shared operational publish-readiness checks for the Shorts queue."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from utils.agency_gate import (
    evaluate_story,
    load_duplicate_ids,
    load_recovery_plans,
    load_rewrite_ids,
    load_success_plan,
)
from utils.growth_strategy import ops_guardian_enforced, paused_categories

EDITORIAL_COOLDOWN_SUPPLY_FALLBACK = "editorial_cooldown_supply_fallback"


def story_id(story: dict) -> str:
    return str(story.get("id") or story.get("slug") or story.get("source_clip_id") or story.get("title") or "")


def has_editorial_cooldown_supply_fallback(story: dict) -> bool:
    queue_prune = story.get("queue_prune") or {}
    objective_reasons = {str(reason) for reason in (queue_prune.get("objective_reasons") or [])}
    editorial = story.get("editorial") or {}
    return (
        EDITORIAL_COOLDOWN_SUPPLY_FALLBACK in objective_reasons
        or editorial.get("override") == EDITORIAL_COOLDOWN_SUPPLY_FALLBACK
    )


def _safe_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def agency_held_reasons(
    *,
    root: Path,
    queue: dict | None = None,
    queue_path: Path | None = None,
    agency_gate_path: Path | None = None,
    refresh: bool = False,
) -> dict[str, list[str]]:
    data_dir = root / "_data"
    queue_path = queue_path or data_dir / "stories_queue.json"
    if refresh and queue is not None:
        try:
            rewrite_ids = load_rewrite_ids(data_dir / "retention_rewrite_queue.json")
            recovery = load_recovery_plans(data_dir / "category_recovery.json")
            duplicate_ids = load_duplicate_ids(queue_path)
            success_plan = load_success_plan(data_dir / "channel_success.json")
            computed: dict[str, list[str]] = {}
            for story in queue.get("stories") or []:
                if not isinstance(story, dict) or story.get("consumed"):
                    continue
                verdict = evaluate_story(story, rewrite_ids, recovery, duplicate_ids, success_plan)
                if not verdict.get("approved"):
                    item_id = story_id(story)
                    if item_id:
                        computed[item_id] = [str(reason) for reason in (verdict.get("reasons") or ["held"])]
            return computed
        except Exception:
            pass

    payload = _safe_json(agency_gate_path or data_dir / "agency_gate.json")
    out: dict[str, list[str]] = {}
    for item in payload.get("held_items") or []:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "")
        if item_id:
            out[item_id] = [str(reason) for reason in (item.get("reasons") or [])]
    return out


def publish_ready_verdict(
    story: dict,
    *,
    paused: set[str] | None = None,
    agency_held: dict[str, list[str]] | None = None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    queue_prune = story.get("queue_prune") or {}
    publish = story.get("publish_score") or {}
    editorial = story.get("editorial") or {}
    paused = paused or set()
    agency_held = agency_held or {}

    if story.get("consumed"):
        reasons.append("consumed")
    item_id = story_id(story)
    if item_id in agency_held:
        agency_reasons = agency_held.get(item_id) or ["held"]
        reasons.extend(f"agency_gate:{reason}" for reason in agency_reasons)
    category = str(story.get("category") or "").strip().lower()
    if category and category in paused:
        reasons.append(f"ops_guardian_paused_category:{category}")
    if queue_prune.get("state") != "publish_ready":
        reasons.append(f"queue_prune:{queue_prune.get('state') or 'missing'}")
    if publish.get("approved") is not True or publish.get("state") != "publish_ready":
        reasons.append(f"publish_score:{publish.get('state') or 'missing'}")
    if editorial.get("approved") is not True and not has_editorial_cooldown_supply_fallback(story):
        reasons.append(f"editor_in_chief:{editorial.get('state') or 'missing'}")
    return not reasons, reasons


def build_readiness_payload(
    queue: dict,
    *,
    root: Path | str = ".",
    env: Mapping[str, str] | None = None,
    refresh_agency: bool = False,
    queue_path: Path | None = None,
    agency_gate_path: Path | None = None,
) -> dict:
    root = Path(root)
    pending = [story for story in queue.get("stories") or [] if isinstance(story, dict) and not story.get("consumed")]
    ready: list[dict] = []
    held: Counter[str] = Counter()
    paused = set(paused_categories(root / "_data" / "ops_guardian.json").keys()) if ops_guardian_enforced(env) else set()
    agency_held = agency_held_reasons(
        root=root,
        queue=queue,
        queue_path=queue_path,
        agency_gate_path=agency_gate_path,
        refresh=refresh_agency,
    )
    for story in pending:
        ok, reasons = publish_ready_verdict(story, paused=paused, agency_held=agency_held)
        if ok:
            ready.append(story)
        else:
            for reason in reasons:
                held[reason] += 1
    return {
        "pending": len(pending),
        "publish_ready": len(ready),
        "publish_ready_ids": [str(story.get("id") or "") for story in ready[:20]],
        "held_reasons": dict(held.most_common()),
    }
