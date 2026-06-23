#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Upload generated vertical videos to YouTube Shorts."""
from __future__ import annotations

import json
import logging
import os
import random
import sys
import time
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from scripts.upload_intent import build_upload_intent, duplicate_slot_uploaded, duplicate_uploaded, write_upload_intent
from utils.api_quota_budget import estimate_publish_run_cost, write_quota_ledger_row
from utils.media_lifecycle import cleanup_meta_artifacts
from utils.session_graph import pinned_comment_payload
from utils.time_semantics import temporal_fields
from utils.youtube_oauth import DEFAULT_SCOPES, credentials_from_token_info, load_token_info, token_status_message
from utils.publish_schedule import active_slot_label, canonical_slots, slot_label

_LANGUAGE = os.environ.get("LANGUAGE", "en").strip() or "en"
for i, arg in enumerate(sys.argv):
    if arg == "--language" and i + 1 < len(sys.argv):
        _LANGUAGE = sys.argv[i + 1]
    elif arg.startswith("--language="):
        _LANGUAGE = arg.split("=", 1)[1]

LOG_FILE = f"upload_youtube{'' if _LANGUAGE == 'en' else '_' + _LANGUAGE}.log"
VIDEOS_DIR = Path("_videos") if _LANGUAGE == "en" else Path(f"_videos_{_LANGUAGE}")
TOKEN_FILE = Path("youtube_token.json") if _LANGUAGE == "en" else Path(f"youtube_token_{_LANGUAGE}.json")
SCOPES = DEFAULT_SCOPES
RETRIABLE_STATUS_CODES = {500, 502, 503, 504}
MAX_RETRIES = 6
PLAYLIST_PREFIX = "Wild Brief | "
PILLAR_PLAYLIST_BY_CATEGORY = {
    "volcanoes": "Earth Engine",
    "weather": "Earth Engine",
    "rivers": "Earth Engine",
    "mountains": "Earth Engine",
    "geology": "Earth Engine",
    "fungi": "Hidden Network",
    "trees": "Hidden Network",
    "forests": "Hidden Network",
    "ecosystems": "Hidden Network",
    "rare_phenomena": "Rare Earth",
    "earth_from_space": "Planet Earth",
    "conservation": "Planet Repair",
    "discoveries": "Discovery Brief",
    "plants": "Biology Brief",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)


def _load_credentials() -> Credentials:
    info = load_token_info(TOKEN_FILE)
    if not info.present:
        raise FileNotFoundError(token_status_message(info))
    return credentials_from_token_info(info, SCOPES)


def get_youtube_service():
    return build("youtube", "v3", credentials=_load_credentials(), cache_discovery=False)


def check_auth() -> bool:
    """Validate OAuth credentials before spending time rendering a Short."""
    _load_credentials()
    log.info("YouTube auth preflight OK.")
    return True


def _collect_pending_meta(videos_dir: Path) -> list[Path]:
    return sorted(p for p in videos_dir.glob("*.json") if p.stem.startswith(("short-", "roundup-")))


def _normalise_tags(tags) -> list[str]:
    out, seen = [], set()
    for tag in tags or []:
        t = str(tag).strip().lstrip("#")
        if t and t.lower() not in seen:
            out.append(t[:30])
            seen.add(t.lower())
        if len(out) >= 15:
            break
    return out


def _youtube_title(meta: dict) -> str:
    title = (meta.get("title") or "Nature fact of the day").strip()
    return title if len(title) <= 100 else title[:97].rstrip(" .,;:-") + "..."


def _youtube_description(meta: dict) -> str:
    mode = os.environ.get("YOUTUBE_DESCRIPTION_MODE", "full").strip().lower()
    if mode in {"", "empty", "none", "off", "0"}:
        return ""
    description = (meta.get("description") or _youtube_title(meta)).strip()
    existing = {part.lower() for part in description.split() if part.startswith("#")}
    missing = [tag for tag in ("#Shorts", "#NatureFacts", "#WildBrief", "#EarthScience") if tag.lower() not in existing]
    if missing:
        description += "\n\n" + " ".join(missing)
    source = (meta.get("source_url") or "").strip()
    if source and source not in description:
        description += "\n\nSource: " + source
    return description[:5000]


