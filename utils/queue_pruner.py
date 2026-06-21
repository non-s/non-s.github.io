"""Queue pruning and quality quarantine for pending Shorts."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import fetch_animals
from utils.channel_objective import cognitive_mechanism_cluster, load_channel_objective, title_template_cluster
from utils.claim_risk import evaluate_claim_risk
from utils.curiosity_angles import is_generic_movement_copy
from utils.editorial import review as editorial_review
from utils.editorial_guard import editorial_issues
from utils.fact_ledger import duplicate_angle_ids
from utils.growth_strategy import ops_guardian_enforced, paused_categories
from utils.local_rewriter import rescue_story
from utils.packaging import extract_action, extract_animal, extract_cue, normalize_story_category, package_story
from utils.publish_score import score_story
from utils.rights_audit import audit_rights
from utils.rights_guard import evaluate_rights_guard
from utils.script_quality import check_script_starts_with_hook
from utils.youtube_brain import creator_premortem

GENERIC_TITLE_PHRASES = (
    "one visible cue for a reason",
    "another signal hiding in plain sight",
    "another secret hiding in plain sight",
    "secret hiding in plain sight",
)
REPETITIVE_TITLE_PHRASES = (
    "another signal hiding in plain sight",
    "another secret hiding in plain sight",
    "secret hiding in plain sight",
)
GENERIC_SCRIPT_PHRASES = (
    "reveal the reason in one tiny movement",
    "not just hunting",
    "one hidden reason",
)
REQUIRED_FIELDS = ("seo_title", "script", "thumbnail_text", "yt_tags")
MAX_ACTIVE_PENDING = 120
EDITORIAL_COOLDOWN_SUPPLY_FALLBACK = "editorial_cooldown_supply_fallback"
PUBLISH_READY_SUPPLY_RESERVE_FALLBACK = "publish_ready_supply_reserve_fallback"
PUBLISH_READY_RESERVE_TARGET = 6
RESERVE_ALLOWED_PACKAGING_RISKS: set[str] = set()
RESERVE_ALLOWED_BRAIN_RISKS: set[str] = set()
RESERVE_ALLOWED_OPPORTUNITY_REASONS = {"low_opportunity_score", "weak_replay_reason", "weak_visual_surface"}
RESERVE_MIN_PUBLISH_SCORE = 95.0
RESERVE_MIN_QUEUE_SCORE = 78.0
AGENCY_GATE_FILE = Path("_data/agency_gate.json")
HARD_QUALITY_ISSUES = {
    "missing_source_url",
    "unknown_category",
    "unknown_source",
    "off_topic_visual",
    "empty_script",
    "duplicate_script",
    "duplicate_source",
    "duplicate_angle",
    "repetitive_title_template",
    "generic_script_template",
    "script_word_loop",
    "missing_source_license",
    "rights_guard_brand_manual_review",
    "rights_guard_person_manual_review",
    "fact_guard_block",
    "subject_alignment_check_failed",
}
RESCUEABLE_HARD_QUALITY_ISSUES = {
    "duplicate_script",
    "duplicate_angle",
}
NON_RESCUEABLE_HARD_QUALITY_ISSUES = HARD_QUALITY_ISSUES - RESCUEABLE_HARD_QUALITY_ISSUES
COMMONS_FIELDS = ("commons_image_url", "commons_page_url", "commons_license", "commons_artist")
PACKAGING_LAB_VARIANT_FIELDS = ("title_variants", "hook_variants", "thumbnail_variants")
VIEWER_COPY_FIELDS = (
    "seo_title",
    "title",
    "hook",
    "script",
    "thumbnail_text",
    "pinned_comment",
    "description",
)
PACKAGING_VIEWER_FIELDS = (
    "title_options",
    "hook_options",
    "thumbnail_options",
    "selected_variant",
    "curiosity_gap",
    "preflight_inputs",
)


def normalise_title(story: dict) -> str:
    title = str(story.get("seo_title") or story.get("title") or "")
    title = re.sub(r"[^\w\s'-]", " ", title.lower(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", title).strip()


def angle_key(story: dict) -> str:
    return "|".join(
        (
            extract_animal(story).lower(),
            extract_action(story).lower(),
            extract_cue(story).lower(),
            str(story.get("category") or "").lower(),
        )
    )


def source_key(story: dict) -> str:
    for key in ("pexels_video_id", "source_clip_id", "pexels_download_url", "source_download_url", "source_url", "url"):
        value = str(story.get(key) or "").strip()
        if value:
            return value.lower()
    return ""


def published_title_keys(root: Path | None = None) -> set[str]:
    """Return normalised titles already uploaded by this channel."""
    root = root or Path(".")
    titles: set[str] = set()
    for directory_name in ("_videos", "_videos_pt-BR"):
        directory = root / directory_name
        if not directory.exists():
            continue
        for path in directory.glob("*.done"):
            try:
                marker = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(marker, dict):
                key = normalise_title(marker)
                if key:
                    titles.add(key)
    return titles


def production_quality_issues(story: dict, *, seen_scripts: set[str] | None = None) -> list[str]:
    """Mirror the generator's hard queue gate before a story is publish-ready."""
    issues: list[str] = []
    category = str(story.get("category") or "")
    topic = fetch_animals.ANIMAL_TOPICS.get(category)
    if not topic:
        issues.append("unknown_category")
        return issues
    clip = type(
        "Clip",
        (),
        {
            "source": story.get("source") or "",
            "url": story.get("url") or story.get("source_url") or "",
            "title": story.get("source_title")
            or story.get("source_description")
            or story.get("description")
            or story.get("title")
            or "",
        },
    )()
    subject = fetch_animals._subject_from_clip(clip, category)
    script = str(story.get("script") or "")
    title = str(story.get("seo_title") or story.get("title") or "")
    if not fetch_animals._topic_accepts_subject(topic, subject):
        issues.append("off_topic_visual")
    if not fetch_animals._script_matches_visible_subject(subject, script):
        issues.append("script_subject_mismatch")
    if not fetch_animals._copy_matches_visible_subject(
        subject,
        title,
        str(story.get("hook") or ""),
        script,
    ):
        issues.append("copy_subject_mismatch")
    if check_script_starts_with_hook(str(story.get("hook") or ""), script):
        issues.append("script_hook_mismatch")
    script_key = fetch_animals._script_key(script)
    if not script_key:
        issues.append("empty_script")
    elif seen_scripts is not None and script_key in seen_scripts:
        issues.append("duplicate_script")
    lower_title = title.lower()
    lower_script = script.lower()
    if any(phrase in lower_title for phrase in REPETITIVE_TITLE_PHRASES):
        issues.append("repetitive_title_template")
    if any(phrase in lower_script for phrase in GENERIC_SCRIPT_PHRASES):
        issues.append("generic_script_template")
    issues.extend(editorial_issues(story))
    words = re.findall(r"[a-z]+", lower_script)
    if words:
        top_word_count = max(words.count(word) for word in set(words))
        if top_word_count >= 10:
            issues.append("script_word_loop")
    if not issues and seen_scripts is not None and script_key:
        seen_scripts.add(script_key)
    return list(dict.fromkeys(issues))


