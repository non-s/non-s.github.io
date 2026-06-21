#!/usr/bin/env python3
"""Dry-run publish scoring without rendering/uploading."""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.growth_strategy import load_strategy, ops_guardian_enforced, paused_categories  # noqa: E402
from utils.publish_priority import autonomy_priority, publish_priority_key  # noqa: E402
from utils.queue_pruner import prune_queue  # noqa: E402

QUEUE = Path("_data/stories_queue.json")
OUT = Path("_data/dry_run_publish.json")
AGENCY_GATE = Path("_data/agency_gate.json")
EDITORIAL_COOLDOWN_SUPPLY_FALLBACK = "editorial_cooldown_supply_fallback"


def _story_id(story: dict) -> str:
    return str(story.get("id") or story.get("slug") or story.get("source_clip_id") or story.get("title") or "")


def _has_editorial_cooldown_supply_fallback(story: dict) -> bool:
    queue_prune = story.get("queue_prune") or {}
    objective_reasons = {str(reason) for reason in (queue_prune.get("objective_reasons") or [])}
    editorial = story.get("editorial") or {}
    return (
        EDITORIAL_COOLDOWN_SUPPLY_FALLBACK in objective_reasons
        or editorial.get("override") == EDITORIAL_COOLDOWN_SUPPLY_FALLBACK
    )


def _agency_held_reasons(path: Path | None = None) -> dict[str, list[str]]:
    gate_path = path or AGENCY_GATE
    if not gate_path.exists():
        return {}
    try:
        payload = json.loads(gate_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, list[str]] = {}
    for item in payload.get("held_items") or []:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "")
        if item_id:
            out[item_id] = [str(reason) for reason in (item.get("reasons") or [])]
    return out


def _prune_with_strategy(data: dict):
    try:
        return prune_queue(data, analytics_strategy=load_strategy())
    except TypeError as exc:
        if "analytics_strategy" not in str(exc):
            raise
        return prune_queue(data)


def build_dry_run(data: dict, *, env: Mapping[str, str] | None = None) -> dict:
    items = []
    objective_reasons: Counter[str] = Counter()
    pruned, rejected, prune_summary = _prune_with_strategy(data)
    paused = set(paused_categories().keys()) if ops_guardian_enforced(env) else set()
    agency_held = _agency_held_reasons()
    for story in pruned.get("stories") or []:
        if story.get("consumed"):
            continue
        story_id = _story_id(story)
        if story_id in agency_held:
            for reason in agency_held[story_id]:
                objective_reasons[f"agency_gate:{reason}"] += 1
            continue
        category = str(story.get("category") or "").strip().lower()
        if category and category in paused:
            continue
        rights = story.get("rights_audit") or {}
        if not rights:
            from utils.rights_audit import audit_rights

            rights = audit_rights(story)
        queue_prune = story.get("queue_prune") or {}
        publish = story.get("publish_score") or {}
        if not publish:
            from utils.publish_score import score_story

            publish = score_story(story)
        editorial = story.get("editorial") or {}
        brain = story.get("youtube_brain") or {}
        packaging = story.get("packaging") or {}
        queue_ready = queue_prune.get("state") == "publish_ready"
        editorial_ready = editorial.get("approved") is True or _has_editorial_cooldown_supply_fallback(story)
        if (
            queue_ready
            and editorial_ready
            and rights.get("approved") is True
            and publish.get("approved") is True
            and publish.get("state") == "publish_ready"
            and not (brain.get("risks") or [])
            and packaging.get("state") != "rewrite_packaging"
            and not (packaging.get("risks") or [])
        ):
            autonomy = story.get("autonomy") or {}
            gate = publish.get("objective_gate") or {}
            for reason in gate.get("reasons") or []:
                objective_reasons[str(reason)] += 1
            items.append(
                {
                    "id": story.get("id", ""),
                    "title": story.get("seo_title") or story.get("title") or "",
                    "category": story.get("category", ""),
                    "queue_score": queue_prune.get("score", 0),
                    "template_cluster": queue_prune.get("template_cluster", ""),
                    "mechanism_cluster": queue_prune.get("mechanism_cluster", ""),
                    "objective_reasons": list(gate.get("reasons") or []),
                    "scale_ready": bool(gate.get("scale_ready", True)),
                    "autonomy_priority": autonomy_priority(story, queue_prune.get("score", 0)),
                    "autonomy_lane": autonomy.get("lane", ""),
                    "hypothesis_id": autonomy.get("hypothesis_id", ""),
                    "packaging_lab": autonomy.get("packaging_lab") or {},
                    "publish_score": publish,
                    "youtube_brain": story.get("youtube_brain") or {},
                    "packaging": story.get("packaging") or {},
                    "rights_audit": rights,
                }
            )
    items = sorted(
        items,
        key=lambda item: publish_priority_key(
            {
                "autonomy": {"priority": item.get("autonomy_priority", 0)},
                "queue_prune": {"score": item.get("queue_score", 0)},
            },
            item.get("publish_score") or {},
        ),
        reverse=True,
    )
    return {
        "would_publish": items[:10],
        "eligible_count": len(items),
        "scale_ready_count": sum(1 for item in items if item.get("scale_ready")),
        "observe_before_scaling_count": sum(
            1 for item in items if "observe_before_scaling" in (item.get("objective_reasons") or [])
        ),
        "objective_reasons": dict(objective_reasons.most_common()),
        "selection_rule": "autonomy_priority first, queue_score and publish_score as tie-breakers",
        "prune_summary": prune_summary,
        "rejected_preview": [
            {
                "id": item["story"].get("id", ""),
                "title": item["story"].get("seo_title") or item["story"].get("title") or "",
                "reasons": item["reasons"],
            }
            for item in rejected[:20]
        ],
    }


def main() -> int:
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    payload = build_dry_run(data, env=os.environ)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"dry_run_publish: {payload['eligible_count']} eligible candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