def _current_publish_slot(now: datetime | None = None) -> tuple[str, str]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    label = active_slot_label(current) or slot_label(current)
    try:
        hour, minute = [int(part) for part in label.split(":", 1)]
    except Exception:
        label = slot_label(current)
        hour, minute = current.hour, current.minute
    start = datetime.combine(current.date(), dt_time(hour, minute, tzinfo=timezone.utc), tzinfo=timezone.utc)
    if start > current:
        start -= timedelta(days=1)
    return label, start.strftime("%Y-%m-%dT%H:%MZ")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_utc(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _rfc3339_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _schedule_slots() -> list[str]:
    configured = [item.strip() for item in os.environ.get("YOUTUBE_SCHEDULE_SLOTS_UTC", "").split(",") if item.strip()]
    slots = configured or canonical_slots()
    out: list[str] = []
    for slot in slots:
        try:
            hour, minute = str(slot).split(":", 1)
            out.append(f"{int(hour):02d}:{int(minute):02d}")
        except Exception:
            continue
    return sorted(set(out)) or ["00:23"]


def _scheduled_publish_at(meta: dict, *, sequence_index: int = 0, now: datetime | None = None) -> str:
    explicit = (
        meta.get("scheduled_publish_at")
        or meta.get("youtube_publish_at")
        or meta.get("publish_at")
        or meta.get("publishAt")
    )
    parsed_explicit = _parse_utc(str(explicit or ""))
    if parsed_explicit:
        return _rfc3339_z(parsed_explicit)
    if not _env_bool("YOUTUBE_SCHEDULE_UPLOADS", False):
        return ""

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    start = _parse_utc(os.environ.get("YOUTUBE_SCHEDULE_START_UTC", "")) or (current + timedelta(hours=1))
    offset = max(0, int(os.environ.get("YOUTUBE_SCHEDULE_OFFSET", "0") or 0) + int(sequence_index or 0))
    candidates: list[datetime] = []
    day = start.date()
    slots = _schedule_slots()
    while len(candidates) <= offset:
        for label in slots:
            hour, minute = [int(part) for part in label.split(":", 1)]
            candidate = datetime.combine(day, dt_time(hour, minute, tzinfo=timezone.utc), tzinfo=timezone.utc)
            if candidate >= start:
                candidates.append(candidate)
        day += timedelta(days=1)
    return _rfc3339_z(candidates[offset])


def _video_url(video_id: str) -> str:
    return f"https://www.youtube.com/shorts/{video_id}" if video_id else ""


def _safe_label(value: str, fallback: str = "Nature Facts") -> str:
    label = " ".join(str(value or "").replace("_", " ").split()).strip(" -|")
    if not label:
        label = fallback
    return label[:60]


def _playlist_titles(meta: dict) -> list[str]:
    category = str(meta.get("category") or "").strip().lower()
    pillar = PILLAR_PLAYLIST_BY_CATEGORY.get(category, "")
    labels = [
        "Start Here",
        _safe_label(pillar, ""),
        _safe_label(meta.get("series"), ""),
        _safe_label(meta.get("category"), ""),
    ]
    out: list[str] = []
    seen: set[str] = set()
    for label in labels:
        if not label:
            continue
        title = f"{PLAYLIST_PREFIX}{label.title()}"
        key = title.lower()
        if key not in seen:
            out.append(title[:150])
            seen.add(key)
    return out or [f"{PLAYLIST_PREFIX}Nature Facts"]


def _comment_text(meta: dict) -> str:
    packaging = meta.get("packaging") if isinstance(meta.get("packaging"), dict) else {}
    text = str(
        meta.get("pinned_comment")
        or packaging.get("pinned_comment")
        or meta.get("session_comment")
        or meta.get("cta_prompt")
        or (
            pinned_comment_payload(meta, meta.get("session_handoff"))
            if isinstance(meta.get("session_handoff"), dict) and meta.get("session_handoff")
            else ""
        )
        or ""
    ).strip()
    if not text:
        text = "👇 What do you think about this? Is the science textbook lying to us? Drop your thoughts below!"
    return text[:500]


def _is_uploadable_meta(meta: dict) -> bool:
    audit = meta.get("pre_publish_audit")
    if isinstance(audit, dict) and audit.get("approved") is False:
        return False
    return Path(meta.get("video") or "").is_file()


def _done_marker(video_id: str, meta: dict) -> dict:
    """Persist the production signals needed by analytics and digest."""
    keys = (
        "title",
        "description",
        "tags",
        "category",
        "series",
        "editorial",
        "is_short",
        "has_broll",
        "has_captions",
        "script_quality_grade",
        "production_quality",
        "pexels_video_id",
        "pexels_download_url",
        "source_clip_id",
        "source",
        "source_url",
        "source_license",
        "source_license_evidence",
        "source_creator",
        "source_collection",
        "rights_policy",
        "commons_page_url",
        "commons_license",
        "commons_artist",
        "gbif",
        "visual_qa",
        "visual_ctr",
        "experiments",
        "hook",
        "story_format",
        "hook_audit",
        "title_audit",
        "narrator_voice",
        "human_voice",
        "humanity",
        "studio_polish",
        "studio_state",
        "ai_rewrite",
        "pre_publish_audit",
        "monetization_audit",
        "seo_score",
        "seo_optimisation",
        "seo_lint",
        "music_bed_variant",
        "publish_score",
        "youtube_brain",
        "packaging",
        "pinned_comment",
        "opportunity_score",
        "retention_score",
        "weak_content",
        "subscriber_conversion",
        "loop_render_applied",
        "end_card_text",
        "variant_assignment_log",
        "cta_prompt",
        "replay_prompt",
        "youtube_operations",
        "opening_audit",
        "opening_gate_v2",
        "story_pattern",
        "hook_library",
        "hook_library_score",
        "payoff_control",
        "payoff_second",
        "loop_semantics",
        "loop_density",
        "callback_keyword_overlap",
        "claim_risk",
        "rights_guard",
        "source_provenance",
        "originality_pack",
        "frame_zero_packaging",
        "search_enrichment",
        "publish_ts_utc",
        "scheduled_publish_at",
        "youtube_privacy",
        "publish_slot",
        "publish_slot_key",
        "publish_day_pt",
        "quota_day_pt",
        "views_regime",
        "upload_intent_key",
        "upload_intent",
        "session_handoff",
        "session_action",
        "audience_strategy",
    )
    defaults = {
        "title": "",
        "description": "",
        "tags": [],
        "category": "",
        "series": "",
        "editorial": {},
        "is_short": True,
        "has_broll": False,
        "has_captions": False,
        "production_quality": {},
        "pexels_video_id": "",
        "pexels_download_url": "",
        "source_clip_id": "",
        "source": "",
        "source_url": "",
        "source_license": "",
        "source_license_evidence": "",
        "source_creator": "",
        "source_collection": "",
        "rights_policy": "",
        "commons_page_url": "",
        "commons_license": "",
        "commons_artist": "",
        "gbif": {},
        "visual_qa": {},
        "visual_ctr": {},
        "experiments": {},
        "hook": "",
        "story_format": "",
        "hook_audit": {},
        "title_audit": {},
        "narrator_voice": "",
        "human_voice": {},
        "humanity": {},
        "studio_polish": {},
        "studio_state": "",
        "ai_rewrite": {},
        "pre_publish_audit": {},
        "monetization_audit": {},
        "seo_score": {},
        "seo_optimisation": {},
        "seo_lint": {},
        "music_bed_variant": "",
        "publish_score": {},
        "youtube_brain": {},
        "packaging": {},
        "pinned_comment": "",
        "opportunity_score": {},
        "retention_score": {},
        "weak_content": {},
        "subscriber_conversion": {},
        "loop_render_applied": {},
        "end_card_text": "",
        "variant_assignment_log": {},
        "cta_prompt": "",
        "replay_prompt": "",
        "youtube_operations": {},
        "opening_audit": {},
        "opening_gate_v2": {},
        "story_pattern": {},
        "hook_library": {},
        "hook_library_score": {},
        "payoff_control": {},
        "payoff_second": 0,
        "loop_semantics": {},
        "loop_density": 0,
        "callback_keyword_overlap": 0,
        "claim_risk": {},
        "rights_guard": {},
        "source_provenance": {},
        "originality_pack": {},
        "frame_zero_packaging": {},
        "search_enrichment": {},
        "publish_ts_utc": "",
        "scheduled_publish_at": "",
        "publish_slot": "",
        "publish_slot_key": "",
        "youtube_privacy": "",
        "publish_day_pt": "",
        "quota_day_pt": "",
        "views_regime": "",
        "upload_intent_key": "",
        "upload_intent": {},
        "session_handoff": {},
        "session_action": {},
        "audience_strategy": {},
    }
    marker = {key: meta.get(key, defaults.get(key)) for key in keys}
    if not marker.get("subscriber_conversion") and isinstance(marker.get("packaging"), dict):
        marker["subscriber_conversion"] = marker["packaging"].get("subscriber_conversion", {})
    uploaded_at = datetime.now(timezone.utc)
    public_at = marker.get("scheduled_publish_at") or marker.get("publish_ts_utc") or uploaded_at
    marker.update(temporal_fields(public_at, now=uploaded_at))
    marker.update(
        {
            "video_id": video_id,
            "url": _video_url(video_id),
            "uploaded_at": uploaded_at.isoformat(),
            "platform": "youtube",
            "language": _LANGUAGE,
        }
    )
    return marker


def _execute(request) -> dict:
    response = request.execute()
    return response if isinstance(response, dict) else {}


def _find_playlist_id(youtube, title: str) -> str:
    page_token = None
    while True:
        request = youtube.playlists().list(
            part="snippet",
            mine=True,
            maxResults=50,
            pageToken=page_token,
        )
        response = _execute(request)
        for item in response.get("items", []) or []:
            snippet = item.get("snippet") or {}
            if str(snippet.get("title") or "").strip().lower() == title.lower():
                return str(item.get("id") or "")
        page_token = response.get("nextPageToken")
        if not page_token:
            return ""


def _create_playlist(youtube, title: str) -> str:
    request = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": "Wild Brief Shorts grouped for easier binge watching.",
            },
            "status": {"privacyStatus": "public"},
        },
    )
    response = _execute(request)
    return str(response.get("id") or "")