def sanitize_story_metadata(story: dict) -> dict:
    out = dict(story)
    normalized_category = normalize_story_category(out)
    if normalized_category:
        out["category"] = normalized_category
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
    if out.get("consumed"):
        viewer_chunks = [str(out.get(field) or "") for field in VIEWER_COPY_FIELDS]
        packaging = out.get("packaging")
        if isinstance(packaging, dict):
            for field in PACKAGING_VIEWER_FIELDS:
                viewer_chunks.append(json.dumps(packaging.get(field) or "", ensure_ascii=False))
        if is_generic_movement_copy(" ".join(viewer_chunks)):
            repackage_input = dict(out)
            repackage_input.pop("local_rewrite", None)
            out = package_story(repackage_input)
            out["consumed"] = story.get("consumed")
            if story.get("consumed_at"):
                out["consumed_at"] = story.get("consumed_at")
            if story.get("consumed_reason"):
                out["consumed_reason"] = story.get("consumed_reason")
    return out


def quality_issues(
    story: dict,
    *,
    seen_titles: set[str],
    seen_angles: set[str],
    seen_sources: set[str],
    seen_scripts: set[str] | None = None,
    duplicate_ids: set[str] | None = None,
) -> list[str]:
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
    issues.extend(production_quality_issues(story))
    try:
        clip = type(
            "Clip",
            (),
            {
                "source": story.get("source") or "",
                "url": story.get("url") or story.get("source_url") or "",
                "title": story.get("source_title")
                or story.get("source_description")
                or story.get("description")
                or story.get("title")
                or "",
            },
        )()
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
    return list(dict.fromkeys(issues))


