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

from scripts.upload_intent import build_upload_intent, duplicate_slot_uploaded, duplicate_uploaded, write_upload_intent
from utils.api_quota_budget import estimate_publish_run_cost, write_quota_ledger_row
from utils.media_lifecycle import cleanup_meta_artifacts
from utils.publish_schedule import active_slot_label, canonical_slots, slot_label
from utils.session_graph import pinned_comment_payload
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
    title = (meta.get("seo_title") or meta.get("title") or "Nature fact of the day").strip()
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


def _existing_upload_ids(videos_dir: Path = VIDEOS_DIR) -> set[str]:
    video_ids: set[str] = set()
    for path in sorted(videos_dir.glob("*.done")):
        try:
            marker = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(marker, dict):
            video_id = str(marker.get("video_id") or "").strip()
            if video_id:
                video_ids.add(video_id)
    return video_ids


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


def _upload_title_map(rows: list[dict]) -> dict[str, dict]:
    by_title: dict[str, dict] = {}
    for row in rows:
        key = _title_key(row.get("title") or "")
        if key and row.get("video_id") and key not in by_title:
            by_title[key] = row
    return by_title


def _channel_uploads_from_intelligence(path: Path = YOUTUBE_INTELLIGENCE_FILE) -> list[dict]:
    payload = _read_json_object(path)
    rows: list[dict] = []
    sections = (
        ((payload.get("uploads_inventory") or {}).get("latest_uploads") or [], "youtube_intelligence.uploads"),
        ((payload.get("video_audit") or {}).get("top_public_videos") or [], "youtube_intelligence.audit"),
    )
    for items, source in sections:
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            normalised = _normalise_channel_upload(item, source=source)
            if normalised:
                rows.append(normalised)
    return rows


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


def _existing_channel_upload_titles(
    youtube=None, *, intelligence_path: Path = YOUTUBE_INTELLIGENCE_FILE
) -> dict[str, dict]:
    rows = _channel_uploads_from_intelligence(intelligence_path)
    try:
        rows = _fetch_recent_channel_uploads(youtube) + rows
    except Exception as exc:
        if _env_bool("YOUTUBE_CHANNEL_DEDUPE_REQUIRED", False):
            raise RuntimeError(f"YouTube channel duplicate preflight failed: {exc}") from exc
        log.warning("YouTube channel duplicate preflight unavailable: %s", exc)
    return _upload_title_map(rows)


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


def _video_url(video_id: str) -> str:
    return f"https://www.youtube.com/shorts/{video_id}" if video_id else ""


def _safe_label(value: object, fallback: str = "Nature Facts") -> str:
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
    raw_packaging = meta.get("packaging")
    packaging: dict = raw_packaging if isinstance(raw_packaging, dict) else {}
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
            "url": _video_url(video_id),
            "uploaded_at": uploaded_at.isoformat(),
            "platform": "youtube",
            "language": _LANGUAGE,
        }
    )
    return marker


def _record_published_clip(meta: dict, video_id: str) -> None:
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
    _record_published_clip(meta, video_id)
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


def _reply_to_parent_comment(youtube, parent_id: str, text: str) -> dict:
    request = youtube.comments().insert(
        part="snippet",
        body={
            "snippet": {
                "parentId": parent_id,
                "textOriginal": text,
            }
        },
    )
    response = _execute(request)
    return {
        "posted": True,
        "reply_id": response.get("id", ""),
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

    comment_context = meta.get("comment_context")
    if comment_context and isinstance(comment_context, dict):
        parent_id = comment_context.get("parent_comment_id")
        if parent_id:
            try:
                reply_text = f"We made this video to answer your question! Check it out here: https://youtube.com/shorts/{video_id}"
                result["parent_reply"] = _reply_to_parent_comment(youtube, parent_id, reply_text)
            except Exception as exc:
                result["parent_reply"] = {"posted": False, "error": f"{type(exc).__name__}: {exc}"}
                log.warning("Failed to reply to parent comment %s: %s", parent_id, exc)

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
        
        # 1. Pinned Comment Quiz (Interactive Trivia)
        if privacy == "public":
            try:
                from utils.ai_helper import ai_text
                animal = meta.get("title", "this animal")
                quiz_prompt = (
                    f"Create a short, super engaging multiple-choice trivia question about {animal}. "
                    "Format it exactly like this: 'Qual você acha que é a verdade sobre [animal]? A) [Opção 1] B) [Opção 2]. Responda abaixo! 👇'"
                )
                trivia = ai_text(quiz_prompt, timeout=15)
                if trivia:
                    comment_request = youtube.commentThreads().insert(
                        part="snippet",
                        body={
                            "snippet": {
                                "videoId": video_id,
                                "topLevelComment": {
                                    "snippet": {
                                        "textOriginal": trivia
                                    }
                                }
                            }
                        }
                    )
                    comment_response = comment_request.execute()
                    comment_id = comment_response["snippet"]["topLevelComment"]["id"]
                    log.info(f"Interactive Pinned Comment Quiz posted! Comment ID: {comment_id}")
            except Exception as e:
                log.error(f"Failed to post interactive trivia comment: {e}")
                
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
    existing_video_ids = _existing_upload_ids(VIDEOS_DIR)
    channel_upload_titles = _existing_channel_upload_titles(youtube)
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
        channel_duplicate = channel_upload_titles.get(_title_key(_youtube_title(meta)))
        if channel_duplicate and _env_mode_blocks("UPLOAD_CHANNEL_TITLE_DEDUPE_MODE"):
            intent = build_upload_intent(meta, meta_file=str(meta_file), slot=intent_slot)
            if str(channel_duplicate.get("video_id") or "") in existing_video_ids:
                log.warning(
                    "Skipping duplicate title %r already tracked as %s",
                    _youtube_title(meta),
                    channel_duplicate.get("video_id"),
                )
                _skip_tracked_channel_duplicate(meta_file, meta, intent, channel_duplicate)
            else:
                log.warning(
                    "Adopting existing channel upload for duplicate title %r as %s",
                    _youtube_title(meta),
                    channel_duplicate.get("video_id"),
                )
                _adopt_existing_channel_upload(meta_file, meta, intent, channel_duplicate)
                existing_video_ids.add(str(channel_duplicate.get("video_id") or ""))
            skipped_duplicates += 1
            existing_titles.add(_title_key(_youtube_title(meta)))
            continue
        title_dedupe = _apply_unique_upload_title(meta, existing_titles)
        if title_dedupe.get("applied"):
            log.info(
                "Adjusted duplicate upload title: %s -> %s",
                title_dedupe.get("before"),
                title_dedupe.get("after"),
            )
        intent = build_upload_intent(meta, meta_file=str(meta_file), slot=intent_slot)
        duplicate = duplicate_uploaded(intent)
        meta["upload_intent_key"] = intent["idempotency_key"]
        meta["upload_intent"] = intent
        if duplicate and _env_mode_blocks("UPLOAD_IDEMPOTENCY_MODE"):
            log.warning(
                "Skipping duplicate upload intent %s already published as %s",
                intent["idempotency_key"],
                duplicate.get("video_id"),
            )
            skipped_duplicates += 1
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
        _record_published_clip(meta, video_id)
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