def _playlist_has_video(youtube, playlist_id: str, video_id: str) -> bool:
    try:
        response = _execute(
            youtube.playlistItems().list(
                part="snippet",
                playlistId=playlist_id,
                videoId=video_id,
                maxResults=1,
            )
        )
    except TypeError:
        response = _execute(
            youtube.playlistItems().list(
                part="snippet",
                playlistId=playlist_id,
                maxResults=50,
            )
        )
    except HttpError as exc:
        if getattr(exc.resp, "status", None) == 404:
            return False
        raise
    for item in response.get("items", []) or []:
        resource = (item.get("snippet") or {}).get("resourceId") or {}
        if str(resource.get("videoId") or "") == video_id:
            return True
    return False


def _ensure_playlist(youtube, title: str) -> str:
    return _find_playlist_id(youtube, title) or _create_playlist(youtube, title)


def _add_video_to_playlist(youtube, playlist_id: str, video_id: str) -> str:
    if _playlist_has_video(youtube, playlist_id, video_id):
        return "already_present"
    request = youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id,
                },
            }
        },
    )
    response = _execute(request)
    return str(response.get("id") or "added")


def _post_cta_comment(youtube, video_id: str, text: str) -> dict:
    request = youtube.commentThreads().insert(
        part="snippet",
        body={
            "snippet": {
                "videoId": video_id,
                "topLevelComment": {
                    "snippet": {
                        "textOriginal": text,
                    }
                },
            }
        },
    )
    response = _execute(request)
    comment = ((response.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
    return {
        "posted": True,
        "comment_thread_id": response.get("id", ""),
        "author_channel_id": ((comment.get("authorChannelId") or {}).get("value") or ""),
        "pin_status": "not_supported_by_youtube_data_api",
    }


def run_post_upload_operations(youtube, video_id: str, meta: dict) -> dict:
    """Run YouTube-only growth operations after a successful upload."""
    if os.environ.get("YOUTUBE_POST_UPLOAD_AUTOMATION", "1").lower() in {"0", "false", "no"}:
        return {"enabled": False}
    result: dict = {
        "enabled": True,
        "playlists": [],
        "comment": {"posted": False, "pin_status": "not_supported_by_youtube_data_api"},
    }
    for title in _playlist_titles(meta):
        item = {"title": title, "added": False, "playlist_id": "", "error": ""}
        try:
            playlist_id = _ensure_playlist(youtube, title)
            item["playlist_id"] = playlist_id
            if playlist_id:
                item["playlist_item_id"] = _add_video_to_playlist(youtube, playlist_id, video_id)
                item["added"] = True
        except Exception as exc:
            item["error"] = f"{type(exc).__name__}: {exc}"
            log.warning("Playlist operation failed for %s: %s", title, exc)
        result["playlists"].append(item)
    try:
        result["comment"] = _post_cta_comment(youtube, video_id, _comment_text(meta))
    except Exception as exc:
        result["comment"] = {
            "posted": False,
            "error": f"{type(exc).__name__}: {exc}",
            "pin_status": "not_supported_by_youtube_data_api",
        }
        log.warning("CTA comment operation failed: %s", exc)
    return result


def _execute_resumable(request) -> dict:
    response, retry = None, 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                log.info("Upload: %d%%", int(status.progress() * 100))
        except HttpError as exc:
            if exc.resp.status not in RETRIABLE_STATUS_CODES:
                raise
            error = f"HTTP {exc.resp.status}"
        except (OSError, TimeoutError) as exc:
            error = f"{type(exc).__name__}: {exc}"
        else:
            continue
        retry += 1
        if retry > MAX_RETRIES:
            raise RuntimeError(f"YouTube upload failed after retries: {error}")
        time.sleep(random.uniform(1, 2**retry))
    return response


def upload_video(youtube, meta: dict, *, sequence_index: int = 0) -> str | None:
    video_path = Path(meta.get("video") or "")
    if not video_path.exists():
        log.error("Video not found: %s", video_path)
        return None
    privacy = (os.environ.get("YOUTUBE_PRIVACY") or meta.get("youtube_privacy") or "public").strip().lower()
    if privacy not in {"public", "unlisted", "private"}:
        privacy = "public"
    scheduled_publish_at = _scheduled_publish_at(meta, sequence_index=sequence_index)
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
    if scheduled_publish_at:
        status["privacyStatus"] = "private"
        status["publishAt"] = scheduled_publish_at
        meta["scheduled_publish_at"] = scheduled_publish_at
        meta["publish_ts_utc"] = scheduled_publish_at
        meta["youtube_privacy"] = "private"
    else:
        meta["youtube_privacy"] = privacy
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": _youtube_title(meta),
                "description": _youtube_description(meta),
                "tags": _normalise_tags(meta.get("tags")),
                "categoryId": str(meta.get("youtube_category_id") or "15"),
            },
            "status": status,
        },
        media_body=MediaFileUpload(str(video_path), mimetype="video/mp4", chunksize=-1, resumable=True),
        notifySubscribers=False,
    )
    response = _execute_resumable(request)
    video_id = response.get("id")
    if not video_id:
        return None
    thumb = Path(meta.get("thumbnail") or "")
    if thumb.exists():
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumb))).execute()
        except HttpError as exc:
            log.warning("Thumbnail upload failed: HTTP %s", exc.resp.status)
    if scheduled_publish_at:
        log.info("Scheduled: %s at %s", _video_url(video_id), scheduled_publish_at)
    else:
        log.info("Published: %s", _video_url(video_id))
    return video_id