def enriched_score(story: dict, analytics_strategy: dict | None = None) -> dict:
    packaged = package_story(story)
    publish = score_story(packaged, analytics_strategy=analytics_strategy)
    brain = creator_premortem(packaged)
    rights = audit_rights(packaged)
    editorial = publish.get("editorial_guard") or {"approved": True, "issues": []}
    editor = editorial_review(packaged)
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
        repair_reasons = list(dict.fromkeys(brain_risks + packaging_risks + publish_risks))
        rescued, applied = rescue_story(packaged, repair_reasons)
        if applied:
            repaired = True
            packaged = package_story(rescued)
            publish = score_story(packaged, analytics_strategy=analytics_strategy)
            brain = creator_premortem(packaged)
            rights = audit_rights(packaged)
            editorial = publish.get("editorial_guard") or {"approved": True, "issues": []}
            editor = editorial_review(packaged)
            pkg = packaged.get("packaging") or {}
            brain_risks = [str(risk) for risk in (brain.get("risks") or [])]
            packaging_risks = [str(risk) for risk in (pkg.get("risks") or [])]
    editor_risks = [f"editor_in_chief:{reason}" for reason in editor.reasons]
    if not editor.approved and editor.state == "needs_ai_rewrite":
        rescue_reasons = editor_risks or [f"editor_in_chief:{editor.state}"]
        rescued, applied = rescue_story(packaged, rescue_reasons)
        if applied:
            repaired = True
            repair_reasons = list(dict.fromkeys(repair_reasons + rescue_reasons))
            packaged = package_story(rescued)
            publish = score_story(packaged, analytics_strategy=analytics_strategy)
            brain = creator_premortem(packaged)
            rights = audit_rights(packaged)
            editorial = publish.get("editorial_guard") or {"approved": True, "issues": []}
            editor = editorial_review(packaged)
            pkg = packaged.get("packaging") or {}
            brain_risks = [str(risk) for risk in (brain.get("risks") or [])]
            packaging_risks = [str(risk) for risk in (pkg.get("risks") or [])]
            editor_risks = [f"editor_in_chief:{reason}" for reason in editor.reasons]
    penalty = 0
    if not rights.get("approved"):
        penalty += 30
    if rights.get("warnings"):
        penalty += 18
    if not publish.get("approved"):
        penalty += 40 if publish.get("state") == "reject" else 22
    if not editorial.get("approved", True):
        penalty += 35
    if not editor.approved:
        if editor.state == "discard":
            penalty += 40
        elif editor.state == "cooldown_subject":
            penalty += 28
        else:
            penalty += 22
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
        "editorial": editor.to_dict(),
        "repair": {
            "attempted": bool(repair_reasons),
            "applied": repaired,
            "reasons": repair_reasons,
        },
    }


