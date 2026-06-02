#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create youtube_token.json for the GitHub Actions YOUTUBE_TOKEN secret."""
from __future__ import annotations

import json
import os
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
TOKEN_FILE = Path("youtube_token.json")


def main() -> None:
    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    if not client_id:
        client_id = input("YOUTUBE_CLIENT_ID: ").strip()
    if not client_secret:
        client_secret = input("YOUTUBE_CLIENT_SECRET: ").strip()
    if not client_id or not client_secret:
        raise SystemExit("Missing YouTube OAuth client id/secret.")

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    print("\nYouTube OAuth complete.")
    print(f"Saved: {TOKEN_FILE.resolve()}")
    print("\nCreate or update this GitHub Actions secret:")
    print("  YOUTUBE_TOKEN")
    print("\nSecret value:")
    print(json.dumps(json.loads(creds.to_json()), separators=(",", ":")))


if __name__ == "__main__":
    main()