def main() -> None:
    from utils.panic import abort_if_halted

    abort_if_halted("upload_youtube")
    if "--check-auth" in sys.argv:
        try:
            check_auth()
        except Exception as exc:
            log.error("YouTube auth preflight failed: %s", exc)
            sys.exit(2)
        return
    try:
        youtube = get_youtube_service()
    except Exception as exc:
        log.error("YouTube auth failed: %s", exc)
        sys.exit(2)
    pending, attempted, uploaded = _collect_pending_meta(VIDEOS_DIR), 0, 0
    require_upload = _env_bool("REQUIRE_UPLOAD_ON_PUBLISH", False)
    if require_upload and not pending:
        log.error("Publish window required an upload, but no generated Short metadata was found in %s.", VIDEOS_DIR)
        sys.exit(1)
    quota_row = write_quota_ledger_row(estimate_publish_run_cost(videos=len(pending)))
    if (quota_row.get("guard") or {}).get("block"):
        log.error("Quota guard blocked upload: %s", (quota_row.get("guard") or {}).get("reason"))
        return
    for meta_file in pending:
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception as exc:
            log.error("Failed to read %s: %s", meta_file.name, exc)
            continue
        if not isinstance(meta, dict):
            continue
        if not _is_uploadable_meta(meta):
            log.warning("Skipping orphan metadata without video: %s", meta_file.name)
            continue
        slot_label_value, slot_key = _current_publish_slot()
        meta["publish_slot"] = meta.get("publish_slot") or slot_label_value
        meta["publish_slot_key"] = meta.get("publish_slot_key") or slot_key
        intent_slot = str(meta.get("publish_slot_key") or meta.get("publish_slot") or "")
        slot_duplicate = duplicate_slot_uploaded(intent_slot)
        if slot_duplicate and os.environ.get("UPLOAD_SLOT_IDEMPOTENCY_MODE", "block").strip().lower() == "block":
            log.warning(
                "Skipping duplicate publish slot %s already published as %s",
                intent_slot,
                slot_duplicate.get("video_id"),
            )
            continue
        intent = build_upload_intent(meta, meta_file=str(meta_file), slot=intent_slot)
        duplicate = duplicate_uploaded(intent)
        meta["upload_intent_key"] = intent["idempotency_key"]
        meta["upload_intent"] = intent
        if duplicate and os.environ.get("UPLOAD_IDEMPOTENCY_MODE", "block").strip().lower() == "block":
            log.warning(
                "Skipping duplicate upload intent %s already published as %s",
                intent["idempotency_key"],
                duplicate.get("video_id"),
            )
            continue
        write_upload_intent(intent)
        attempted += 1
        video_id = upload_video(youtube, meta, sequence_index=uploaded)
        if not video_id:
            continue
        uploaded_intent = {
            **intent,
            "status": "uploaded",
            "video_id": video_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        write_upload_intent(uploaded_intent)
        meta["upload_intent"] = uploaded_intent
        meta["youtube_operations"] = run_post_upload_operations(youtube, video_id, meta)
        meta["session_action"] = {
            "applied": bool(meta["youtube_operations"].get("comment", {}).get("posted")),
            "operator_assist": meta["youtube_operations"].get("comment", {}).get("pin_status")
            == "not_supported_by_youtube_data_api",
            "comment_text": _comment_text(meta),
        }
        marker = _done_marker(video_id, meta)
        marker["media_lifecycle"] = cleanup_meta_artifacts(meta)
        meta_file.with_suffix(".done").write_text(
            json.dumps(marker, indent=2),
            encoding="utf-8",
        )
        try:
            from fetch_animals import record_published_clip

            record_published_clip(
                pexels_video_id=meta.get("pexels_video_id", ""),
                story_id=meta.get("story_id", ""),
                pexels_url=meta.get("pexels_download_url", ""),
                source_clip_id=meta.get("source_clip_id", ""),
                source=meta.get("source", ""),
                source_url=meta.get("source_url", ""),
                source_license=meta.get("source_license", ""),
                source_license_evidence=meta.get("source_license_evidence", ""),
                platform_video_id=video_id,
            )
        except Exception as exc:
            log.warning("published_clips ledger update failed: %s", exc)
        meta_file.unlink()
        uploaded += 1
    log.info("%d/%d video(s) uploaded to YouTube.", uploaded, attempted)
    if (attempted and uploaded == 0) or (require_upload and uploaded == 0):
        sys.exit(1)


if __name__ == "__main__":
    main()
