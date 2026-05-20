#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
upload_tiktok.py — Faz upload dos vídeos gerados para o TikTok
=================================================================
Usa a Content Posting API oficial:

  POST /v2/post/publish/video/init/    → cria a sessão de upload
  PUT  <upload_url>                    → envia o arquivo em chunks
  POST /v2/post/publish/status/fetch/  → polling até publicar

Requer: tiktok_token.json (gerado por auth_tiktok.py uma única vez)
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from utils import tiktok_quota

# Locale axis — mirrors generate_shorts.py. When LANGUAGE=pt-BR (or any
# non-en locale), we upload from `_videos_pt-BR/` so a single repo can
# serve sibling channels (English @wildbrief_x, Portuguese @wildbriefbr…)
# without entangling state.
_LANGUAGE  = os.environ.get("LANGUAGE", "en").strip() or "en"
LOG_FILE   = f"upload_tiktok{'' if _LANGUAGE == 'en' else '_' + _LANGUAGE}.log"
VIDEOS_DIR = Path("_videos") if _LANGUAGE == "en" else Path(f"_videos_{_LANGUAGE}")
TOKEN_FILE = Path("tiktok_token.json")

# TikTok Open API v2 endpoints.
API_BASE         = "https://open.tiktokapis.com"
INIT_URL         = f"{API_BASE}/v2/post/publish/video/init/"
INBOX_INIT_URL   = f"{API_BASE}/v2/post/publish/inbox/video/init/"
STATUS_URL       = f"{API_BASE}/v2/post/publish/status/fetch/"
TOKEN_REFRESH_URL = f"{API_BASE}/v2/oauth/token/"
USER_INFO_URL    = f"{API_BASE}/v2/user/info/"

# Chunked upload tuning. TikTok's documented rules:
#   - min chunk = 5 MB (except the LAST chunk, if there are > 1 chunks)
#   - max chunk = 64 MB
#   - chunk_size <= video_size (so single-chunk uploads MUST set
#       chunk_size = video_size, not the 5 MB default)
#   - chunk count <= 1000
# Wild Brief shorts are always under 64 MB, so `_compute_chunking()`
# returns 1 chunk == video_size; the multi-chunk branch only matters
# for hypothetical bigger inputs.
MIN_CHUNK_SIZE = 5 * 1024 * 1024
MAX_CHUNK_SIZE = 64 * 1024 * 1024
MAX_RETRIES = 4
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


def _compute_chunking(video_size: int) -> tuple[int, int]:
    """Return (chunk_size, total_chunks) that satisfy TikTok's rules.

    Earlier versions hard-coded CHUNK_SIZE=5MB and ceil'd the count,
    which produced bodies TikTok rejects with
    `invalid_params - The total chunk count is invalid` whenever the
    video was under 5 MB (chunk_size > video_size) or just above 5 MB
    (last chunk would be < 5 MB).
    """
    if video_size <= MAX_CHUNK_SIZE:
        return video_size, 1
    # Multi-chunk path: try the largest legal chunk_size first,
    # shrinking if the leftover last chunk would fall under the 5 MB
    # floor. This always terminates because at chunk_size == MIN we
    # can fold the leftover into the previous chunk (last < 2*MIN).
    chunk = MAX_CHUNK_SIZE
    while chunk >= MIN_CHUNK_SIZE:
        total = (video_size + chunk - 1) // chunk
        last = video_size - chunk * (total - 1)
        if last >= MIN_CHUNK_SIZE:
            return chunk, total
        chunk -= MIN_CHUNK_SIZE
    # Pathological fallback (shouldn't happen with the loop bounds
    # above): one giant chunk equal to video_size.
    return video_size, 1

# Polling cadence for publish status. TikTok says "available for query
# up to 24h after init"; in practice the FAILED/PUBLISH_COMPLETE state
# lands within 30s for small files.
STATUS_POLL_INITIAL = 5
STATUS_POLL_MAX_S   = 300
STATUS_POLL_BACKOFF = 1.5

