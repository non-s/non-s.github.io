#!/usr/bin/env python3
"""Count Shorts that can survive the real publishing gate right now."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.agency_gate import (  # noqa: E402
    evaluate_story,
    load_duplicate_ids,
    load_recovery_plans,
    load_rewrite_ids,
    load_success_plan,
)
from utils.growth_strategy import load_strategy, ops_guardian_enforced, paused_categories  # noqa: E402
from utils.queue_pruner import prune_queue  # noqa: E402
from utils.rejected_queue import record_rejection  # noqa: E402

QUEUE = ROOT / "_data" / "stories_queue.json"
PRUNE_REPORT = ROOT / "_data" / "queue_prune_report.json"
REPAIR_OUT = ROOT / "_data" / "repair_queue.jsonl"
AGENCY_GATE = ROOT / "_data" / "agency_gate.json"
CATEGORY_RECOVERY = ROOT / "_data" / "category_recovery.json"
CHANNEL_SUCCESS = ROOT / "_data" / "channel_success.json"
REWRITE_QUEUE = ROOT / "_data" / "retention_rewrite_queue.json"
EDITORIAL_COOLDOWN_SUPPLY_FALLBACK = "editorial_cooldown_supply_fallback"


def _read_queue(path: Path = QUEUE) -> dict:
    if not path.exists():
        return {"stories": []}
    return json.loads(path.read_text(encoding="utf-8"))


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


def _agency_held_reasons(
    path: Path | None = None,
    *,
    queue: dict | None = None,
    queue_path: Path = QUEUE,
) -> dict[str, list[str]]:
    if queue is not None:
        try:
            rewrite_ids = load_rewrite_ids(REWRITE_QUEUE)
            recovery = load_recovery_plans(CATEGORY_RECOVERY)
            duplicate_ids = load_duplicate_ids(queue_path)
            success_plan = load_success_plan(CHANNEL_SUCCESS)
            computed: dict[str, list[str]] = {}
            for story in queue.get("stories") or []:
                if not isinstance(story, dict) or story.get("consumed"):
                    continue
                verdict = evaluate_story(story, rewrite_ids, recovery, duplicate_ids, success_plan)
                if not verdict.get("approved"):
                    story_id = _story_id(story)
                    if story_id:
                        computed[story_id] = [str(reason) for reason in (verdict.get("reasons") or ["held"])]
            return computed
        except Exception:
            pass

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


def _is_publish_ready(
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
    story_id = _story_id(story)
    if story_id in agency_held:
        agency_reasons = agency_held.get(story_id) or ["held"]
        reasons.extend(f"agency_gate:{reason}" for reason in agency_reasons)
    category = str(story.get("category") or "").strip().lower()
    if category and category in paused:
        reasons.append(f"ops_guardian_paused_category:{category}")
    if queue_prune.get("state") != "publish_ready":
        reasons.append(f"queue_prune:{queue_prune.get('state') or 'missing'}")
    if publish.get("approved") is not True or publish.get("state") != "publish_ready":
        reasons.append(f"publish_score:{publish.get('state') or 'missing'}")
    if editorial.get("approved") is not True and not _has_editorial_cooldown_supply_fallback(story):
        reasons.append(f"editor_in_chief:{editorial.get('state') or 'missing'}")
    return not reasons, reasons


def refresh_queue(path: Path = QUEUE) -> dict:
    """Prune and persist queue metadata before counting ready supply."""
    queue = _read_queue(path)
    pruned, rejected, summary = prune_queue(queue, analytics_strategy=load_strategy())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pruned, indent=2, ensure_ascii=False), encoding="utf-8")
    PRUNE_REPORT.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    repair_items = []
    for item in rejected:
        record_rejection(item["story"], item["reasons"], stage=item.get("stage", "queue_prune"))
        if item.get("stage") == "queue_repair":
            repair_items.append(item)
    REPAIR_OUT.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in repair_items),
        encoding="utf-8",
    )
    return pruned


def build_payload(
    queue: dict,
    *,
    env: Mapping[str, str] | None = None,
    refresh_agency: bool = False,
    queue_path: Path = QUEUE,
) -> dict:
    pending = [story for story in queue.get("stories") or [] if isinstance(story, dict) and not story.get("consumed")]
    ready: list[dict] = []
    held: Counter[str] = Counter()
    paused = set(paused_categories().keys()) if ops_guardian_enforced(env) else set()
    agency_held = _agency_held_reasons(queue=queue, queue_path=queue_path) if refresh_agency else _agency_held_reasons()
    for story in pending:
        ok, reasons = _is_publish_ready(story, paused=paused, agency_held=agency_held)
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default=str(QUEUE), help="Queue JSON path.")
    parser.add_argument(
        "--refresh", action="store_true", help="Refresh queue_prune/editorial metadata before counting."
    )
    parser.add_argument("--json", action="store_true", help="Print the full JSON payload.")
    parser.add_argument("--field", choices=("pending", "publish_ready"), help="Print one numeric field only.")
    args = parser.parse_args()

    queue_path = Path(args.queue)
    queue = refresh_queue(queue_path) if args.refresh else _read_queue(queue_path)
    payload = build_payload(queue, refresh_agency=args.refresh, queue_path=queue_path)
    if args.field:
        print(int(payload.get(args.field, 0) or 0))
    elif args.json:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    else:
        print(f"queue_ready_count: {payload['publish_ready']} publish-ready / {payload['pending']} pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
