"""Queue pruning and quality quarantine for pending Shorts."""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone

import fetch_animals
from utils.local_rewriter import rescue_story
from utils.packaging import extract_action, extract_animal, extract_cue, package_story
from utils.publish_score import score_story
from utils.rights_audit import audit_rights
from utils.youtube_brain import creator_premortem

GENERIC_TITLE_PHRASES = (
    "one visible cue for a reason",
    "another signal hiding in plain sight",
    "another secret hiding in plain sight",
    "secret hiding in plain sight",
)
REQUIRED_FIELDS = ("seo_title", "script", "thumbnail_text", "yt_tags")
MAX_ACTIVE_PENDING = 120
HARD_QUALITY_ISSUES = {
    "missing_source_url",
    "unknown_source",
    "off_topic_visual",
    "duplicate_title",
    "duplicate_source",
    "duplicate_angle",
    "subject_alignment_check_failed",
}
COMMONS_FIELDS = ("commons_image_url", "commons_page_url", "commons_license", "commons_artist")


def normalise_title(story: dict) -> str:
    title = str(story.get("seo_title") or story.get("title") or "")
    title = re.sub(r"[^\w\s'-]", " ", title.lower(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", title).strip()


def angle_key(story: dict) -> str:
    packaged = package_story(story)
    return "|".join((
        extract_animal(packaged).lower(),
        extract_action(packaged).lower(),
        extract_cue(packaged).lower(),
        str(packaged.get("category") or "").lower(),
    ))


def source_key(story: dict) -> str:
    for key in ("pexels_video_id", "source_clip_id", "pexels_download_url", "source_download_url", "source_url", "url"):
        value = str(story.get(key) or "").strip()
        if value:
            return value.lower()
    return ""


def sanitize_story_metadata(story: dict) -> dict:
    out = dict(story)
    for field in COMMONS_FIELDS:
        if field in out:
            out[field] = fetch_animals._safe_commons_value(str(out.get(field) or ""))
    return out


def quality_issues(story: dict, *, seen_titles: set[str], seen_angles: set[str],
                   seen_sources: set[str]) -> list[str]:
    issues: list[str] = []
    title_key = normalise_title(story)
    title = str(story.get("seo_title") or story.get("title") or "")
    if any(phrase in title.lower() for phrase in GENERIC_TITLE_PHRASES):
        issues.append("generic_title_template")
    for field in REQUIRED_FIELDS:
        if not story.get(field):
            issues.append(f"missing_{field}")
    if not (story.get("source_url") or story.get("url")):
        issues.append("missing_source_url")
    rights = audit_rights(story)
    if not rights.get("approved"):
        issues.extend(str(reason) for reason in rights.get("reasons") or [])
    try:
        clip = type("Clip", (), {"url": story.get("url", ""), "title": story.get("title", "")})()
        subject = fetch_animals._subject_from_clip(clip, str(story.get("category") or ""))
        topic = fetch_animals.ANIMAL_TOPICS.get(str(story.get("category") or ""))
        if topic and not fetch_animals._topic_accepts_subject(topic, subject):
            issues.append("off_topic_visual")
        if not fetch_animals._script_matches_visible_subject(subject, str(story.get("script") or "")):
            issues.append("script_subject_mismatch")
    except Exception:
        issues.append("subject_alignment_check_failed")
    if title_key and title_key in seen_titles:
        issues.append("duplicate_title")
    src = source_key(story)
    if src and src in seen_sources:
        issues.append("duplicate_source")
    akey = angle_key(story)
    if akey and akey in seen_angles:
        issues.append("duplicate_angle")
    if not issues:
        if title_key:
            seen_titles.add(title_key)
        if src:
            seen_sources.add(src)
        if akey:
            seen_angles.add(akey)
    return issues


def enriched_score(story: dict, analytics_strategy: dict | None = None) -> dict:
    packaged = package_story(story)
    publish = score_story(packaged, analytics_strategy=analytics_strategy)
    brain = creator_premortem(packaged)
    rights = audit_rights(packaged)
    pkg = packaged.get("packaging") or {}
    repaired = False
    repair_reasons: list[str] = []
    publish_risks = []
    if publish.get("state") == "rewrite" or not publish.get("approved"):
        publish_risks.append("publish_score_rewrite")
    if (publish.get("phrase_risk") or {}).get("hits"):
        publish_risks.append("repetitive_title_template")
    if brain.get("state") in {"rewrite_before_publish", "do_not_publish"} or pkg.get("state") == "rewrite_packaging" or publish_risks:
        repair_reasons = list(dict.fromkeys(
            (brain.get("risks") or []) + (pkg.get("risks") or []) + publish_risks
        ))
        rescued, applied = rescue_story(packaged, repair_reasons)
        if applied:
            repaired = True
            packaged = package_story(rescued)
            publish = score_story(packaged, analytics_strategy=analytics_strategy)
            brain = creator_premortem(packaged)
            rights = audit_rights(packaged)
            pkg = packaged.get("packaging") or {}
    penalty = 0
    if not rights.get("approved"):
        penalty += 30
    if brain.get("state") == "do_not_publish":
        penalty += 35
    elif brain.get("state") == "rewrite_before_publish":
        penalty += 12
    if pkg.get("state") == "rewrite_packaging":
        penalty += 16
    total = max(0.0, min(100.0, float(publish.get("score", 0) or 0) - penalty))
    state = "publish_ready"
    if penalty >= 35 or total < 55:
        state = "reject"
    elif penalty or total < 72:
        state = "rewrite"
    return {
        "story": packaged,
        "score": round(total, 1),
        "state": state,
        "publish_score": publish,
        "youtube_brain": brain,
        "packaging": pkg,
        "rights_audit": rights,
        "repair": {
            "attempted": bool(repair_reasons),
            "applied": repaired,
            "reasons": repair_reasons,
        },
    }


def prune_queue(queue: dict, *, max_pending: int = MAX_ACTIVE_PENDING,
                analytics_strategy: dict | None = None) -> tuple[dict, list[dict], dict]:
    """Return pruned queue, rejected entries, and summary."""
    consumed = [sanitize_story_metadata(s) for s in queue.get("stories") or [] if s.get("consumed")]
    pending = [sanitize_story_metadata(s) for s in queue.get("stories") or [] if not s.get("consumed")]
    seen_titles: set[str] = set()
    seen_angles: set[str] = set()
    seen_sources: set[str] = set()
    rejected: list[dict] = []
    repair: list[dict] = []
    accepted: list[dict] = []
    reasons = Counter()

    for story in pending:
        issues = quality_issues(
            story,
            seen_titles=seen_titles,
            seen_angles=seen_angles,
            seen_sources=seen_sources,
        )
        if issues:
            if not (set(issues) & HARD_QUALITY_ISSUES):
                rescued, applied = rescue_story(story, issues)
                if applied:
                    retry_issues = quality_issues(
                        rescued,
                        seen_titles=seen_titles,
                        seen_angles=seen_angles,
                        seen_sources=seen_sources,
                    )
                    if not retry_issues:
                        story = rescued
                        issues = []
            if issues:
                reasons.update(issues)
                rejected.append({"story": story, "reasons": issues, "stage": "queue_prune"})
                continue
        scored = enriched_score(story, analytics_strategy=analytics_strategy)
        if scored["state"] == "reject":
            reject_reasons = list(dict.fromkeys(
                (scored["youtube_brain"].get("risks") or [])
                + (scored["packaging"].get("risks") or [])
                + (scored["rights_audit"].get("reasons") or [])
                + ["queue_score_reject"]
            ))
            reasons.update(reject_reasons)
            repair.append({"story": scored["story"], "reasons": reject_reasons, "stage": "queue_repair"})
            rejected.append({"story": scored["story"], "reasons": reject_reasons, "stage": "queue_repair"})
            continue
        accepted.append(scored)

    accepted.sort(key=lambda item: (
        float((item["story"].get("autonomy") or {}).get("priority", 0) or 0),
        item["score"],
        int(item["story"].get("score", 0) or 0),
        item["story"].get("fetched_at", ""),
    ), reverse=True)

    kept: list[dict] = []
    for index, item in enumerate(accepted):
        if index >= max_pending:
            reasons.update(["queue_pruned_low_priority"])
            rejected.append({"story": item["story"], "reasons": ["queue_pruned_low_priority"], "stage": "queue_prune"})
            continue
        story = dict(item["story"])
        story["publish_score"] = item["publish_score"]
        story["youtube_brain"] = item["youtube_brain"]
        story["packaging"] = item["packaging"]
        story["queue_repair"] = item["repair"]
        story["queue_prune"] = {
            "score": item["score"],
            "state": item["state"],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        kept.append(story)

    out = dict(queue)
    out["stories"] = consumed + kept
    out["updated_at"] = datetime.now(timezone.utc).isoformat()
    summary = {
        "pending_before": len(pending),
        "pending_after": len(kept),
        "rejected": len(rejected),
        "repair_needed": len(repair),
        "repaired": sum(1 for item in accepted if (item.get("repair") or {}).get("applied")),
        "reasons": dict(reasons.most_common()),
    }
    return out, rejected, summary
