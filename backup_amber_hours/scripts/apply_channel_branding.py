#!/usr/bin/env python3
"""Apply Amber Hours channel branding: title, banner, and live thumbnail.

One-off/manual admin tool. The channel avatar/profile picture has no
public YouTube Data API endpoint at all -- that still needs a manual
upload via YouTube Studio (Customization > Basic info > Picture), or the
linked Google/Brand Account photo settings.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from googleapiclient.http import MediaFileUpload  # noqa: E402

from upload_youtube import get_youtube_service  # noqa: E402

BRANDING_DIR = ROOT / "_assets" / "branding"
CHANNEL_TITLE = "Amber Hours"
BANNER_PATH = BRANDING_DIR / "banner_2560x1440.png"
THUMBNAIL_PATH = BRANDING_DIR / "thumbnail_1280x720.png"

ACTIVE_BROADCAST_STATUSES = {"live", "ready", "testing"}


def update_channel_title(youtube, title: str) -> str:
    response = youtube.channels().list(part="brandingSettings", mine=True).execute()
    items = response.get("items") or []
    if not items:
        raise RuntimeError("No channel found for the authenticated account.")
    channel_id = items[0]["id"]
    branding = items[0].get("brandingSettings") or {}
    branding.setdefault("channel", {})["title"] = title
    youtube.channels().update(
        part="brandingSettings",
        body={"id": channel_id, "brandingSettings": branding},
    ).execute()
    return channel_id


def upload_banner(youtube, channel_id: str, banner_path: Path) -> str:
    media = MediaFileUpload(str(banner_path), mimetype="image/png")
    response = youtube.channelBanners().insert(media_body=media).execute()
    banner_url = response["url"]
    branding_response = youtube.channels().list(part="brandingSettings", id=channel_id).execute()
    branding = branding_response["items"][0].get("brandingSettings") or {}
    branding.setdefault("image", {})["bannerExternalUrl"] = banner_url
    youtube.channels().update(
        part="brandingSettings",
        body={"id": channel_id, "brandingSettings": branding},
    ).execute()
    return banner_url


def find_active_broadcast_id(youtube) -> str | None:
    response = (
        youtube.liveBroadcasts()
        .list(part="id,status", broadcastStatus="all", broadcastType="all", maxResults=50)
        .execute()
    )
    for item in response.get("items", []):
        if (item.get("status") or {}).get("lifeCycleStatus") in ACTIVE_BROADCAST_STATUSES:
            return item.get("id")
    return None


def set_live_thumbnail(youtube, broadcast_id: str, thumbnail_path: Path) -> None:
    media = MediaFileUpload(str(thumbnail_path), mimetype="image/png")
    youtube.thumbnails().set(videoId=broadcast_id, media_body=media).execute()


def main() -> int:
    youtube = get_youtube_service()
    ok = True

    try:
        channel_id = update_channel_title(youtube, CHANNEL_TITLE)
        print(f"Channel title set to {CHANNEL_TITLE!r} (channel {channel_id}).")
    except Exception as exc:
        print(f"Failed to update channel title: {exc}", file=sys.stderr)
        return 1

    if BANNER_PATH.exists():
        try:
            banner_url = upload_banner(youtube, channel_id, BANNER_PATH)
            print(f"Banner uploaded: {banner_url}")
        except Exception as exc:
            print(f"Failed to upload banner: {exc}", file=sys.stderr)
            ok = False
    else:
        print(f"Banner file not found at {BANNER_PATH}, skipped.", file=sys.stderr)
        ok = False

    if THUMBNAIL_PATH.exists():
        broadcast_id = find_active_broadcast_id(youtube)
        if broadcast_id:
            try:
                set_live_thumbnail(youtube, broadcast_id, THUMBNAIL_PATH)
                print(f"Live thumbnail set on broadcast {broadcast_id}.")
            except Exception as exc:
                print(f"Failed to set live thumbnail: {exc}", file=sys.stderr)
                ok = False
        else:
            print("No active broadcast found; skipped setting live thumbnail.", file=sys.stderr)
            ok = False
    else:
        print(f"Thumbnail file not found at {THUMBNAIL_PATH}, skipped.", file=sys.stderr)
        ok = False

    print(
        "NOTE: channel avatar/profile picture has no public YouTube Data API "
        "endpoint -- upload _assets/branding/avatar_800x800.png manually in "
        "YouTube Studio > Customization > Basic info > Picture."
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