def _objective_rank(item: dict) -> tuple[int, float]:
    gate = (item.get("publish_score") or {}).get("objective_gate") or {}
    scale_ready = 1 if gate.get("scale_ready", True) else 0
    try:
        confidence = float(gate.get("confidence_score") or 0)
    except Exception:
        confidence = 0.0
    return scale_ready, confidence


def _soft_rewrite_can_publish(item: dict, *, score: float, editor: dict) -> bool:
    """Allow safe, already-approved soft rewrites to keep the live queue stocked."""
    if score < 72:
        return False
    publish = item.get("publish_score") or {}
    if publish.get("approved") is not True or publish.get("state") != "publish_ready":
        return False
    rights = item.get("rights_audit") or {}
    if rights.get("approved") is not True or rights.get("warnings"):
        return False
    if editor and editor.get("approved") is not True:
        return False
    brain = item.get("youtube_brain") or {}
    if brain.get("state") in {"rewrite_before_publish", "do_not_publish"}:
        return False
    if brain.get("risks"):
        return False
    packaging = item.get("packaging") or {}
    if packaging.get("state") == "rewrite_packaging":
        return False
    if packaging.get("risks"):
        return False
    if item.get("state") not in {"rewrite", "publish_ready"}:
        return False
    return True


def _editorial_cooldown_supply_candidate(story: dict) -> bool:
    queue_prune = story.get("queue_prune") or {}
    editorial = story.get("editorial") or {}
    if queue_prune.get("state") != "rewrite" or editorial.get("approved") is True:
        return False
    if editorial.get("state") != "cooldown_subject":
        return False
    if float(editorial.get("score", 0) or 0) < 70:
        return False
    editorial_reasons = {str(reason) for reason in (editorial.get("reasons") or [])}
    if any("below" in reason.lower() for reason in editorial_reasons):
        return False
    objective_reasons = [str(reason) for reason in (queue_prune.get("objective_reasons") or [])]
    publish = story.get("publish_score") or {}
    gate = publish.get("objective_gate") or {}
    gate_reasons = {str(reason) for reason in (gate.get("reasons") or [])}
    objective_gate_reasons = {reason for reason in objective_reasons if reason.startswith("objective_gate:")}
    objective_observe_only = objective_gate_reasons == {"objective_gate:observe_before_scaling"}
    objective_clear = (
        not objective_gate_reasons
        and not gate_reasons
        and gate.get("publish_blocking") is not True
        and gate.get("scale_ready", True) is True
    )
    if not (objective_observe_only or objective_clear):
        return False
    if publish.get("approved") is not True or publish.get("state") != "publish_ready":
        return False
    if float(publish.get("score", 0) or 0) < 90:
        return False
    rights = story.get("rights_audit") or {}
    if rights.get("approved") is not True or rights.get("warnings"):
        return False
    brain = story.get("youtube_brain") or {}
    if brain.get("state") != "publish_minded" or brain.get("risks"):
        return False
    packaging = story.get("packaging") or {}
    if packaging.get("state") == "rewrite_packaging" or packaging.get("risks"):
        return False
    return True