# Tracks per-invocation how many videos got soft-skipped because the
# TikTok app is still in the multi-week review queue. When ALL pending
# uploads in a run hit this state (and only this state), `main()` exits
# 0 so the workflow shows green — the videos just wait for the next
# cron after TikTok approves. Reset at the start of `main()`.
_audit_pending_count = 0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ── Token handling ──────────────────────────────────────────────────

def _load_token() -> dict:
    """Read tiktok_token.json with clear diagnostics on common failures."""
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            "tiktok_token.json não encontrado! Execute auth_tiktok.py "
            "primeiro (ou defina o secret TIKTOK_TOKEN no GitHub)."
        )
    raw = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not raw:
        raise RuntimeError(
            "tiktok_token.json está vazio. O secret TIKTOK_TOKEN "
            "provavelmente não foi configurado. Rode auth_tiktok.py "
            "localmente e copie o conteúdo para o secret TIKTOK_TOKEN."
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"tiktok_token.json malformado ({exc}). Recrie com auth_tiktok.py."
        ) from exc
    # TikTok wraps successful responses in {"data": {...}, "error": ...}.
    # auth_tiktok.py persists the raw response, so unwrap if needed.
    if "data" in data and isinstance(data["data"], dict):
        merged = dict(data["data"])
        if "client_key" in data:
            merged["client_key"] = data["client_key"]
        data = merged
    if not data.get("access_token"):
        raise RuntimeError(
            "tiktok_token.json não contém access_token. Re-autorize "
            "com auth_tiktok.py."
        )
    if not data.get("refresh_token"):
        raise RuntimeError(
            "tiktok_token.json não contém refresh_token. Re-autorize "
            "com auth_tiktok.py (a primeira autorização gera o "
            "refresh_token)."
        )
    return data


