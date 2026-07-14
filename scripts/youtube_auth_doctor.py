#!/usr/bin/env python3
"""Report YouTube OAuth visibility without printing token material."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.youtube_oauth import (
    ANALYTICS_SCOPE,
    COMMENTS_SCOPE,
    FULL_YOUTUBE_SCOPE,
    READONLY_SCOPE,
    TOKEN_ENV,
    UPLOAD_SCOPE,
    load_token_info,
    redacted_token_diagnostics,
    token_issue_codes,
)

TOKEN_FILE = ROOT / "youtube_token.json"

REQUIREMENTS = {
    "upload": [UPLOAD_SCOPE, FULL_YOUTUBE_SCOPE],
    "readonly": [READONLY_SCOPE, FULL_YOUTUBE_SCOPE],
    "comments": [COMMENTS_SCOPE, FULL_YOUTUBE_SCOPE],
    "analytics": [ANALYTICS_SCOPE, READONLY_SCOPE],
}


def build_report(token_file: Path = TOKEN_FILE, env_var: str = TOKEN_ENV) -> dict:
    info = load_token_info(token_file, env_var)
    diagnostics = redacted_token_diagnostics(info)
    capabilities = diagnostics["capabilities"]
    missing = [name for name, ok in capabilities.items() if not ok]
    issues = token_issue_codes(info)
    if info.present:
        issues.extend(f"youtube_{name}_scope_missing" for name in missing)
    return {
        "token": {
            **diagnostics,
            "token_file": str(Path(token_file)),
            "env_present": bool(os.environ.get(env_var, "").strip()),
        },
        "requirements": REQUIREMENTS,
        "issues": issues,
        "status": "ok" if info.present and not missing else "incomplete",
    }


def _print_text(report: dict) -> None:
    token = report["token"]
    print("YouTube auth doctor")
    print(f"source: {token['source']}")
    print(f"token_file_exists: {token['token_file_exists']}")
    print(f"env_present: {token['env_present']} ({token['env_var']})")
    print(f"has_refresh_token: {token['has_refresh_token']}")
    if token.get("expiry"):
        print(f"expiry: {token['expiry']}")
    if token.get("client_id_suffix"):
        print(f"client_id_suffix: ...{token['client_id_suffix']}")
    print("capabilities:")
    for name, ok in token["capabilities"].items():
        print(f"  {name}: {'ok' if ok else 'missing'}")
    if report["issues"]:
        print("issues:")
        for issue in report["issues"]:
            print(f"  {issue}")
    else:
        print("issues: none")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print machine-readable redacted diagnostics.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when the token is missing or incomplete.")
    args = parser.parse_args()
    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_text(report)
    return 2 if args.strict and report["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