def _publish_ready_reserve_candidate(story: dict) -> bool:
    queue_prune = story.get("queue_prune") or {}
    if queue_prune.get("state") != "rewrite":
        return False
    objective_reasons = {str(reason) for reason in (queue_prune.get("objective_reasons") or [])}
    objective_gate_reasons = {reason for reason in objective_reasons if reason.startswith("objective_gate:")}
    if objective_reasons - objective_gate_reasons:
        return False
    allowed_objective = {
        "objective_gate:observe_before_scaling",
        "objective_gate:bootstrap_observe_before_scaling",
    }
    publish = story.get("publish_score") or {}
    publish_gate = publish.get("objective_gate") or {}
    publish_gate_reasons = {f"objective_gate:{reason}" for reason in (publish_gate.get("reasons") or [])}
    if objective_gate_reasons and not objective_gate_reasons <= allowed_objective:
        return False
    if publish_gate_reasons and not publish_gate_reasons <= allowed_objective:
        return False
    if publish_gate.get("publish_blocking") is True:
        return False
    editorial = story.get("editorial") or {}
    if editorial.get("approved") is not True:
        return False
    publish_ready = publish.get("approved") is True and publish.get("state") == "publish_ready"
    publish_rewrite = publish.get("state") == "rewrite" and publish.get("approved") is not True
    if not (publish_ready or publish_rewrite):
        return False
    if float(publish.get("score", 0) or 0) < RESERVE_MIN_PUBLISH_SCORE:
        return False
    if publish_rewrite:
        opportunity_reasons = {str(reason) for reason in ((publish.get("opportunity") or {}).get("reasons") or [])}
        if opportunity_reasons - RESERVE_ALLOWED_OPPORTUNITY_REASONS:
            return False
        if (publish.get("editorial_guard") or {}).get("approved") is False:
            return False
        if (publish.get("phrase_risk") or {}).get("hits"):
            return False
        if (publish.get("weak_content") or {}).get("state") not in {"", "clear", None}:
            return False
    if float(queue_prune.get("score", 0) or 0) < RESERVE_MIN_QUEUE_SCORE:
        return False
    rights = story.get("rights_audit") or {}
    if rights.get("approved") is not True or rights.get("warnings"):
        return False
    brain = story.get("youtube_brain") or {}
    if brain.get("state") != "publish_minded":
        return False
    brain_risks = {str(risk) for risk in (brain.get("risks") or [])}
    if brain_risks - RESERVE_ALLOWED_BRAIN_RISKS:
        return False
    packaging = story.get("packaging") or {}
    if packaging.get("state") == "rewrite_packaging":
        return False
    packaging_risks = {str(risk) for risk in (packaging.get("risks") or [])}
    if packaging_risks - RESERVE_ALLOWED_PACKAGING_RISKS:
        return False
    return True


def _agency_held_ids(path: Path = AGENCY_GATE_FILE) -> set[str]:
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {str(item.get("id") or "") for item in (payload.get("held_items") or []) if isinstance(item, dict)}


def _has_editorial_cooldown_supply_fallback(story: dict) -> bool:
    queue_prune = story.get("queue_prune") or {}
    editorial = story.get("editorial") or {}
    objective_reasons = {str(reason) for reason in (queue_prune.get("objective_reasons") or [])}
    return (
        EDITORIAL_COOLDOWN_SUPPLY_FALLBACK in objective_reasons
        or editorial.get("override") == EDITORIAL_COOLDOWN_SUPPLY_FALLBACK
    )


def _operational_publish_ready_count(stories: list[dict]) -> int:
    paused = set(paused_categories().keys()) if ops_guardian_enforced() else set()
    held_ids = _agency_held_ids()
    ready = 0
    for story in stories:
        if not isinstance(story, dict) or story.get("consumed"):
            continue
        story_id = str(story.get("id") or "")
        category = str(story.get("category") or "").strip().lower()
        if story_id in held_ids or (category and category in paused):
            continue
        queue_prune = story.get("queue_prune") or {}
        publish = story.get("publish_score") or {}
        editorial = story.get("editorial") or {}
        if queue_prune.get("state") != "publish_ready":
            continue
        if publish.get("approved") is not True or publish.get("state") != "publish_ready":
            continue
        if editorial.get("approved") is not True and not _has_editorial_cooldown_supply_fallback(story):
            continue
        brain = story.get("youtube_brain") or {}
        if brain.get("risks"):
            continue
        packaging = story.get("packaging") or {}
        if packaging.get("state") == "rewrite_packaging" or packaging.get("risks"):
            continue
        ready += 1
    return ready


