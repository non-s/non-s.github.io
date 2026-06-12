"""Queue pruning and quality quarantine for pending Shorts."""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone

import fetch_animals
from utils.channel_objective import cognitive_mechanism_cluster, load_channel_objective, title_template_cluster
from utils.claim_risk import evaluate_claim_risk
from utils.fact_ledger import duplicate_angle_ids
from utils.local_rewriter import rescue_story
from utils.packaging import extract_action, extract_animal, extract_cue, package_story
from utils.publish_score import score_story
from utils.rights_audit import audit_rights
from utils.rights_guard import evaluate_rights_guard
from utils.youtube_brain import creator_premortem
from utils.editorial_guard import editorial_issues

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
    "missing_source_license",
    "rights_guard_brand_manual_review",
    "rights_guard_person_manual_review",
    "fact_guard_block",
    "subject_alignment_check_failed",
}
COMMONS_FIELDS = ("commons_image_url", "commons_page_url", "commons_license", "commons_artist")
PACKAGING_LAB_VARIANT_FIELDS = ("title_variants", "hook_variants", "thumbnail_variants")


def normalise_title(story: dict) -> str:
    title = str(story.get("seo_title") or story.get("title") or "")
    title = re.sub(r"[^\w\s'-]", " ", title.lower(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", title).strip()


def angle_key(story: dict) -> str:
    return "|".join((
        extract_animal(story).lower(),
        extract_action(story).lower(),
        extract_cue(story).lower(),
        str(story.get("category") or "").lower(),
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
    lab = out.get("autonomy", {}).get("packaging_lab") if isinstance(out.get("autonomy"), dict) else None
    if isinstance(lab, dict):
        clean_lab = dict(lab)
        changed = False
        for field in PACKAGING_LAB_VARIANT_FIELDS:
            values = clean_lab.get(field)
            if not isinstance(values, list):
                continue
            cleaned = []
            for value in values:
                text = str(value or "").strip()
                if not text:
                    continue
                candidate = {
                    **out,
                    "title": text,
                    "seo_title": text,
                    "hook": text,
                    "thumbnail_text": text,
                }
                if not editorial_issues(candidate, include_script=False):
                    cleaned.append(text)
            changed = changed or cleaned != values
            if cleaned:
                clean_lab[field] = cleaned
            else:
                clean_lab.pop(field, None)
        if changed:
            autonomy = dict(out.get("autonomy") or {})
            autonomy["packaging_lab"] = clean_lab
            out["autonomy"] = autonomy
    return out


def quality_issues(story: dict, *, seen_titles: set[str], seen_angles: set[str],
                   seen_sources: set[str], seen_scripts: set[str] | None = None,
                   duplicate_ids: set[str] | None = None) -> list[str]:
    issues: list[str] = []
    duplicate_ids = duplicate_ids or set()
    seen_scripts = seen_scripts if seen_scripts is not None else set()
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
    issues.extend(str(warning) for warning in rights.get("warnings") or [])
    rights_guard = evaluate_rights_guard(story)
    if rights_guard.get("state") != "approved":
        issues.extend(f"rights_guard_{reason}" for reason in rights_guard.get("reasons") or [])
    claim = evaluate_claim_risk(story)
    if claim.get("level") == "block":
        issues.append("fact_guard_block")
    issues.extend(editorial_issues(story))
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
    script_key = fetch_animals._script_key(str(story.get("script") or ""))
    if script_key and script_key in seen_scripts:
        issues.append("duplicate_script")
    akey = angle_key(story)
    if str(story.get("id") or "") in duplicate_ids or (akey and akey in seen_angles):
        issues.append("duplicate_angle")
    if not issues:
        if title_key:
            seen_titles.add(title_key)
        if src:
            seen_sources.add(src)
        if script_key:
            seen_scripts.add(script_key)
        if akey:
            seen_angles.add(akey)
    return issues


def enriched_score(story: dict, analytics_strategy: dict | None = None) -> dict:
    packaged = package_story(story)
    publish = score_story(packaged, analytics_strategy=analytics_strategy)
    brain = creator_premortem(packaged)
    rights = audit_rights(packaged)
    editorial = publish.get("editorial_guard") or {"approved": True, "issues": []}
    pkg = packaged.get("packaging") or {}
    repaired = False
    repair_reasons: list[str] = []
    publish_risks = []
    brain_risks = [str(risk) for risk in (brain.get("risks") or [])]
    packaging_risks = [str(risk) for risk in (pkg.get("risks") or [])]
    if publish.get("state") == "rewrite" or not publish.get("approved"):
        publish_risks.append("publish_score_rewrite")
    if (publish.get("phrase_risk") or {}).get("hits"):
        publish_risks.append("repetitive_title_template")
    if not editorial.get("approved", True):
        publish_risks.extend(str(issue) for issue in editorial.get("issues") or [])
    if (
        brain.get("state") in {"rewrite_before_publish", "do_not_publish"}
        or brain_risks
        or pkg.get("state") == "rewrite_packaging"
        or packaging_risks
        or publish_risks
    ):
        repair_reasons = list(dict.fromkeys(
            brain_risks + packaging_risks + publish_risks
        ))
        rescued, applied = rescue_story(packaged, repair_reasons)
        if applied:
            repaired = True
            packaged = package_story(rescued)
            publish = score_story(packaged, analytics_strategy=analytics_strategy)
            brain = creator_premortem(packaged)
            rights = audit_rights(packaged)
            editorial = publish.get("editorial_guard") or {"approved": True, "issues": []}
            pkg = packaged.get("packaging") or {}
            brain_risks = [str(risk) for risk in (brain.get("risks") or [])]
            packaging_risks = [str(risk) for risk in (pkg.get("risks") or [])]
    penalty = 0
    if not rights.get("approved"):
        penalty += 30
    if rights.get("warnings"):
        penalty += 18
    if not publish.get("approved"):
        penalty += 40 if publish.get("state") == "reject" else 22
    if not editorial.get("approved", True):
        penalty += 35
    if brain.get("state") == "do_not_publish":
        penalty += 35
    elif brain.get("state") == "rewrite_before_publish":
        penalty += 12
    if brain_risks:
        penalty += min(18, 6 * len(brain_risks))
    if pkg.get("state") == "rewrite_packaging":
        penalty += 16
    elif packaging_risks:
        penalty += min(12, 4 * len(packaging_risks))
    total = max(0.0, min(100.0, float(publish.get("score", 0) or 0) - penalty))
    state = "publish_ready"
    if penalty >= 35 or total < 55:
        state = "reject"
    elif not publish.get("approved") or publish.get("state") != "publish_ready" or penalty or total < 72:
        state = "rewrite"
    return {
        "story": packaged,
        "score": round(total, 1),
        "state": state,
        "publish_score": publish,
        "youtube_brain": brain,
        "packaging": pkg,
        "rights_audit": rights,
        "editorial_guard": editorial,
        "repair": {
            "attempted": bool(repair_reasons),
            "applied": repaired,
            "reasons": repair_reasons,
        },
    }


def _objective_rank(item: dict) -> tuple[int, float]:
    gate = ((item.get("publish_score") or {}).get("objective_gate") or {})
    scale_ready = 1 if gate.get("scale_ready", True) else 0
    try:
        confidence = float(gate.get("confidence_score") or 0)
    except Exception:
        confidence = 0.0
    return scale_ready, confidence


def prune_queue(queue: dict, *, max_pending: int = MAX_ACTIVE_PENDING,
                analytics_strategy: dict | None = None) -> tuple[dict, list[dict], dict]:
    """Return pruned queue, rejected entries, and summary."""
    consumed = [sanitize_story_metadata(s) for s in queue.get("stories") or [] if s.get("consumed")]
    pending = [sanitize_story_metadata(s) for s in queue.get("stories") or [] if not s.get("consumed")]
    pending.sort(
        key=lambda story: (
            float((story.get("autonomy") or {}).get("priority", 0) or 0),
            int(story.get("score", 0) or 0),
            story.get("fetched_at", ""),
        ),
        reverse=True,
    )
    seen_titles: set[str] = set()
    seen_angles: set[str] = set()
    seen_sources: set[str] = set()
    seen_scripts: set[str] = set()
    duplicate_ids = duplicate_angle_ids(pending)
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
            seen_scripts=seen_scripts,
            duplicate_ids=duplicate_ids,
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
                        seen_scripts=seen_scripts,
                        duplicate_ids=duplicate_ids - {str(story.get("id") or "")},
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
        *_objective_rank(item),
        float((item["story"].get("autonomy") or {}).get("priority", 0) or 0),
        item["score"],
        int(item["story"].get("score", 0) or 0),
        item["story"].get("fetched_at", ""),
    ), reverse=True)

    kept: list[dict] = []
    objective = load_channel_objective()
    objective_targets = objective.get("targets") or {}
    max_cluster = int(objective_targets.get("max_publish_ready_template_cluster") or 2)
    max_mechanism_cluster = int(objective_targets.get("max_publish_ready_mechanism_cluster") or 2)
    template_clusters: Counter[str] = Counter()
    mechanism_clusters: Counter[str] = Counter()
    final_seen_titles: set[str] = set()
    final_seen_angles: set[str] = set()
    final_seen_sources: set[str] = set()
    final_seen_scripts: set[str] = set()
    for index, item in enumerate(accepted):
        story = dict(item["story"])
        final_issues = quality_issues(
            story,
            seen_titles=final_seen_titles,
            seen_angles=final_seen_angles,
            seen_sources=final_seen_sources,
            seen_scripts=final_seen_scripts,
            duplicate_ids=set(),
        )
        if final_issues:
            reasons.update(final_issues)
            rejected.append({"story": story, "reasons": final_issues, "stage": "queue_prune_final"})
            continue
        if len(kept) >= max_pending:
            reasons.update(["queue_pruned_low_priority"])
            rejected.append({"story": story, "reasons": ["queue_pruned_low_priority"], "stage": "queue_prune"})
            continue
        story["publish_score"] = item["publish_score"]
        story["youtube_brain"] = item["youtube_brain"]
        story["packaging"] = item["packaging"]
        story["queue_repair"] = item["repair"]
        effective_state = item["state"]
        effective_score = item["score"]
        gate = (item["publish_score"] or {}).get("objective_gate") or {}
        objective_reasons = [
            f"objective_gate:{reason}"
            for reason in (gate.get("reasons") or [])
        ]
        if objective_reasons:
            reasons.update(objective_reasons)
        cluster = title_template_cluster(str(story.get("seo_title") or story.get("title") or ""))
        mechanism = cognitive_mechanism_cluster(story)
        if cluster and effective_state == "publish_ready":
            if template_clusters[cluster] >= max_cluster:
                effective_state = "rewrite"
                effective_score = max(0.0, float(effective_score) - 12.0)
                objective_reasons.append(f"template_cluster_limit:{cluster}")
            else:
                template_clusters[cluster] += 1
        if mechanism and effective_state == "publish_ready":
            if mechanism_clusters[mechanism] >= max_mechanism_cluster:
                effective_state = "rewrite"
                effective_score = max(0.0, float(effective_score) - 14.0)
                objective_reasons.append(f"mechanism_cluster_limit:{mechanism}")
            else:
                mechanism_clusters[mechanism] += 1
        if objective_reasons:
            reasons.update(objective_reasons)
        story["queue_prune"] = {
            "score": round(effective_score, 1),
            "state": effective_state,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "template_cluster": cluster,
            "mechanism_cluster": mechanism,
            "objective_reasons": objective_reasons,
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
