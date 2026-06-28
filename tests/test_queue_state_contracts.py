import json
from collections import Counter
from pathlib import Path

from utils.channel_objective import load_channel_objective
from utils.agency_gate import is_soft_agency_hold
from utils.editorial_guard import editorial_issues
from utils.growth_strategy import paused_categories
from utils.queue_pruner import production_quality_issues

ROOT = Path(__file__).resolve().parent.parent


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _publish_ready(story: dict, *, held_ids: set[str] | None = None) -> bool:
    paused = paused_categories(ROOT / "_data" / "ops_guardian.json")
    category = str(story.get("category") or "").strip().lower()
    story_id = str(story.get("id") or "")
    return (
        (story.get("queue_prune") or {}).get("state") == "publish_ready"
        and (story.get("editorial") or {}).get("approved") is True
        and category not in paused
        and story_id not in (held_ids or set())
    )


def _soft_recovery_ready(story: dict, held_reasons: dict[str, list[str]]) -> bool:
    story_id = str(story.get("id") or "")
    publish = story.get("publish_score") or {}
    brain = story.get("youtube_brain") or {}
    packaging = story.get("packaging") or {}
    return (
        story_id in held_reasons
        and is_soft_agency_hold(held_reasons[story_id])
        and _publish_ready(story)
        and publish.get("approved") is True
        and publish.get("state") == "publish_ready"
        and not (brain.get("risks") or [])
        and packaging.get("state") != "rewrite_packaging"
        and not (packaging.get("risks") or [])
    )


def test_publish_ready_queue_matches_operational_reports():
    queue = _json("_data/stories_queue.json")
    pending = [story for story in queue.get("stories") or [] if not story.get("consumed")]
    queue_audit = _json("_data/queue_audit.json")
    dry_run = _json("_data/dry_run_publish.json")
    next_shorts = _json("_data/next_shorts.json")
    agency_gate = _json("_data/agency_gate.json")
    held_reasons = {
        str(item.get("id") or ""): [str(reason) for reason in (item.get("reasons") or [])]
        for item in (agency_gate.get("held_items") or [])
    }
    held_ids = set(held_reasons)
    ready = [story for story in pending if _publish_ready(story, held_ids=held_ids)]
    recovery_ready = [story for story in pending if _soft_recovery_ready(story, held_reasons)]

    assert queue_audit.get("pending") == len(pending)
    assert int(agency_gate.get("approved") or 0) + int(agency_gate.get("held") or 0) == len(pending)
    ready_ids = {str(story.get("id") or "") for story in ready}
    assert not (ready_ids & held_ids)
    assert dry_run.get("selection_rule") == "autonomy_priority first, queue_score and publish_score as tie-breakers"
    assert next_shorts.get("selection_rule") == "autonomy_priority first, queue_score and publish_score as tie-breakers"
    dry_run_ready = ready + recovery_ready
    assert dry_run.get("eligible_count") == len(dry_run_ready)
    assert len(dry_run.get("would_publish") or []) == min(10, len(dry_run_ready))
    assert len(next_shorts.get("items") or []) == min(30, len(ready))
    if dry_run_ready and ready:
        dry_run_ids = {str(item.get("id") or "") for item in dry_run.get("would_publish") or []}
        assert str(next_shorts["items"][0]["id"]) in dry_run_ids


def test_publish_ready_queue_has_no_known_copy_or_score_risks():
    queue = _json("_data/stories_queue.json")
    pending = [story for story in queue.get("stories") or [] if not story.get("consumed")]
    ready = [story for story in pending if _publish_ready(story)]

    for story in ready:
        assert (story.get("editorial") or {}).get("approved") is True
        assert editorial_issues(story) == []
        assert production_quality_issues(story) == []
        assert not ((story.get("youtube_brain") or {}).get("risks") or [])
        assert not ((story.get("packaging") or {}).get("risks") or [])


def test_publish_ready_queue_respects_mechanism_cluster_limit():
    queue = _json("_data/stories_queue.json")
    objective = load_channel_objective(ROOT / "_data" / "channel_objective.json")
    limit = int((objective.get("targets") or {}).get("max_publish_ready_mechanism_cluster") or 2)
    pending = [story for story in queue.get("stories") or [] if not story.get("consumed")]
    ready = [story for story in pending if _publish_ready(story)]
    clusters = Counter(
        (story.get("queue_prune") or {}).get("mechanism_cluster")
        for story in ready
        if (story.get("queue_prune") or {}).get("mechanism_cluster")
    )

    assert all(count <= limit for count in clusters.values())


def test_pending_queue_has_unique_titles_and_sources():
    queue = _json("_data/stories_queue.json")
    pending = [story for story in queue.get("stories") or [] if not story.get("consumed")]

    ids = [str(story.get("id") or "") for story in pending]
    titles = [str(story.get("title") or story.get("seo_title") or "").strip().lower() for story in pending]
    sources = [
        str(story.get("source_url") or story.get("url") or "").strip().lower()
        for story in pending
        if str(story.get("source_url") or story.get("url") or "").strip()
    ]

    assert len(ids) == len(set(ids))
    assert len(titles) == len(set(titles))
    assert len(sources) == len(set(sources))