def _apply_editorial_cooldown_supply_fallback(story: dict) -> None:
    queue_prune = dict(story.get("queue_prune") or {})
    objective_reasons = [str(reason) for reason in (queue_prune.get("objective_reasons") or [])]
    if EDITORIAL_COOLDOWN_SUPPLY_FALLBACK not in objective_reasons:
        objective_reasons.append(EDITORIAL_COOLDOWN_SUPPLY_FALLBACK)
    queue_prune["objective_reasons"] = objective_reasons
    queue_prune["state"] = "publish_ready"
    queue_prune["score"] = max(72.0, float(queue_prune.get("score", 0) or 0))
    story["queue_prune"] = queue_prune
    original_editorial = dict(story.get("editorial") or {})
    story["editorial"] = {
        **original_editorial,
        "approved": True,
        "state": "publish_now",
        "override": EDITORIAL_COOLDOWN_SUPPLY_FALLBACK,
        "original_approved": original_editorial.get("approved"),
        "original_state": original_editorial.get("state"),
        "original_reasons": list(original_editorial.get("reasons") or []),
    }


def _apply_publish_ready_reserve_fallback(story: dict) -> None:
    queue_prune = dict(story.get("queue_prune") or {})
    objective_reasons = [str(reason) for reason in (queue_prune.get("objective_reasons") or [])]
    if PUBLISH_READY_SUPPLY_RESERVE_FALLBACK not in objective_reasons:
        objective_reasons.append(PUBLISH_READY_SUPPLY_RESERVE_FALLBACK)
    queue_prune["objective_reasons"] = objective_reasons
    queue_prune["state"] = "publish_ready"
    queue_prune["score"] = max(72.0, float(queue_prune.get("score", 0) or 0))
    story["queue_prune"] = queue_prune
    publish = dict(story.get("publish_score") or {})
    if publish.get("approved") is not True or publish.get("state") != "publish_ready":
        publish["reserve_override"] = {
            "reason": PUBLISH_READY_SUPPLY_RESERVE_FALLBACK,
            "original_approved": publish.get("approved"),
            "original_state": publish.get("state"),
            "original_opportunity_reasons": list((publish.get("opportunity") or {}).get("reasons") or []),
        }
        publish["approved"] = True
        publish["state"] = "publish_ready"
        story["publish_score"] = publish


