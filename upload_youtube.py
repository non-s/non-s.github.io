#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Upload generated vertical videos to YouTube Shorts."""

from __future__ import annotations

import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from datetime import time as dt_time
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from scripts.upload_intent import build_upload_intent, duplicate_slot_uploaded, write_upload_intent
from utils.api_quota_budget import estimate_publish_run_cost, write_quota_ledger_row
from utils.media_lifecycle import cleanup_meta_artifacts
from utils.publish_schedule import active_slot_label, canonical_slots, slot_label
from utils.time_semantics import temporal_fields
from utils.youtube_oauth import DEFAULT_SCOPES, credentials_from_token_info, load_token_info, token_status_message

_LANGUAGE = os.environ.get("LANGUAGE", "en").strip() or "en"
for i, arg in enumerate(sys.argv):
    if arg == "--language" and i + 1 < len(sys.argv):
        _LANGUAGE = sys.argv[i + 1]
    elif arg.startswith("--language="):
        _LANGUAGE = arg.split("=", 1)[1]

LOG_FILE = f"upload_youtube{'' if _LANGUAGE == 'en' else '_' + _LANGUAGE}.log"
VIDEOS_DIR = Path("_videos") if _LANGUAGE == "en" else Path(f"_videos_{_LANGUAGE}")
TOKEN_FILE = Path("youtube_token.json") if _LANGUAGE == "en" else Path(f"youtube_token_{_LANGUAGE}.json")
YOUTUBE_INTELLIGENCE_FILE = Path("_data/youtube_intelligence.json")
SCOPES = DEFAULT_SCOPES
RETRIABLE_STATUS_CODES = {500, 502, 503, 504}
MAX_RETRIES = 6
PLAYLIST_PREFIX = os.environ.get("CHANNEL_PLAYLIST_PREFIX", "")
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
    return sorted(p for p in videos_dir.glob("*.json") if p.stem.startswith(("short-", "roundup-", "mix-")))


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
    title = (meta.get("seo_title") or meta.get("title") or "New Short").strip()
    return title if len(title) <= 100 else title[:97].rstrip(" .,;:-") + "..."


def _title_key(title: str) -> str:
    return re.sub(r"\s+", " ", str(title or "").strip().lower())


def _existing_upload_titles(videos_dir: Path = VIDEOS_DIR) -> set[str]:
    titles: set[str] = set()
    for path in sorted(videos_dir.glob("*.done")):
        try:
            marker = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(marker, dict):
            key = _title_key(marker.get("title") or "")
            if key:
                titles.add(key)
    return titles


