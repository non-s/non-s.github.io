#!/usr/bin/env python3
"""Dry-run publish scoring without rendering/uploading."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.queue_pruner import prune_queue
from utils.publish_priority import autonomy_priority, publish_priority_key

QUEUE = Path("_data/stories_queue.json")
OUT = Path("_data/dry_run_publish.json")


def build_dry_run(data: dict) -> dict:
    items = []
    objective_reasons = Counter()
    pruned, rejected, prune_summary = prune_queue(data)
    for story in pruned.get("stories") or []:
        if story.get("consumed"):
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
        queue_ready = queue_prune.get("state") == "publish_ready" or (
            queue_prune.get("state") == "rewrite" and float(queue_prune.get("score", 0) or 0) >= 90
        )
        if (
            queue_ready
            and rights.get("approved") is True
            and publish.get("approved") is True
            and publish.get("state") == "publish_ready"
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
    payload = build_dry_run(data)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"dry_run_publish: {payload['eligible_count']} eligible candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