def _persist_token_to_github_secret(token: dict) -> bool:
    """Push the rotated TikTok token JSON back to the TIKTOK_TOKEN
    GitHub repository secret so the next workflow run starts with a
    valid refresh_token.

    TikTok rotates the refresh_token on EVERY refresh and invalidates
    the previous one immediately. Without this round-trip, the local
    file gets the new token but the secret keeps the (now-dead) old
    one — and the next run dies with `invalid_grant`.

    Requires two env vars (both set by the workflow):
      - GH_REPO_FULL       (auto-set as ${{ github.repository }})
      - TIKTOK_SECRETS_PAT (PAT with Actions secrets read+write;
                            see SETUP.md §1.5)

    Best-effort: returns False on any failure and only WARNS — we
    still have a valid runtime token for this run; the failure mode
    only bites the NEXT run, and the user can re-mint manually.
    """
    repo = os.environ.get("GH_REPO_FULL", "").strip()
    pat = os.environ.get("TIKTOK_SECRETS_PAT", "").strip()
    if not repo or not pat:
        log.warning(
            "⚠️ TIKTOK_SECRETS_PAT/GH_REPO_FULL ausentes — refresh_token "
            "rotacionado NÃO será persistido. Próxima run vai morrer com "
            "invalid_grant. Configure conforme SETUP.md §1.5."
        )
        return False
    try:
        from nacl import encoding, public  # type: ignore
    except ImportError:
        log.warning(
            "⚠️ pynacl não está instalado — não consigo encriptar pro "
            "GitHub Secrets API. Adicione `pynacl` em requirements.txt."
        )
        return False

    api = f"https://api.github.com/repos/{repo}/actions/secrets"
    headers = {
        "Authorization":        f"Bearer {pat}",
        "Accept":               "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        r = requests.get(f"{api}/public-key", headers=headers, timeout=20)
        if r.status_code != 200:
            log.warning(
                "⚠️ GET /actions/secrets/public-key → %s %s",
                r.status_code, r.text[:200],
            )
            return False
        pk = r.json()
        sealed = public.SealedBox(
            public.PublicKey(pk["key"].encode("utf-8"),
                             encoder=encoding.Base64Encoder)
        )
        body = json.dumps(token, indent=2).encode("utf-8")
        ciphertext = sealed.encrypt(body)
        encoded = encoding.Base64Encoder.encode(ciphertext).decode("utf-8")

        r = requests.put(
            f"{api}/TIKTOK_TOKEN",
            headers=headers,
            json={"encrypted_value": encoded, "key_id": pk["key_id"]},
            timeout=20,
        )
        if r.status_code not in (201, 204):
            log.warning(
                "⚠️ PUT /actions/secrets/TIKTOK_TOKEN → %s %s",
                r.status_code, r.text[:200],
            )
            return False
        log.info("🔐 TIKTOK_TOKEN GitHub secret atualizado.")
        return True
    except Exception as exc:
        log.warning("⚠️ Falha ao persistir TIKTOK_TOKEN no GitHub: %s", exc)
        return False


def _refresh_access_token(token: dict) -> dict:
    """Use refresh_token to mint a new access_token. Saves token back."""
    client_key = (token.get("client_key")
                  or os.environ.get("TIKTOK_CLIENT_KEY", "")).strip()
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
    if not client_key or not client_secret:
        raise RuntimeError(
            "TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET não configurados — "
            "necessários para renovar o access_token."
        )
    resp = requests.post(
        TOKEN_REFRESH_URL,
        data={
            "client_key":    client_key,
            "client_secret": client_secret,
            "grant_type":    "refresh_token",
            "refresh_token": token["refresh_token"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("error"):
        raise RuntimeError(f"TikTok refresh falhou: {payload}")
    new_token = dict(token)
    new_token.update({
        "access_token":  payload.get("access_token", token["access_token"]),
        "refresh_token": payload.get("refresh_token", token["refresh_token"]),
        "expires_in":    payload.get("expires_in"),
        "refreshed_at":  datetime.now(timezone.utc).isoformat(),
        "scope":         payload.get("scope", token.get("scope", "")),
    })
    new_token["client_key"] = client_key
    TOKEN_FILE.write_text(json.dumps(new_token, indent=2))
    log.info("✅ access_token renovado via refresh_token.")
    _persist_token_to_github_secret(new_token)
    return new_token


def _is_token_expired(token: dict) -> bool:
    """True if the access_token should be refreshed proactively.

    Decides based on `refreshed_at` (stamped by `_refresh_access_token`)
    or `issued_at` (stamped by `auth_tiktok.py` at initial mint) plus
    `expires_in`. If NEITHER timestamp is present, we trust the token
    and skip the preemptive refresh — refreshing a fresh access_token
    unnecessarily would burn the single-use refresh_token and break
    the first workflow run after every manual `auth_tiktok.py` mint.
    """
    expires_in = token.get("expires_in")
    if not isinstance(expires_in, (int, float)):
        return True
    ts_str = token.get("refreshed_at") or token.get("issued_at")
    if not ts_str:
        return False
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return True
    age = (datetime.now(timezone.utc) - ts).total_seconds()
    return age >= max(0, float(expires_in) - 300)


def get_access_token() -> tuple[str, dict]:
    """Returns (access_token, full_token_dict). Refreshes if expired."""
    token = _load_token()
    if _is_token_expired(token):
        token = _refresh_access_token(token)
    return token["access_token"], token


# ── Caption building ────────────────────────────────────────────────

def _build_caption(meta: dict) -> str:
    """Combine title + description + hashtags into one ≤2200 char caption.

    TikTok has a single `title` field on the post which doubles as the
    caption: hashtags go inline. We respect their hard limits:
      - caption (title field) max 2200 chars
      - max 100 hashtags (we ship 4-6)
    """
    title = (meta.get("title") or "").strip()
    description = (meta.get("description") or "").strip()
    # Description often already ends with the hashtag block; if not,
    # append a sensible default chosen by generate_shorts.py.
    parts: list[str] = []
    if title:
        parts.append(title)
    if description and description not in title:
        parts.append(description)
    caption = "\n\n".join(parts).strip() or "Wild Brief"
    if len(caption) > 2200:
        caption = caption[:2190].rstrip() + "…"
    return caption


# ── Publish flow ────────────────────────────────────────────────────

def _post_json(url: str, access_token: str, body: dict,
                timeout: int = 30) -> dict:
    """POST JSON to a TikTok API endpoint with bearer auth."""
    resp = requests.post(
        url,
        json=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json; charset=UTF-8",
        },
        timeout=timeout,
    )
    try:
        payload = resp.json()
    except Exception:
        payload = {"raw": resp.text[:500]}
    if resp.status_code >= 400:
        raise RuntimeError(
            f"TikTok API {url} → HTTP {resp.status_code}: {payload}"
        )
    err = (payload.get("error") or {})
    if err and err.get("code") and err["code"] not in ("ok", ""):
        raise RuntimeError(f"TikTok API {url} → error {err}")
    return payload


def _init_direct_post(access_token: str, video_size: int,
                       caption: str, privacy_level: str,
                       disable_comment: bool, disable_duet: bool,
                       disable_stitch: bool) -> dict:
    """POST /post/publish/video/init/ — kicks off a DIRECT_POST upload."""
    chunk_size, total_chunks = _compute_chunking(video_size)
    body = {
        "post_info": {
            "title":           caption[:2200],
            "privacy_level":   privacy_level,
            "disable_duet":    disable_duet,
            "disable_comment": disable_comment,
            "disable_stitch":  disable_stitch,
            # Cover frame at 1s — gives Ken Burns a beat to settle.
            "video_cover_timestamp_ms": 1000,
            # Required disclosure: every Short on this channel has
            # AI-authored voice-over + AI-selected imagery.
            "brand_content_toggle": False,
            "brand_organic_toggle": False,
        },
        "source_info": {
            "source":            "FILE_UPLOAD",
            "video_size":        video_size,
            "chunk_size":        chunk_size,
            "total_chunk_count": total_chunks,
        },
    }
    return _post_json(INIT_URL, access_token, body)


def _init_inbox_upload(access_token: str, video_size: int) -> dict:
    """Fallback path: drop the video into the user's TikTok inbox as a
    draft. The user must finalize publish in the app. Used when DIRECT_POST
    is unavailable for an unaudited app.
    """
    chunk_size, total_chunks = _compute_chunking(video_size)
    body = {
        "source_info": {
            "source":            "FILE_UPLOAD",
            "video_size":        video_size,
            "chunk_size":        chunk_size,
            "total_chunk_count": total_chunks,
        },
    }
    return _post_json(INBOX_INIT_URL, access_token, body)


def _upload_chunks(upload_url: str, video_path: Path) -> None:
    """PUT the file to TikTok's signed upload_url in chunks that match
    what `_init_*` told TikTok to expect. TikTok rejects PUTs whose
    Content-Range doesn't line up with the init metadata."""
    total = video_path.stat().st_size
    chunk_size, _ = _compute_chunking(total)
    sent = 0
    with video_path.open("rb") as fh:
        chunk_index = 0
        while sent < total:
            data = fh.read(chunk_size)
            if not data:
                break
            start = sent
            end = sent + len(data) - 1
            attempt = 0
            while True:
                try:
                    resp = requests.put(
                        upload_url,
                        data=data,
                        headers={
                            "Content-Type":   "video/mp4",
                            "Content-Length": str(len(data)),
                            "Content-Range":  f"bytes {start}-{end}/{total}",
                        },
                        timeout=300,
                    )
                except (requests.ConnectionError, requests.Timeout) as exc:
                    if attempt < MAX_RETRIES:
                        attempt += 1
                        wait = 2 ** attempt
                        log.warning("  ⚠️ %s on chunk %d; retry %d/%d in %ds",
                                    type(exc).__name__, chunk_index,
                                    attempt, MAX_RETRIES, wait)
                        time.sleep(wait)
                        continue
                    raise
                if resp.status_code in RETRYABLE_STATUSES:
                    if attempt < MAX_RETRIES:
                        attempt += 1
                        wait = 2 ** attempt
                        log.warning("  ⚠️ HTTP %d on chunk %d; retry %d/%d in %ds",
                                    resp.status_code, chunk_index,
                                    attempt, MAX_RETRIES, wait)
                        time.sleep(wait)
                        continue
                if resp.status_code >= 400:
                    raise RuntimeError(
                        f"TikTok chunk PUT failed: HTTP {resp.status_code} "
                        f"body={resp.text[:300]}"
                    )
                break
            sent += len(data)
            chunk_index += 1
            pct = int(100 * sent / total) if total else 100
            log.info("  Upload: %d%% (chunk %d, %d/%d bytes)",
                     pct, chunk_index, sent, total)


def _poll_publish_status(access_token: str, publish_id: str) -> dict:
    """Poll status/fetch until terminal state. Returns the final payload.

    Terminal states:
      - PUBLISH_COMPLETE    → direct-post succeeded
      - SEND_TO_USER_INBOX  → inbox upload reached the user's TikTok
                              app; they finalize publish manually. This
                              is terminal for inbox mode — polling
                              forever for PUBLISH_COMPLETE would just
                              waste 5 min and exit with TimeoutError.
      - FAILED              → permanent failure
    Intermediate: PROCESSING_UPLOAD, PROCESSING_*.
    """
    deadline = time.time() + STATUS_POLL_MAX_S
    wait = STATUS_POLL_INITIAL
    while time.time() < deadline:
        body = {"publish_id": publish_id}
        payload = _post_json(STATUS_URL, access_token, body, timeout=20)
        tiktok_quota.record("publish.status.fetch",
                            channel=_LANGUAGE, publish_id=publish_id)
        data = (payload.get("data") or {})
        status = data.get("status", "")
        log.info("  📡 publish status: %s", status or "(empty)")
        if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            return data
        if status == "FAILED":
            reason = data.get("fail_reason") or data
            raise RuntimeError(f"TikTok publish FAILED: {reason}")
        time.sleep(wait)
        wait = min(int(wait * STATUS_POLL_BACKOFF) + 1, 30)
    raise TimeoutError(
        f"TikTok publish status polling timed out after {STATUS_POLL_MAX_S}s "
        f"for publish_id={publish_id}"
    )


def upload_video(access_token: str, meta: dict) -> str | None:
    """Upload a single video to TikTok. Returns the publish_id or None.

    Honors the env knob `TIKTOK_PUBLISH_MODE`:
      - "direct" (default) → posts go live immediately via Direct Post API.
        Requires the app to be approved for the `video.publish` scope.
      - "inbox"            → drops as a draft in the user's TikTok inbox.
        The user finalizes from the TikTok mobile app. Useful while the
        Direct Post scope is pending review.
    """
    video_field = meta.get("video")
    if not video_field:
        log.error("Metadata sem campo 'video' — pulando.")
        return None
    video_path = Path(video_field)
    if not video_path.exists():
        log.error(f"Vídeo não encontrado: {video_path}")
        return None

    caption = _build_caption(meta)
    log.info(f"📤 Uploading: {caption[:60]}…")

    privacy_level = (os.environ.get("TIKTOK_PRIVACY", "")
                      or meta.get("privacy_level")
                      or "PUBLIC_TO_EVERYONE").upper()
    disable_comment = _flag(os.environ.get("TIKTOK_DISABLE_COMMENT"), False)
    disable_duet    = _flag(os.environ.get("TIKTOK_DISABLE_DUET"),    False)
    disable_stitch  = _flag(os.environ.get("TIKTOK_DISABLE_STITCH"),  False)

    mode = (os.environ.get("TIKTOK_PUBLISH_MODE", "direct").strip().lower()
            or "direct")
    video_size = video_path.stat().st_size

    try:
        if mode == "inbox":
            init_payload = _init_inbox_upload(access_token, video_size)
            tiktok_quota.record("video.upload.init", channel=_LANGUAGE)
        else:
            init_payload = _init_direct_post(
                access_token, video_size, caption, privacy_level,
                disable_comment, disable_duet, disable_stitch,
            )
            tiktok_quota.record("video.publish.init", channel=_LANGUAGE)
    except RuntimeError as exc:
        # Apps awaiting TikTok review return specific codes when asked
        # to do anything beyond `SELF_ONLY` posts to private accounts.
        # We have two behaviours depending on what the operator wanted:
        #
        #   privacy=PUBLIC_TO_EVERYONE → soft-wait. The operator has
        #     opted into "publish publicly the moment the app is
        #     audited"; falling back to Inbox would dump unwanted
        #     drafts in their phone. Leave the .json pending and let
        #     the next cron retry.
        #
        #   privacy=SELF_ONLY (or other) → fall back to Inbox so the
        #     operator can finish publishing manually from the TikTok
        #     mobile app. This is the historical workflow.
        msg = str(exc)
        unaudited_signals = (
            "unaudited_client_can_only_post_to_private_accounts",
            "scope_not_authorized",
            "unaudited_client",
        )
        is_unaudited = any(s in msg for s in unaudited_signals)
        if is_unaudited and mode != "inbox":
            if privacy_level == "PUBLIC_TO_EVERYONE":
                global _audit_pending_count
                _audit_pending_count += 1
                log.warning(
                    "  ⏳ TikTok app still unaudited — public direct-post "
                    "denied. Video stays queued for the next cron retry. "
                    "This is expected until TikTok approves the app."
                )
                return None
            log.warning(
                "  ⚠️ TikTok refused direct post (app likely unaudited): %s",
                msg[:200],
            )
            log.warning(
                "  ⤷ Retrying via Inbox — open the TikTok app on your "
                "phone to finalize the draft."
            )
            try:
                init_payload = _init_inbox_upload(access_token, video_size)
                tiktok_quota.record("video.upload.init", channel=_LANGUAGE)
                mode = "inbox"
            except RuntimeError as exc2:
                log.error("  ❌ TikTok inbox fallback also failed: %s", exc2)
                return None
        else:
            log.error("  ❌ TikTok init failed: %s", exc)
            return None

    data = (init_payload.get("data") or {})
    publish_id = data.get("publish_id") or ""
    upload_url = data.get("upload_url") or ""
    if not publish_id or not upload_url:
        log.error("  ❌ TikTok init returned no publish_id/upload_url: %s",
                  init_payload)
        return None

    try:
        _upload_chunks(upload_url, video_path)
    except Exception as exc:
        log.error("  ❌ Chunk upload failed: %s", exc)
        return None

    # Polling completes the publish handshake (TikTok runs an async
    # moderation pass before the video goes live).
    try:
        final = _poll_publish_status(access_token, publish_id)
    except Exception as exc:
        log.error("  ❌ Publish never reached PUBLISH_COMPLETE: %s", exc)
        return None

    public_id = final.get("publicaly_available_post_id") or final.get("video_id") or ""
    if mode == "inbox":
        log.info("  ✅ Drafted to inbox — finalize in the TikTok app.")
        log.info("     publish_id=%s", publish_id)
    else:
        tt_url = _tiktok_url(public_id, meta)
        log.info("  ✅ Publicado: %s", tt_url or f"publish_id={publish_id}")
    return public_id or publish_id


def _flag(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "y", "on")


def _tiktok_url(public_id: str, meta: dict) -> str:
    """Construct the canonical TikTok share URL when we have an id."""
    if not public_id:
        return ""
    handle = (meta.get("channel_handle")
              or os.environ.get("CHANNEL_WATERMARK", "@wildbrief_x")).lstrip("@")
    return f"https://www.tiktok.com/@{handle}/video/{public_id}"


# ── Pending-metadata orchestration ─────────────────────────────────

def _collect_pending_meta(videos_dir: Path) -> list[Path]:
    """Return meta JSON sidecars in `videos_dir` for the uploader to process.

    Only files matching `short-…` / `roundup-…` are real meta sidecars —
    other `.json` files (notably `shorts_done.json`, which the generator
    uses for idempotency) are NOT video metadata.
    """
    return sorted(p for p in videos_dir.glob("*.json")
                  if p.stem.startswith(("short-", "roundup-")))


def main():
    from utils.panic import abort_if_halted
    abort_if_halted("upload_tiktok")

    global _audit_pending_count
    _audit_pending_count = 0

    if not TOKEN_FILE.exists():
        log.error(
            "❌ tiktok_token.json not found. The tiktok-bot workflow "
            "restores it from the TIKTOK_TOKEN secret — that secret may "
            "be unset or invalid JSON. Run auth_tiktok.py locally to "
            "refresh it."
        )
        sys.exit(2)

    try:
        access_token, _ = get_access_token()
    except FileNotFoundError as e:
        log.error("❌ %s", e)
        sys.exit(2)
    except RuntimeError as e:
        log.error("❌ %s", e)
        sys.exit(2)

    pending = _collect_pending_meta(VIDEOS_DIR)
    if not pending:
        log.info("Nenhum vídeo pendente para upload.")
        return
    log.info("📋 %d vídeo(s) pendente(s) para upload", len(pending))

    uploaded = 0
    for meta_file in pending:
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception as e:
            log.error("Falha ao ler %s: %s", meta_file.name, e)
            continue
        if not isinstance(meta, dict):
            log.error("Pulando %s: metadata não é um dict (got %s).",
                      meta_file.name, type(meta).__name__)
            continue

        publish_id = upload_video(access_token, meta)
        if publish_id:
            done_file = meta_file.with_suffix(".done")
            tt_url = _tiktok_url(publish_id, meta)
            done_file.write_text(json.dumps({
                "video_id":    publish_id,
                "url":         tt_url,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "title":       meta.get("title", ""),
                "description": meta.get("description", ""),
                "tags":        meta.get("tags", []),
                "category":    meta.get("category", ""),
                "is_short":    meta.get("is_short", False),
                # Pexels source-clip identity — carries through so a
                # future audit can match a TikTok post back to its
                # source clip; the dedup ledger reads from this.
                "pexels_video_id":     meta.get("pexels_video_id", ""),
                "pexels_download_url": meta.get("pexels_download_url", ""),
                # A/B variant tags so tiktok_analytics.py can correlate
                # them with the retention numbers it pulls.
                "experiments": meta.get("experiments", {}),
                "language":    _LANGUAGE,
            }, indent=2))
            # Permanent dedup ledger — append BEFORE deleting the meta
            # file so a crash between the two steps still leaves the
            # ledger truthful.
            try:
                from fetch_animals import record_published_clip
                record_published_clip(
                    pexels_video_id=meta.get("pexels_video_id", ""),
                    story_id=meta.get("story_id", ""),
                    pexels_url=meta.get("pexels_download_url", ""),
                    platform_video_id=publish_id,
                )
            except Exception as exc:
                log.warning("⚠️ published_clips ledger update failed: %s", exc)
            meta_file.unlink()
            uploaded += 1

    log.info("🏁 %d/%d vídeo(s) publicado(s) no TikTok.", uploaded, len(pending))

    q = tiktok_quota.summary()
    log.info("📊 TikTok posts today: %d / %d (%.0f%%) — %s",
             q["used"], q["budget"], q["pct_used"],
             q["warning"] or "OK")

    if pending and uploaded == 0:
        # Soft-exit if every pending video was deferred waiting for
        # TikTok to audit the app. The workflow stays green; the
        # videos retry on the next cron.
        if _audit_pending_count == len(pending):
            log.info(
                "⏳ %d video(s) waiting for TikTok to approve the app. "
                "They'll publish automatically on the next cron after "
                "approval — no action needed. Exit 0.",
                len(pending),
            )
            return
        log.error("❌ All uploads failed (%d pending, 0 uploaded). Exiting non-zero.",
                  len(pending))
        sys.exit(1)


if __name__ == "__main__":
    main()
