#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create youtube_token.json for the GitHub Actions YOUTUBE_TOKEN secret."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from utils.youtube_oauth import DEFAULT_SCOPES

SCOPES = DEFAULT_SCOPES
TOKEN_FILE = Path("youtube_token.json")
REPO = "non-s/non-s.github.io"


def _client_config(args: argparse.Namespace) -> dict:
    if args.client_secrets_file:
        data = json.loads(Path(args.client_secrets_file).read_text(encoding="utf-8"))
        if "installed" not in data:
            raise SystemExit("Client secrets JSON must contain an 'installed' OAuth client.")
        return data
    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    if not client_id:
        client_id = input("YOUTUBE_CLIENT_ID: ").strip()
    if not client_secret:
        client_secret = input("YOUTUBE_CLIENT_SECRET: ").strip()
    if not client_id or not client_secret:
        raise SystemExit("Missing YouTube OAuth client id/secret.")
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def _set_github_secret(secret_value: str) -> None:
    subprocess.run(
        ["gh", "secret", "set", "YOUTUBE_TOKEN", "--repo", REPO],
        input=secret_value,
        text=True,
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-secrets-file", help="Downloaded OAuth desktop-client JSON from Google Cloud.")
    parser.add_argument(
        "--set-github-secret", action="store_true", help="Update the repository YOUTUBE_TOKEN secret via gh."
    )
    parser.add_argument(
        "--print-secret", action="store_true", help="Print token JSON for manual copy. Avoid in shared terminals."
    )
    args = parser.parse_args()

    client_config = _client_config(args)
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    token_json = creds.to_json()
    TOKEN_FILE.write_text(token_json, encoding="utf-8")
    if args.set_github_secret:
        _set_github_secret(json.dumps(json.loads(token_json), separators=(",", ":")))

    print("\nYouTube OAuth complete.")
    print(f"Saved: {TOKEN_FILE.resolve()}")
    if args.set_github_secret:
        print(f"Updated GitHub Actions secret YOUTUBE_TOKEN in {REPO}.")
    elif args.print_secret:
        print("\nCreate or update this GitHub Actions secret:")
        print("  YOUTUBE_TOKEN")
        print("\nSecret value:")
        print(json.dumps(json.loads(token_json), separators=(",", ":")))
    else:
        print("Token JSON was not printed. Use --set-github-secret or --print-secret if needed.")


if __name__ == "__main__":
    main()
