import json
import re
from collections import Counter
from pathlib import Path

from utils.editorial_guard import editorial_issues

ROOT = Path(__file__).resolve().parent.parent
BAD_COPY = re.compile(
    r"to use|to rely|signal cue|body posture|through body cue|with detail|with movement|turn the detail",
    re.I,
)
BODY_SIGNAL_TEMPLATE = re.compile(
    r"(?:(?:recognize signals through|signal the next move with) "
    r"(?:body cue|body posture|ear position|eye contact|face shape|"
    r"feeding cue|fin movement|first movement|flipper movement|hand movement|head movement|"
    r"tail position|wing movement|wing position|beak movement|ear|ears|eye|eyes|face|"
    r"faces|feet|fin|fins|flipper|flippers|hand|hands|head|hoof|hooves|leg|legs|"
    r"nose|paw|paws|tail|wing|wings)\b|rely on(?: the)? "
    r"(?:body cue|body posture|ear position|eye contact|face shape|"
    r"feeding cue|fin movement|first movement|flipper movement|hand movement|head movement|"
    r"tail position|wing movement|wing position|beak movement|ear|ears|eye|eyes|face|"
    r"faces|feet|fin|fins|flipper|flippers|hand|hands|head|hoof|hooves|leg|legs|"
    r"nose|paw|paws|tail|wing|wings) to signal)\b",
    re.I,
)
GENERIC_MOVEMENT_TITLE = re.compile(
    r"\bthis (?:(?:first )?movement|first move) changes what [a-z]+s? do next\b|"
    r"\brely on (?:the )?first movement for a reason\b|"
    r"\b(?:read the moment from one first move|react differently when the first move appears|"
    r"rely on (?:the )?first movement to [a-z]+)\b|"
    r"\bwhen the ear movement changes\b|"
    r"\bthis ear position changes what [a-z]+s? do next\b",
    re.I,
)


def _json(path: str) -> dict:
    target = ROOT / path
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def _assert_recommendable(text: str):
    text = str(text or "").strip()
    if not text:
        return
    assert not BAD_COPY.search(text)
    assert not BODY_SIGNAL_TEMPLATE.search(text)
    assert editorial_issues({"title": text, "seo_title": text}, include_script=False) == []


def test_crosspost_pack_exposes_only_recommendable_titles():
    for item in _json("_data/crosspost_pack.json").get("items") or []:
        _assert_recommendable(item.get("title", ""))
        assert not BAD_COPY.search(str(item.get("shortform_caption") or ""))
        assert not BAD_COPY.search(str(item.get("instagram_caption") or ""))


def test_session_and_related_outputs_expose_only_recommendable_titles():
    for item in _json("_data/session_graph.json").get("nodes") or []:
        _assert_recommendable(item.get("title", ""))
    for item in _json("_data/sequel_candidates.json").get("items") or []:
        _assert_recommendable(item.get("title", ""))
    for item in _json("_data/related_video_recommendations.json").get("items") or []:
        _assert_recommendable(item.get("source_title", ""))
        _assert_recommendable((item.get("recommendation") or {}).get("title", ""))
    session_ops = _json("_data/post_upload_session_ops.json")
    for item in session_ops.get("related_video_recommendations") or []:
        _assert_recommendable(item.get("source_title", ""))
        _assert_recommendable((item.get("recommendation") or {}).get("title", ""))
    for item in session_ops.get("sequel_opportunities") or []:
        _assert_recommendable(item.get("title", ""))


def test_session_outputs_cap_repeated_targets():
    checks = [
        (_json("_data/session_graph.json"), "edges"),
        (_json("_data/next_session_actions.json"), "items"),
        (_json("_data/session_graph_actions.json"), "actions"),
    ]
    for payload, key in checks:
        rows = payload.get(key) or []
        if not rows:
            continue
        limit = int(payload.get("target_reuse_limit") or 0)
        assert limit >= 1
        counts = Counter(str(row.get("target_video_id") or "") for row in rows if row.get("target_video_id"))
        assert counts
        assert max(counts.values()) <= limit


def test_session_operator_actions_meet_score_threshold():
    for payload, key in (
        (_json("_data/next_session_actions.json"), "items"),
        (_json("_data/session_graph_actions.json"), "actions"),
    ):
        rows = payload.get(key) or []
        threshold = float(payload.get("action_score_threshold") or 55)
        for row in rows:
            assert float(row.get("score", row.get("edge_weight", 0)) or 0) >= threshold


def test_winner_sequel_outputs_use_recommendable_source_titles():
    for item in _json("_data/winner_sequel_factory.json").get("candidates") or []:
        _assert_recommendable(item.get("source_title", ""))
    for item in _json("_data/autonomous_director.json").get("sequel_candidates") or []:
        _assert_recommendable(item.get("source_title", ""))


def test_remake_and_sequence_outputs_use_recommendable_titles():
    for item in _json("_data/remake_backlog.json").get("remakes") or []:
        _assert_recommendable(item.get("source_title", ""))
        for title in item.get("candidate_titles") or []:
            _assert_recommendable(title)
    for item in _json("_data/sequence_plan.json").get("variants") or []:
        _assert_recommendable(item.get("title", ""))
        _assert_recommendable((item.get("remake_of") or {}).get("title", ""))


