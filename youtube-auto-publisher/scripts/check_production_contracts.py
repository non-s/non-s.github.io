from __future__ import annotations

import re
from pathlib import Path

ROOT = Path.cwd()
failures: list[str] = []


def read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def must_contain(rel_path: str, token: str, message: str) -> None:
    if token not in read(rel_path):
        failures.append(f"{rel_path}: {message}")


def must_match(rel_path: str, pattern: str, message: str) -> None:
    if not re.search(pattern, read(rel_path), flags=re.MULTILINE | re.DOTALL):
        failures.append(f"{rel_path}: {message}")


def must_not_match(rel_path: str, pattern: str, message: str) -> None:
    if re.search(pattern, read(rel_path), flags=re.MULTILINE | re.DOTALL):
        failures.append(f"{rel_path}: {message}")


must_contain(
    ".github/workflows/auto-publish.yml",
    "Validar secrets de producao",
    "auto-publish workflow must validate required secrets before expensive work",
)
must_contain(
    ".github/workflows/auto-publish.yml",
    "id: production_preflight",
    "auto-publish workflow must expose a production preflight output",
)
must_contain(
    ".github/workflows/auto-publish.yml",
    "can_publish=false",
    "auto-publish workflow must skip cleanly when required secrets are missing",
)
must_contain(
    ".github/workflows/auto-publish.yml",
    "steps.production_preflight.outputs.can_publish == 'true'",
    "expensive publishing steps must only run after a successful preflight",
)
must_contain(
    ".github/workflows/auto-publish.yml",
    "refresh_token",
    "auto-publish workflow must require unattended YouTube refresh tokens",
)
must_contain(
    ".github/workflows/auto-publish.yml",
    "token_path.chmod(0o600)",
    "auto-publish workflow must write token.json with restricted permissions",
)
must_not_match(
    ".github/workflows/auto-publish.yml",
    r"echo\s+\"\$YOUTUBE_TOKEN_JSON\"\s*>\s*token\.json",
    "auto-publish workflow must not write OAuth tokens with echo",
)

must_contain("config.py", "PEXELS_MAX_DOWNLOAD_MB", "Pexels download size limit must be configurable")
must_contain("config.py", "MAX_UPLOAD_RETRIES", "YouTube upload retry count must be configurable")
must_contain("config.py", "UPLOAD_RETRY_MAX_SLEEP_SECONDS", "YouTube retry sleep cap must be configurable")
must_contain("config.py", "HTTP_USER_AGENT", "HTTP user agent must be configurable")
must_contain("config.py", "require_youtube_token", "config validation must support upload token requirements")

must_contain("main.py", "write_json_atomic", "state JSON writes must be atomic")
must_contain("main.py", "clamp_int(duration", "video duration must be clamped")
must_contain("main.py", "clamp_int(num_clips", "clip count must be clamped")
must_contain("main.py", "config.validate_config", "pipeline must validate runtime config before API work")

must_contain("src/pexels_downloader.py", "HTTPAdapter", "Pexels downloader must use retry-capable sessions")
must_contain("src/pexels_downloader.py", "PEXELS_MAX_DOWNLOAD_MB", "Pexels downloader must enforce max download size")
must_contain("src/pexels_downloader.py", "num_clips: int | None = None", "Pexels downloader must accept main.py num_clips keyword")

must_contain("src/youtube_uploader.py", "RETRIABLE_STATUS_CODES", "YouTube uploader must classify retryable API responses")
must_contain("src/youtube_uploader.py", "os.getenv(\"CI\")", "YouTube uploader must not start interactive OAuth in CI")
must_contain("src/youtube_uploader.py", "_sleep_before_retry", "YouTube uploader must retry resumable upload chunks")
must_contain("src/youtube_uploader.py", "HttpError", "YouTube uploader must handle API retry errors")
must_match(
    "src/youtube_uploader.py",
    r"TOKEN_FILE\.write_text\(creds\.to_json\(\), encoding=\"utf-8\"\)",
    "local token refreshes must be written explicitly as UTF-8",
)

quality = read(".github/workflows/quality.yml")
if "check_production_contracts.py" not in quality:
    failures.append("quality workflow must run check_production_contracts.py")

if failures:
    print("PRODUCTION_CONTRACTS_FAILED")
    for failure in failures:
        print(f"- {failure}")
    raise SystemExit(1)

print("PRODUCTION_CONTRACTS_OK")