def _read_json_object(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _normalise_channel_upload(row: dict, *, source: str) -> dict:
    title = str(row.get("title") or "").strip()
    video_id = str(row.get("video_id") or row.get("id") or "").strip()
    if not title or not video_id:
        return {}
    return {
        "video_id": video_id,
        "title": title,
        "published_at": str(row.get("published_at") or row.get("publishedAt") or ""),
        "source": source,
    }


def _fetch_recent_channel_uploads(youtube, *, limit: int = 50) -> list[dict]:
    if youtube is None or not hasattr(youtube, "channels") or not hasattr(youtube, "playlistItems"):
        return []
    channel_response = _execute(youtube.channels().list(part="contentDetails", mine=True))
    channels = channel_response.get("items") or []
    playlist_id = ""
    if channels:
        playlist_id = str(
            (((channels[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads") or "")
        )
    if not playlist_id:
        return []
    uploads: list[dict] = []
    page_token = None
    while len(uploads) < limit:
        response = _execute(
            youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=min(50, limit - len(uploads)),
                pageToken=page_token,
            )
        )
        for item in response.get("items", []) or []:
            snippet = item.get("snippet") or {}
            content = item.get("contentDetails") or {}
            normalised = _normalise_channel_upload(
                {
                    "video_id": content.get("videoId") or item.get("id", ""),
                    "title": snippet.get("title", ""),
                    "published_at": content.get("videoPublishedAt") or snippet.get("publishedAt", ""),
                },
                source="youtube_api.uploads_playlist",
            )
            if normalised:
                uploads.append(normalised)
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return uploads


def _phrase_words(value: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", str(value or ""))


def _display_phrase(value: str) -> str:
    words = _phrase_words(value)
    phrase = " ".join(words[:4]).lower()
    return phrase[:1].upper() + phrase[1:] if phrase else ""


_CATEGORY_DETAIL_CONFLICTS = {
    "plants": {
        "bee",
        "bees",
        "bird",
        "birds",
        "butterfly",
        "butterflies",
        "insect",
        "insects",
        "pollinator",
        "pollinators",
        "wasp",
        "wasps",
    }
}

_CATEGORY_REPLACEMENT_TERMS = {
    "plants": {
        "algae",
        "blooms",
        "blossoms",
        "buds",
        "flowers",
        "fronds",
        "grasses",
        "hairs",
        "leaves",
        "mosses",
        "petals",
        "plants",
        "roots",
        "seeds",
        "stems",
        "trees",
        "vines",
    }
}


def _category_key(value: str) -> str:
    words = _phrase_words(str(value or "").lower().replace("_", " "))
    return words[0] if words else ""


def _detail_conflicts_with_category(detail: str, category: str) -> bool:
    conflicts = _CATEGORY_DETAIL_CONFLICTS.get(_category_key(category), set())
    return bool(conflicts and conflicts & {word.lower() for word in _phrase_words(detail)})


def _can_replace_category_anchor(detail: str, category: str) -> bool:
    allowed = _CATEGORY_REPLACEMENT_TERMS.get(_category_key(category))
    if not allowed:
        return True
    words = {word.lower() for word in _phrase_words(detail)}
    return bool(words & allowed)


def _search_intent_title_details(meta: dict) -> list[str]:
    values: list[str] = []

    def collect(package) -> None:
        if not isinstance(package, dict):
            return
        for key in ("visible_cue", "subject"):
            value = str(package.get(key) or "").strip()
            if value:
                values.append(value)
        terms = package.get("terms") or []
        if isinstance(terms, list):
            values.extend(str(term) for term in terms if str(term or "").strip())
        nested = package.get("search_intent")
        if isinstance(nested, dict):
            collect(nested)

    collect(meta.get("search_intent"))
    collect(meta.get("retention_contract"))
    return values


def _candidate_title_details(meta: dict) -> list[str]:
    generic = {
        "animal",
        "animals",
        "biology",
        "earth",
        "fact",
        "facts",
        "nature",
        "science",
        "short",
        "shorts",
        "wild",
        "wildlife",
    }
    category = str(meta.get("category") or "").strip().lower().replace("_", " ")
    generic.update(_phrase_words(category))
    title_key = _title_key(_youtube_title(meta))
    candidates: list[str] = []
    values: list[str] = _search_intent_title_details(meta)
    for key in ("yt_tags", "tags", "discovery_hashtags"):
        values.extend(str(item) for item in (meta.get(key) or []))
    values.extend(
        str(meta.get(key) or "")
        for key in ("subject", "source_caption", "visual_search", "description")
        if meta.get(key)
    )
    for value in values:
        text = str(value or "")
        if ":" in text:
            text = text.rsplit(":", 1)[-1]
        phrase = _display_phrase(text)
        if not phrase:
            continue
        words = [word.lower() for word in _phrase_words(phrase)]
        if len(words) > 4 or all(word in generic for word in words):
            continue
        if _detail_conflicts_with_category(phrase, category):
            continue
        key = " ".join(words)
        if key in title_key or key in {_title_key(item) for item in candidates}:
            continue
        candidates.append(phrase)
    return candidates


def _title_variants(title: str, meta: dict) -> list[str]:
    words = _phrase_words(title)
    if not words:
        return []
    category_words = {word.lower() for word in _phrase_words(str(meta.get("category") or ""))}
    for word in list(category_words):
        if word.endswith("s"):
            category_words.add(word[:-1])
        else:
            category_words.add(word + "s")
    rest = title[len(words[0]) :].strip()
    variants: list[str] = []
    for detail in _candidate_title_details(meta):
        if (
            rest
            and words[0].lower() in category_words
            and _can_replace_category_anchor(detail, str(meta.get("category") or ""))
        ):
            variants.append(f"{detail} {rest}")
        variants.append(f"{title} | {detail}")
    story_id = re.sub(r"[^A-Za-z0-9]", "", str(meta.get("story_id") or meta.get("id") or ""))
    if story_id:
        variants.append(f"{title} clip {story_id[:6]}")
    return variants


def _apply_unique_upload_title(meta: dict, existing_titles: set[str] | None = None) -> dict:
    """Mutate upload metadata so a Short never repeats an already published title."""
    existing = set(existing_titles or set())
    original = _youtube_title(meta)
    if _title_key(original) not in existing:
        return {"applied": False, "title": original}
    for variant in _title_variants(original, meta):
        candidate = _youtube_title({"title": variant})
        if not candidate or _title_key(candidate) in existing:
            continue
        description = str(meta.get("description") or "")
        meta["title"] = candidate
        if description and _title_key(description[: len(original)]) == _title_key(original):
            meta["description"] = candidate + description[len(original) :]
        meta["upload_title_dedupe"] = {
            "applied": True,
            "reason": "published_title_collision",
            "before": original,
            "after": candidate,
        }
        return meta["upload_title_dedupe"]
    return {"applied": False, "title": original, "reason": "no_unique_variant_available"}


def _youtube_description(meta: dict) -> str:
    mode = os.environ.get("YOUTUBE_DESCRIPTION_MODE", "full").strip().lower()
    if mode in {"", "empty", "none", "off", "0"}:
        return ""
    description = (meta.get("description") or _youtube_title(meta)).strip()
    existing = {part.lower() for part in description.split() if part.startswith("#")}
    default_hashtags = [
        tag.strip() for tag in os.environ.get("CHANNEL_DEFAULT_HASHTAGS", "#Shorts").split(",") if tag.strip()
    ]
    if meta.get("is_short") is False:
        # #Shorts on a long-form video is just wrong, not merely harmless --
        # don't carry over a hashtag list tuned for the vertical Shorts.
        default_hashtags = [tag for tag in default_hashtags if tag.lower() != "#shorts"]
    missing = [tag for tag in default_hashtags if tag.lower() not in existing]
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


def _env_mode_blocks(name: str, default: str = "block") -> bool:
    return os.environ.get(name, default).strip().lower() == "block"


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


def _video_url(video_id: str, meta: dict | None = None) -> str:
    if not video_id:
        return ""
    if meta is not None and meta.get("is_short") is False:
        return f"https://www.youtube.com/watch?v={video_id}"
    return f"https://www.youtube.com/shorts/{video_id}"


def _safe_label(value: object, fallback: str = "Highlights") -> str:
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
    return out or [f"{PLAYLIST_PREFIX}Highlights"]


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
        "script",
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
        "retention_contract",
        "search_intent",
        "next_episode_question",
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
        "upload_title_dedupe",
    )
    defaults = {
        "title": "",
        "description": "",
        "script": "",
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
        "retention_contract": {},
        "search_intent": {},
        "next_episode_question": "",
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
        "upload_title_dedupe": {},
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
            "url": _video_url(video_id, meta),
            "uploaded_at": uploaded_at.isoformat(),
            "platform": "youtube",
            "language": _LANGUAGE,
        }
    )
    return marker


def _adopt_existing_channel_upload(meta_file: Path, meta: dict, intent: dict, upload: dict) -> None:
    video_id = str(upload.get("video_id") or "").strip()
    uploaded_intent = {
        **intent,
        "status": "uploaded",
        "video_id": video_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "adopted_from": "youtube_channel_title_duplicate",
    }
    meta["upload_intent_key"] = intent["idempotency_key"]
    meta["upload_intent"] = uploaded_intent
    meta["youtube_operations"] = {
        "enabled": False,
        "reason": "channel_title_duplicate_adopted",
        "matched_upload": upload,
    }
    meta["session_action"] = {
        "applied": False,
        "operator_assist": False,
        "comment_text": "",
    }
    write_upload_intent(intent)
    write_upload_intent(uploaded_intent)
    marker = _done_marker(video_id, meta)
    marker["adopted_existing_upload"] = upload
    marker["media_lifecycle"] = cleanup_meta_artifacts(meta)
    meta_file.with_suffix(".done").write_text(json.dumps(marker, indent=2), encoding="utf-8")
    meta_file.unlink(missing_ok=True)


def _skip_tracked_channel_duplicate(meta_file: Path, meta: dict, intent: dict, upload: dict) -> None:
    skipped_intent = {
        **intent,
        "status": "skipped_duplicate",
        "video_id": str(upload.get("video_id") or ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "skip_reason": "channel_title_duplicate_already_tracked",
    }
    write_upload_intent(skipped_intent)
    cleanup_meta_artifacts(meta)
    meta_file.unlink(missing_ok=True)


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
                "description": os.environ.get(
                    "CHANNEL_PLAYLIST_DESCRIPTION", "Shorts grouped for easier binge watching."
                ),
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


def run_post_upload_operations(youtube, video_id: str, meta: dict) -> dict:
    """Run YouTube-only growth operations after a successful upload."""
    if os.environ.get("YOUTUBE_POST_UPLOAD_AUTOMATION", "1").lower() in {"0", "false", "no"}:
        return {"enabled": False}
    result: dict = {
        "enabled": True,
        "playlists": [],
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
    localizations_dict = {}
    try:
        from utils.ai_helper import ai_text

        en_title = _youtube_title(meta)
        en_desc = _youtube_description(meta)

        prompt = (
            "Translate the following YouTube video title and description into Hindi (hi), Russian (ru), and Spanish (es).\n\n"
            f"Title: {en_title}\n"
            f"Description: {en_desc}\n\n"
            "Return valid JSON strictly matching this schema:\n"
            "{\n"
            '  "hi": {"title": "...", "description": "..."},\n'
            '  "ru": {"title": "...", "description": "..."},\n'
            '  "es": {"title": "...", "description": "..."}\n'
            "}"
        )
        translated_json = ai_text(prompt, timeout=25, json_mode=True)
        if translated_json:
            clean = re.sub(r"```(?:json)?\s*|\s*```", "", translated_json).strip()
            locs = json.loads(clean)
            if "hi" in locs and "title" in locs["hi"]:
                localizations_dict = locs
                meta["localizations"] = locs
    except Exception as e:
        log.warning(f"Translation logic failed: {e}")

    part_str = "snippet,status"
    body_payload = {
        "snippet": {
            "title": _youtube_title(meta),
            "description": _youtube_description(meta),
            "tags": _normalise_tags(meta.get("tags")),
            "categoryId": str(meta.get("youtube_category_id") or "15"),
            "defaultLanguage": "en",
        },
        "status": status,
    }

    if localizations_dict:
        part_str += ",localizations"
        body_payload["localizations"] = localizations_dict

    request = youtube.videos().insert(
        part=part_str,
        body=body_payload,
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
        log.info("Scheduled: %s at %s", _video_url(video_id, meta), scheduled_publish_at)
    else:
        log.info("Published: %s", _video_url(video_id, meta))
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
    skipped_duplicates = 0
    require_upload = _env_bool("REQUIRE_UPLOAD_ON_PUBLISH", False)
    if require_upload and not pending:
        log.error("Publish window required an upload, but no generated Short metadata was found in %s.", VIDEOS_DIR)
        sys.exit(1)
    quota_row = write_quota_ledger_row(estimate_publish_run_cost(videos=len(pending)))
    if (quota_row.get("guard") or {}).get("block"):
        log.error("Quota guard blocked upload: %s", (quota_row.get("guard") or {}).get("reason"))
        return
    existing_titles = _existing_upload_titles(VIDEOS_DIR)
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
        if slot_duplicate and _env_mode_blocks("UPLOAD_SLOT_IDEMPOTENCY_MODE"):
            log.warning(
                "Skipping duplicate publish slot %s already published as %s",
                intent_slot,
                slot_duplicate.get("video_id"),
            )
            skipped_duplicates += 1
            continue
        intent = build_upload_intent(meta, meta_file=str(meta_file), slot=intent_slot)
        meta["upload_intent_key"] = intent["idempotency_key"]
        meta["upload_intent"] = intent

        title_dedupe = _apply_unique_upload_title(meta, existing_titles)
        if title_dedupe.get("applied"):
            log.info(
                "Adjusted duplicate upload title: %s -> %s",
                title_dedupe.get("before"),
                title_dedupe.get("after"),
            )
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
            "applied": False,
            "operator_assist": False,
            "comment_text": "",
        }
        marker = _done_marker(video_id, meta)
        marker["media_lifecycle"] = cleanup_meta_artifacts(meta)
        meta_file.with_suffix(".done").write_text(
            json.dumps(marker, indent=2),
            encoding="utf-8",
        )
        meta_file.unlink()
        existing_titles.add(_title_key(_youtube_title(meta)))
        uploaded += 1
    log.info("%d/%d video(s) uploaded to YouTube.", uploaded, attempted)
    if uploaded == 0 and attempted == 0 and skipped_duplicates:
        log.info(
            "%d generated metadata item(s) skipped because upload idempotency already satisfied the slot.",
            skipped_duplicates,
        )
        return
    if attempted and uploaded == 0:
        sys.exit(1)
    if require_upload and uploaded == 0 and attempted == 0:
        log.warning(
            "Publish window required an upload, but no eligible candidate cleared the "
            "editorial/quality gate this cycle; treating as a safe skip instead of a hard failure."
        )
        return


if __name__ == "__main__":
    main()