def test_ops_guardian_remake_recommendations_are_recommendable():
    executive = _json("_data/ops_guardian.json").get("executive_report") or {}
    for item in executive.get("what_to_remake") or []:
        _assert_recommendable(item.get("title", ""))


def test_comment_to_short_outputs_do_not_expose_bad_source_titles():
    for item in _json("_data/comment_to_short_candidates.json").get("candidates") or []:
        _assert_recommendable(item.get("source_title", ""))


def test_format_memory_does_not_promote_bad_copy_patterns():
    memory = _json("_data/format_memory.json")
    winning_text = " ".join(
        list((memory.get("winning_title_patterns") or {}).keys())
        + list((memory.get("winning_hook_patterns") or {}).keys())
    )

    assert not BAD_COPY.search(winning_text)


def test_early_warning_sequence_candidates_are_recommendable():
    warning = _json("_data/early_warning.json")
    for item in warning.get("sequence_candidates") or []:
        _assert_recommendable(item.get("title", ""))
    for item in warning.get("remake_candidates") or []:
        title = str(item.get("title") or "")
        if title and editorial_issues({"title": title, "seo_title": title}, include_script=False):
            assert item.get("title_issues")


def test_channel_success_scales_only_recommendable_first_day_winners():
    first_day = _json("_data/channel_success.json").get("first_24h") or {}
    for item in first_day.get("winners") or []:
        _assert_recommendable(item.get("title", ""))
    for item in first_day.get("rework") or []:
        title = str(item.get("title") or "")
        if title and editorial_issues({"title": title, "seo_title": title}, include_script=False):
            assert item.get("title_issues")


def test_post24_review_scales_only_recommendable_titles():
    for item in _json("_data/post24_review.json").get("items") or []:
        title = str(item.get("title") or "")
        if item.get("decision") == "scale":
            _assert_recommendable(title)
        elif title and editorial_issues({"title": title, "seo_title": title}, include_script=False):
            assert item.get("decision") == "repair_package"
            assert item.get("title_issues")


def test_opening_audit_report_masks_malformed_titles():
    report = _json("_data/opening_audit_report.json")
    for item in (report.get("worst_openings") or []) + (report.get("weak_openings") or []):
        title = str(item.get("title") or "")
        if not title:
            continue
        assert editorial_issues({"title": title, "seo_title": title}, include_script=False) == []
        source_title = str(item.get("source_title") or "")
        if source_title and editorial_issues({"title": source_title, "seo_title": source_title}, include_script=False):
            assert item.get("title_issues")


def test_youtube_brain_report_separates_publish_ready_from_rewrite():
    report = _json("_data/youtube_brain_report.json")
    for item in report.get("publish_ready_top") or []:
        assert item.get("queue_state") == "publish_ready"
    for item in report.get("risk_watchlist") or []:
        brain = item.get("youtube_brain") or {}
        assert item.get("queue_state") != "publish_ready" or brain.get("risks")


def test_agency_plan_avoids_paused_trend_categories():
    paused = {
        str(item.get("category") or "").lower()
        for item in (_json("_data/ops_guardian.json").get("paused_topics") or [])
        if item.get("category")
    }
    plan = _json("_data/agency_plan.json")
    for day in plan.get("days") or []:
        category = str(day.get("trend_category") or "").lower()
        if category:
            assert category not in paused
    for item in plan.get("blocked_trends") or []:
        assert str(item.get("category") or "").lower() in paused


def test_next_shorts_title_shape_watch_has_rewrite_candidates():
    mix = _json("_data/next_shorts.json").get("title_shape_mix") or {}
    if mix.get("status") == "watch":
        candidates = mix.get("rewrite_candidates") or []
        assert candidates
        for item in candidates:
            assert item.get("title")
            assert item.get("shape")
            assert item.get("action")
            suggestions = item.get("suggested_titles") or []
            assert suggestions
            for title in suggestions:
                _assert_recommendable(title)


def test_operational_surfaces_do_not_promote_generic_body_signal_templates():
    queue = _json("_data/stories_queue.json")
    for story in queue.get("stories") or []:
        if story.get("consumed") or (story.get("queue_prune") or {}).get("state") != "publish_ready":
            continue
        title = str(story.get("seo_title") or story.get("title") or "")
        assert not BODY_SIGNAL_TEMPLATE.search(title), title
        assert not GENERIC_MOVEMENT_TITLE.search(title), title

    for path in (
        "_data/next_shorts.json",
        "_data/dry_run_publish.json",
        "_data/queue_audit.json",
        "_data/youtube_brain_report.json",
        "_data/packaging_report.json",
        "_data/autonomous_growth_plan.json",
        "_data/automation_health.json",
        "_data/trends/freshness_report.json",
        "_site/index.html",
    ):
        target = ROOT / path
        if target.exists():
            text = target.read_text(encoding="utf-8")
            assert not BODY_SIGNAL_TEMPLATE.search(text), path
            assert not GENERIC_MOVEMENT_TITLE.search(text), path