def prune_queue(
    queue: dict, *, max_pending: int = MAX_ACTIVE_PENDING, analytics_strategy: dict | None = None
) -> tuple[dict, list[dict], dict]:
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
    seen_titles: set[str] = published_title_keys()
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
            rescue_attempted = False
            rescue_applied = False
            rescue_reasons = list(issues)
            if not (set(issues) & NON_RESCUEABLE_HARD_QUALITY_ISSUES):
                rescue_attempted = True
                rescued, applied = rescue_story(story, issues)
                if applied:
                    rescue_applied = True
                    retry_issues = quality_issues(
                        rescued,
                        seen_titles=seen_titles,
                        seen_angles=seen_angles,
                        seen_sources=seen_sources,
                        seen_scripts=seen_scripts,
                        duplicate_ids=duplicate_ids - {str(story.get("id") or "")},
                    )
                    if not retry_issues:
                        story = dict(rescued)
                        story["_queue_quality_repair"] = {
                            "attempted": True,
                            "applied": True,
                            "reasons": issues,
                            "stage": "queue_quality",
                        }
                        issues = []
                    else:
                        story = dict(rescued)
                        story["_queue_quality_repair"] = {
                            "attempted": True,
                            "applied": True,
                            "reasons": rescue_reasons,
                            "stage": "queue_quality",
                        }
                        issues = retry_issues
            if issues:
                if rescue_attempted:
                    story = dict(story)
                    story["_queue_quality_repair"] = {
                        "attempted": True,
                        "applied": rescue_applied,
                        "reasons": rescue_reasons,
                        "stage": "queue_quality",
                    }
                reasons.update(issues)
                rejected.append({"story": story, "reasons": issues, "stage": "queue_prune"})
                continue
        scored = enriched_score(story, analytics_strategy=analytics_strategy)
        quality_repair = story.get("_queue_quality_repair")
        if isinstance(quality_repair, dict) and quality_repair.get("applied"):
            score_repair = dict(scored.get("repair") or {})
            scored["repair"] = {
                "attempted": True,
                "applied": True,
                "reasons": list(
                    dict.fromkeys(
                        [str(reason) for reason in (quality_repair.get("reasons") or [])]
                        + [str(reason) for reason in (score_repair.get("reasons") or [])]
                    )
                ),
                "stage": "queue_quality",
            }
        if scored["state"] == "reject":
            reject_reasons = list(
                dict.fromkeys(
                    (scored["youtube_brain"].get("risks") or [])
                    + (scored["packaging"].get("risks") or [])
                    + (scored["rights_audit"].get("reasons") or [])
                    + ["queue_score_reject"]
                )
            )
            reasons.update(reject_reasons)
            repair.append({"story": scored["story"], "reasons": reject_reasons, "stage": "queue_repair"})
            rejected.append({"story": scored["story"], "reasons": reject_reasons, "stage": "queue_repair"})
            continue
        accepted.append(scored)

    accepted.sort(
        key=lambda item: (
            *_objective_rank(item),
            float((item["story"].get("autonomy") or {}).get("priority", 0) or 0),
            item["score"],
            int(item["story"].get("score", 0) or 0),
            item["story"].get("fetched_at", ""),
        ),
        reverse=True,
    )

    kept: list[dict] = []
    objective = load_channel_objective()
    objective_targets = objective.get("targets") or {}
    max_cluster = int(objective_targets.get("max_publish_ready_template_cluster") or 2)
    max_mechanism_cluster = int(objective_targets.get("max_publish_ready_mechanism_cluster") or 2)
    template_clusters: Counter[str] = Counter()
    mechanism_clusters: Counter[str] = Counter()
    final_seen_titles: set[str] = published_title_keys()
    final_seen_angles: set[str] = set()
    final_seen_sources: set[str] = set()
    final_seen_scripts: set[str] = set()
    for index, item in enumerate(accepted):
        story = dict(item["story"])
        story.pop("_queue_quality_repair", None)
        final_issues = quality_issues(
            story,
            seen_titles=final_seen_titles,
            seen_angles=final_seen_angles,
            seen_sources=final_seen_sources,
            seen_scripts=final_seen_scripts,
            duplicate_ids=set(),
        )
        if final_issues and not (set(final_issues) & NON_RESCUEABLE_HARD_QUALITY_ISSUES):
            rescue_attempted = True
            rescue_applied = False
            rescue_reasons = list(final_issues)
            rescued, applied = rescue_story(story, final_issues)
            if applied:
                rescue_applied = True
                rescored = enriched_score(rescued, analytics_strategy=analytics_strategy)
                if rescored["state"] != "reject":
                    retry_story = dict(rescored["story"])
                    retry_story.pop("_queue_quality_repair", None)
                    retry_issues = quality_issues(
                        retry_story,
                        seen_titles=final_seen_titles,
                        seen_angles=final_seen_angles,
                        seen_sources=final_seen_sources,
                        seen_scripts=final_seen_scripts,
                        duplicate_ids=set(),
                    )
                    if not retry_issues:
                        original_repair = dict(item.get("repair") or {})
                        rescored_repair = dict(rescored.get("repair") or {})
                        rescored["repair"] = {
                            "attempted": True,
                            "applied": True,
                            "reasons": list(
                                dict.fromkeys(
                                    [str(reason) for reason in final_issues]
                                    + [str(reason) for reason in (original_repair.get("reasons") or [])]
                                    + [str(reason) for reason in (rescored_repair.get("reasons") or [])]
                                )
                            ),
                            "stage": "queue_quality_final",
                        }
                        item = rescored
                        story = retry_story
                        final_issues = []
                    else:
                        story = retry_story
                        story["_queue_quality_repair"] = {
                            "attempted": True,
                            "applied": True,
                            "reasons": rescue_reasons,
                            "stage": "queue_quality_final",
                        }
                        final_issues = retry_issues
                else:
                    story = dict(rescored.get("story") or rescued)
                    story["_queue_quality_repair"] = {
                        "attempted": True,
                        "applied": True,
                        "reasons": rescue_reasons,
                        "stage": "queue_quality_final",
                    }
        else:
            rescue_attempted = False
            rescue_applied = False
            rescue_reasons = []
        if final_issues:
            if rescue_attempted:
                story = dict(story)
                story["_queue_quality_repair"] = {
                    "attempted": True,
                    "applied": rescue_applied,
                    "reasons": rescue_reasons,
                    "stage": "queue_quality_final",
                }
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
        story["rights_audit"] = item["rights_audit"]
        editor = item.get("editorial") or {"approved": True, "state": "publish_now", "reasons": []}
        story["editorial"] = editor
        if editor.get("series"):
            story["series"] = editor["series"]
        story["queue_repair"] = item["repair"]
        effective_state = item["state"]
        effective_score = item["score"]
        gate = (item["publish_score"] or {}).get("objective_gate") or {}
        objective_reasons = [f"objective_gate:{reason}" for reason in (gate.get("reasons") or [])]
        if editor and not editor.get("approved", False):
            editor_reasons = [f"editor_in_chief:{reason}" for reason in (editor.get("reasons") or [])]
            if not editor_reasons:
                editor_reasons = [f"editor_in_chief:{editor.get('state') or 'not_approved'}"]
            objective_reasons.extend(editor_reasons)
            effective_state = "reject" if editor.get("state") == "discard" else "rewrite"
            effective_score = max(0.0, float(effective_score) - 8.0)
        if effective_state == "rewrite" and _soft_rewrite_can_publish(
            item, score=float(effective_score), editor=editor
        ):
            effective_state = "publish_ready"
            objective_reasons.append("soft_ready_fallback")
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

    publish_ready_count = _operational_publish_ready_count(kept)
    if publish_ready_count < PUBLISH_READY_RESERVE_TARGET:
        fallback_candidates = [story for story in kept if _editorial_cooldown_supply_candidate(story)]
        fallback_candidates.sort(
            key=lambda story: (
                float((story.get("autonomy") or {}).get("priority", 0) or 0),
                float((story.get("publish_score") or {}).get("score", 0) or 0),
                float((story.get("queue_prune") or {}).get("score", 0) or 0),
            ),
            reverse=True,
        )
        for story in fallback_candidates[: max(0, PUBLISH_READY_RESERVE_TARGET - publish_ready_count)]:
            _apply_editorial_cooldown_supply_fallback(story)
            reasons.update([EDITORIAL_COOLDOWN_SUPPLY_FALLBACK])
        publish_ready_count = _operational_publish_ready_count(kept)
    if publish_ready_count < PUBLISH_READY_RESERVE_TARGET:
        paused = set(paused_categories().keys()) if ops_guardian_enforced() else set()
        held_ids = _agency_held_ids()
        reserve_candidates = [
            story
            for story in kept
            if _publish_ready_reserve_candidate(story)
            and str(story.get("id") or "") not in held_ids
            and str(story.get("category") or "").strip().lower() not in paused
        ]
        reserve_candidates.sort(
            key=lambda story: (
                float((story.get("autonomy") or {}).get("priority", 0) or 0),
                float((story.get("publish_score") or {}).get("score", 0) or 0),
                float((story.get("queue_prune") or {}).get("score", 0) or 0),
            ),
            reverse=True,
        )
        for story in reserve_candidates[: max(0, PUBLISH_READY_RESERVE_TARGET - publish_ready_count)]:
            _apply_publish_ready_reserve_fallback(story)
            reasons.update([PUBLISH_READY_SUPPLY_RESERVE_FALLBACK])

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
